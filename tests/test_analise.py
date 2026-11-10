"""Algoritmo de task mining: encontra os processos escondidos no meio do ruído."""
import pytest

import simulador


ESPERADO = {
    "financeiro": [["Outlook", "Adobe Acrobat", "SAP", "Excel"],
                   ["Banco Empresas", "Explorador de Arquivos", "Excel", "Outlook"],
                   ["SAP", "Excel", "PowerPoint", "Outlook"]],
    "comercial": [["Outlook", "CRM Vendas", "SAP", "Outlook"],
                  ["CRM Vendas", "Excel", "Teams"],
                  ["CRM Vendas", "Excel", "PowerPoint", "Outlook"]],
}


@pytest.mark.parametrize("perfil", ["financeiro", "comercial"])
@pytest.mark.parametrize("semente", [1, 7, 42])
def test_encontra_exatamente_os_tres_processos(banco, perfil, semente):
    import analise
    simulador.simular("teste", perfil=perfil, semente=semente)
    r = analise.analisar(banco.conectar(), "teste")
    assert sorted(p["aplicativos"] for p in r["processos"]) == sorted(ESPERADO[perfil])


def test_frequencias(banco):
    import analise
    simulador.simular("teste", perfil="financeiro", semente=42)
    r = analise.analisar(banco.conectar(), "teste")
    tipos = {tuple(p["aplicativos"]): p["tipo_frequencia"] for p in r["processos"]}
    assert tipos[("Outlook", "Adobe Acrobat", "SAP", "Excel")] == "diaria"
    assert tipos[("SAP", "Excel", "PowerPoint", "Outlook")] == "semanal"


def test_gargalo_no_sap_das_notas_fiscais(banco):
    import analise
    simulador.simular("teste", perfil="financeiro", semente=42)
    r = analise.analisar(banco.conectar(), "teste")
    nf = next(p for p in r["processos"] if p["aplicativos"][0] == "Outlook" and "Adobe Acrobat" in p["aplicativos"])
    etapas = {g["etapa"] for g in nf["gargalos"]}
    assert 2 in etapas          # etapa 3 (SAP), índice 2


def test_sem_eventos_avisa(banco):
    import analise
    with pytest.raises(ValueError):
        analise.analisar(banco.conectar(), "ninguem")
