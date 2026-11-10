"""Testes do executor: fila, aprovação, passos com o Claude (simulado) e travas de segurança."""
import re

import pytest

from conftest import entrar


def _login(cliente, email):
    c, _, _ = entrar(cliente, email)
    html = c.get("/executor").get_data(as_text=True)      # o login troca o token CSRF: pega o novo
    return c, re.search(r'name="csrf" value="([^"]+)"', html).group(1)


@pytest.fixture()
def ctx(cliente, empresa_demo):
    import db
    con = db.conectar()
    admin = next(c for c in empresa_demo.values() if c["papel"] == "admin")
    colab = next(c for c in empresa_demo.values() if c["papel"] == "colaborador")
    token = con.execute("SELECT token_coleta FROM contas WHERE email = ?", (colab["email"],)).fetchone()[0]
    if not token:
        token = "tok-teste-123"
        con.execute("UPDATE contas SET token_coleta = ? WHERE email = ?", (token, colab["email"]))
        con.commit()
    return {"con": con, "db": db, "admin": admin, "colab": colab, "token": token, "cliente": cliente}


def _api(cliente, token, caminho, corpo=None):
    return cliente().post(caminho, json=corpo or {}, headers={"Authorization": f"Bearer {token}"})


def test_executor_exige_liberacao_do_colaborador(ctx):
    r = _api(ctx["cliente"], ctx["token"], "/api/executor/proximo")
    assert r.status_code == 403


def test_token_invalido(ctx):
    assert _api(ctx["cliente"], "xxx", "/api/executor/proximo").status_code == 401


def test_comando_do_admin_so_roda_apos_aprovacao_do_colaborador(ctx):
    db, con = ctx["db"], ctx["con"]
    colab_id = con.execute("SELECT id FROM contas WHERE email = ?", (ctx["colab"]["email"],)).fetchone()[0]
    db.definir_executor_ativo(con, colab_id, True)

    adm, csrf = _login(ctx["cliente"], ctx["admin"]["email"])
    adm.post("/executor/novo", data={"csrf": csrf, "conta_id": colab_id, "instrucao": "Abrir a planilha de conciliação"})
    cmd = db.comandos_da_empresa(con, 1)[0]
    assert cmd["status"] == "aguardando"
    assert _api(ctx["cliente"], ctx["token"], "/api/executor/proximo").get_json()["comando"] is None

    # o admin não consegue aprovar no lugar do colaborador
    adm.post(f"/executor/{cmd['id']}/decidir", data={"csrf": csrf, "acao": "aprovar"})
    assert db.comando(con, cmd["id"])["status"] == "aguardando"

    col, csrf2 = _login(ctx["cliente"], ctx["colab"]["email"])
    col.post(f"/executor/{cmd['id']}/decidir", data={"csrf": csrf2, "acao": "aprovar"})
    r = _api(ctx["cliente"], ctx["token"], "/api/executor/proximo").get_json()
    assert r["comando"]["id"] == cmd["id"]


def test_fluxo_completo_com_claude_simulado(ctx, monkeypatch):
    import executor_ia
    db, con = ctx["db"], ctx["con"]
    colab_id = con.execute("SELECT id FROM contas WHERE email = ?", (ctx["colab"]["email"],)).fetchone()[0]
    db.definir_executor_ativo(con, colab_id, True)
    cid = db.criar_comando(con, 1, colab_id, colab_id, "Digitar um texto no bloco de notas")
    db.atualizar_comando(con, cid, status="aprovado")

    respostas = iter([
        [{"type": "tool_use", "id": "t1", "name": "computer", "input": {"action": "left_click", "coordinate": [10, 20]}}],
        [{"type": "tool_use", "id": "t2", "name": "computer", "input": {"action": "type", "text": "segredo123"}}],
        [{"type": "text", "text": "CONCLUÍDO: texto digitado."}],
    ])
    monkeypatch.setattr(executor_ia, "chamar_claude", lambda m, w, h: next(respostas))

    t = ctx["token"]
    assert _api(ctx["cliente"], t, "/api/executor/iniciar", {"comando_id": cid, "tela_w": 800, "tela_h": 600}).status_code == 200
    p1 = _api(ctx["cliente"], t, "/api/executor/passo", {"comando_id": cid, "screenshot": "AAAA"}).get_json()
    assert p1["acao"]["action"] == "left_click" and p1["tool_use_id"] == "t1"
    p2 = _api(ctx["cliente"], t, "/api/executor/passo", {"comando_id": cid, "screenshot": "BBBB", "tool_use_id": "t1"}).get_json()
    assert p2["acao"]["action"] == "type"
    p3 = _api(ctx["cliente"], t, "/api/executor/passo", {"comando_id": cid, "screenshot": "CCCC", "tool_use_id": "t2"}).get_json()
    assert p3["fim"] and p3["status"] == "concluido"

    final = db.comando(con, cid)
    assert final["status"] == "concluido" and final["passos"] == 2
    assert "AAAA" not in final["conversa"]                      # capturas não ficam guardadas
    log = " ".join(r["acao"] for r in db.log_do_comando(con, cid))
    assert "segredo123" not in log                               # texto digitado não fica no registro


