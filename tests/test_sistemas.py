"""Identificação do sistema/site usado (sistemas.py)."""
import sistemas


def test_guarda_so_dominio_e_primeiro_trecho():
    assert sistemas.reduzir_endereco("https://docs.google.com/spreadsheets/d/1AbC/edit?x=1") == ("docs.google.com", "spreadsheets")


def test_descarta_numeros_e_codigos_do_caminho():
    assert sistemas.reduzir_endereco("https://crm.empresa.com.br/12345/detalhe") == ("crm.empresa.com.br", None)


def test_site_conhecido_pelo_catalogo():
    assert sistemas.identificar("chrome.exe", "Caixa de entrada - Gmail", "mail.google.com") == ("Gmail", "Chrome")
    assert sistemas.identificar("msedge.exe", "Plan", "docs.google.com", "spreadsheets")[0] == "Google Planilhas"


def test_site_da_empresa_pelo_titulo_da_aba():
    assert sistemas.identificar("chrome.exe", "CRM Vendas - Oportunidades - Google Chrome",
                                "crm.empresademo.com.br", "oportunidades") == ("CRM Vendas", "Chrome")


def test_sem_endereco_fica_o_navegador():
    assert sistemas.identificar("chrome.exe", "Nova guia", None) == ("Chrome", None)


def test_programa_desconhecido_usa_nome_do_produto():
    assert sistemas.identificar("erp_x.exe", "", produto="ERP da Empresa") == ("ERP da Empresa", None)
