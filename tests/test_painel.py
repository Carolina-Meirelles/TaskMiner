"""Painel web: login, permissões e telas principais."""
from conftest import entrar


def test_admin_cai_na_tela_de_processos(cliente):
    c, _, resp = entrar(cliente, "marina@demo.com.br")
    assert resp.status_code == 302
    r = c.get("/", follow_redirects=True)
    assert "Processos da empresa" in r.get_data(as_text=True)


def test_senha_errada(cliente):
    _, _, resp = entrar(cliente, "marina@demo.com.br", "errada123")
    assert "incorretos" in resp.get_data(as_text=True)


def test_formulario_sem_csrf_e_recusado(cliente):
    c = cliente()
    assert c.post("/entrar", data={"email": "marina@demo.com.br", "senha": "demo12345"}).status_code == 400


def test_colaborador_so_ve_o_que_e_dele(cliente, empresa_demo):
    c, _, _ = entrar(cliente, "ana.souza@demo.com.br")
    ana, bruno = empresa_demo["ana.souza@demo.com.br"], empresa_demo["bruno.lima@demo.com.br"]
    assert c.get(f"/colaborador/{ana['id']}").status_code == 200
    assert c.get(f"/colaborador/{bruno['id']}").status_code == 403
    assert c.get("/processos").status_code == 403
    assert c.get("/melhorias").status_code == 403


def test_todas_as_telas_do_admin_abrem(cliente, empresa_demo):
    c, _, _ = entrar(cliente, "marina@demo.com.br")
    ana = empresa_demo["ana.souza@demo.com.br"]["id"]
    for url in ["/processos", "/empresa", "/empresa/graficos", "/melhorias", "/colaboradores",
                f"/colaborador/{ana}", f"/colaborador/{ana}/processo/p1", f"/colaborador/{ana}/graficos",
                f"/colaborador/{ana}/melhorias", "/empresa/exportar", "/minha-coleta"]:
        assert c.get(url).status_code == 200, url


def test_status_de_melhoria_so_admin_altera(cliente, empresa_demo):
    import re
    adm, _, _ = entrar(cliente, "marina@demo.com.br")
    html = adm.get("/melhorias").get_data(as_text=True)
    csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)       # o login gera um código novo
    chave = re.search(r'name="chave" value="([^"]+)"', html).group(1)
    assert adm.post("/melhorias/status", data={"csrf": csrf, "chave": chave, "status": "andamento"}).status_code == 302
    assert 'data-st="andamento"' in adm.get("/melhorias").get_data(as_text=True)
    ana, _, _ = entrar(cliente, "ana.souza@demo.com.br")
    csrf2 = re.search(r'name="csrf" value="([^"]+)"', ana.get("/minha-conta").get_data(as_text=True)).group(1)
    assert ana.post("/melhorias/status", data={"csrf": csrf2, "chave": chave, "status": "concluida"}).status_code == 403


def test_api_do_agente_recusa_codigo_invalido(cliente):
    c = cliente()
    r = c.post("/api/eventos", json={"eventos": []}, headers={"Authorization": "Bearer invalido"})
    assert r.status_code == 401