def test_cancelar_no_painel_para_o_executor(ctx, monkeypatch):
    import executor_ia
    db, con = ctx["db"], ctx["con"]
    colab_id = con.execute("SELECT id FROM contas WHERE email = ?", (ctx["colab"]["email"],)).fetchone()[0]
    db.definir_executor_ativo(con, colab_id, True)
    cid = db.criar_comando(con, 1, colab_id, colab_id, "Tarefa longa de teste")
    db.atualizar_comando(con, cid, status="aprovado")
    monkeypatch.setattr(executor_ia, "chamar_claude", lambda m, w, h: [
        {"type": "tool_use", "id": "t1", "name": "computer", "input": {"action": "screenshot"}}])
    t = ctx["token"]
    _api(ctx["cliente"], t, "/api/executor/iniciar", {"comando_id": cid, "tela_w": 800, "tela_h": 600})
    col, csrf = _login(ctx["cliente"], ctx["colab"]["email"])
    col.post(f"/executor/{cid}/decidir", data={"csrf": csrf, "acao": "cancelar"})
    r = _api(ctx["cliente"], t, "/api/executor/passo", {"comando_id": cid, "screenshot": "AAAA"}).get_json()
    assert r["fim"] and r["status"] == "cancelado"


def test_limite_de_passos(ctx, monkeypatch):
    import config
    import executor_ia
    db, con = ctx["db"], ctx["con"]
    colab_id = con.execute("SELECT id FROM contas WHERE email = ?", (ctx["colab"]["email"],)).fetchone()[0]
    db.definir_executor_ativo(con, colab_id, True)
    monkeypatch.setattr(config, "EXECUTOR_MAX_PASSOS", 2)
    cid = db.criar_comando(con, 1, colab_id, colab_id, "Tarefa que nunca termina")
    db.atualizar_comando(con, cid, status="aprovado")
    monkeypatch.setattr(executor_ia, "chamar_claude", lambda m, w, h: [
        {"type": "tool_use", "id": "t", "name": "computer", "input": {"action": "screenshot"}}])
    t = ctx["token"]
    _api(ctx["cliente"], t, "/api/executor/iniciar", {"comando_id": cid, "tela_w": 800, "tela_h": 600})
    resp, uso = None, None
    for _ in range(4):
        resp = _api(ctx["cliente"], t, "/api/executor/passo",
                    {"comando_id": cid, "screenshot": "A", "tool_use_id": uso}).get_json()
        if resp.get("fim"):
            break
        uso = resp["tool_use_id"]
    assert resp["fim"] and resp["status"] == "falhou"


def test_janela_sensivel_e_bloqueada():
    import executor
    assert executor.janela_sensivel("Nova guia anônima - Google Chrome", "chrome.exe")
    assert executor.janela_sensivel("Cofre", "KeePassXC.exe")
    assert executor.janela_sensivel("Internet Banking - Itaú", "chrome.exe")
    assert not executor.janela_sensivel("Planilha de conciliação - Excel", "excel.exe")


def test_podar_imagens_antigas():
    import executor_ia
    msgs = [{"role": "user", "content": [{"type": "image", "source": {}}]}]
    for i in range(5):
        msgs.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": str(i),
                                                  "content": [{"type": "image", "source": {}}]}]})
    executor_ia._podar_imagens(msgs)
    restantes = sum(1 for m in msgs for b in m["content"]
                    if b["type"] == "image" or (b["type"] == "tool_result" and b["content"][0]["type"] == "image"))
    assert restantes == 3
