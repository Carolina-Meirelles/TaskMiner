"""Processo novo fora do padrão: o TaskMiner pergunta ao gestor se vira processo fixo."""
import re

import simulador
from conftest import entrar


def test_atividade_recente_vira_candidato_e_nao_processo(banco):
    import analise
    simulador.simular("teste", perfil="financeiro", semente=42)
    r = analise.analisar(banco.conectar(), "teste")
    assert len(r["processos"]) == 3
    assert [c["aplicativos"] for c in r["candidatos"]] == [["Explorador de Arquivos", "Excel", "Outlook"]]
    assert r["candidatos"][0]["recente"] is True


def test_ruido_nao_gera_processo_novo(banco):
    import analise
    simulador.simular("teste", perfil="comercial", semente=42)
    assert analise.analisar(banco.conectar(), "teste")["candidatos"] == []


def test_aprovar_e_recusar_na_analise(banco):
    import analise
    simulador.simular("teste", perfil="financeiro", semente=42)
    con = banco.conectar()
    assin = analise.analisar(con, "teste")["candidatos"][0]["assinatura"]
    aprovado = analise.analisar(con, "teste", aprovados={assin})
    assert len(aprovado["processos"]) == 4 and aprovado["candidatos"] == []
    assert any(p["fixado_pelo_gestor"] for p in aprovado["processos"])
    recusado = analise.analisar(con, "teste", rejeitados={assin})
    assert len(recusado["processos"]) == 3 and recusado["candidatos"] == []


def _decidir(cliente, empresa_demo, decisao):
    adm, _, _ = entrar(cliente, "marina@demo.com.br")
    html = adm.get("/processos").get_data(as_text=True)
    assert "Novo processo identificado" in html and "Responder pedidos da auditoria" in html
    csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
    assin = re.search(r'name="assinatura" value="([^"]+)"', html).group(1)
    ana = empresa_demo["ana.souza@demo.com.br"]
    resp = adm.post("/processos/novo/decidir", data={"csrf": csrf, "conta_id": ana["id"], "assinatura": assin,
                                                     "decisao": decisao, "volta": "/processos"})
    return adm, resp, ana


def test_gestor_torna_processo_fixo_e_documentacao_antiga_e_mantida(cliente, empresa_demo, banco):
    adm, resp, ana = _decidir(cliente, empresa_demo, "fixo")
    assert resp.status_code == 302 and "/processo/" in resp.location
    r = banco.carregar_resultado(banco.conectar(), ana["usuario_coleta"])
    nomes = [p["documento"]["nome"] for p in r["processos"]]
    assert "Responder pedidos da auditoria" in nomes and len(nomes) == 4
    assert sum(1 for p in r["processos"] if p["documento"]["gerado_por"] == "Claude") == 3   # não foi refeita
    assert "Novo processo identificado" not in adm.get("/processos").get_data(as_text=True)
    assert "fixado pelo gestor" in adm.get(f"/colaborador/{ana['id']}").get_data(as_text=True)


def test_gestor_marca_como_pontual(cliente, empresa_demo, banco):
    adm, resp, ana = _decidir(cliente, empresa_demo, "pontual")
    assert resp.status_code == 302
    r = banco.carregar_resultado(banco.conectar(), ana["usuario_coleta"])
    assert len(r["processos"]) == 3 and r["candidatos"] == []
    assert "Novo processo identificado" not in adm.get("/processos").get_data(as_text=True)


def test_colaborador_ve_aviso_mas_nao_decide(cliente, empresa_demo):
    ana = empresa_demo["ana.souza@demo.com.br"]
    c, _, _ = entrar(cliente, "ana.souza@demo.com.br")
    html = c.get(f"/colaborador/{ana['id']}").get_data(as_text=True)
    assert "Novo processo identificado" in html and 'name="decisao"' not in html
    csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
    r = c.post("/processos/novo/decidir", data={"csrf": csrf, "conta_id": ana["id"], "assinatura": "x", "decisao": "fixo"})
    assert r.status_code == 403
