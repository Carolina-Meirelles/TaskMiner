"""Identifica o SISTEMA que o colaborador está usando, em vez de só o programa.

- Navegadores (Chrome, Edge, Firefox...): pelo endereço do site (só o domínio e o 1º trecho do
  caminho, nunca o endereço completo) e, se o site não for conhecido, pelo título da aba.
- Programas instalados: pelo nome conhecido do executável ou pelo nome do produto gravado no
  próprio arquivo .exe (ex.: smartclient.exe -> "TOTVS SmartClient").

Para ensinar um sistema novo à empresa, basta acrescentar uma linha em SITES ou PROGRAMAS.
"""
import re
from urllib.parse import urlsplit

NAVEGADORES = {
    "chrome.exe": "Chrome", "msedge.exe": "Edge", "firefox.exe": "Firefox", "brave.exe": "Brave",
    "opera.exe": "Opera", "iexplore.exe": "Internet Explorer", "vivaldi.exe": "Vivaldi",
}

PROGRAMAS = {
    "excel.exe": "Excel", "winword.exe": "Word", "powerpnt.exe": "PowerPoint", "msaccess.exe": "Access",
    "outlook.exe": "Outlook", "olk.exe": "Outlook", "onenote.exe": "OneNote",
    "ms-teams.exe": "Teams", "teams.exe": "Teams", "slack.exe": "Slack", "zoom.exe": "Zoom",
    "whatsapp.exe": "WhatsApp", "explorer.exe": "Explorador de Arquivos",
    "acrord32.exe": "Adobe Acrobat", "acrobat.exe": "Adobe Acrobat",
    "saplogon.exe": "SAP", "sapgui.exe": "SAP", "nwbc.exe": "SAP Business Client",
    "smartclient.exe": "TOTVS Protheus", "totvs.exe": "TOTVS", "rm.exe": "TOTVS RM",
    "sankhya.exe": "Sankhya", "senior.exe": "Senior", "dominio.exe": "Domínio Sistemas",
    "notepad.exe": "Bloco de Notas", "notepad++.exe": "Notepad++", "code.exe": "VS Code",
    "anydesk.exe": "AnyDesk", "mstsc.exe": "Área de Trabalho Remota", "wfica32.exe": "Citrix",
    "powerbi.exe": "Power BI", "pbidesktop.exe": "Power BI", "calc.exe": "Calculadora",
}

# (padrão do domínio, trecho inicial do caminho ou None, nome do sistema). A primeira que casar vale.
SITES = [
    (r"(^|\.)mail\.google\.com$", None, "Gmail"),
    (r"(^|\.)docs\.google\.com$", "spreadsheets", "Google Planilhas"),
    (r"(^|\.)docs\.google\.com$", "document", "Google Docs"),
    (r"(^|\.)docs\.google\.com$", "presentation", "Google Apresentações"),
    (r"(^|\.)docs\.google\.com$", "forms", "Google Forms"),
    (r"(^|\.)drive\.google\.com$", None, "Google Drive"),
    (r"(^|\.)calendar\.google\.com$", None, "Google Agenda"),
    (r"(^|\.)meet\.google\.com$", None, "Google Meet"),
    (r"(^|\.)lookerstudio\.google\.com$", None, "Looker Studio"),
    (r"(^|\.)outlook\.(office|office365|live)\.com$", None, "Outlook (web)"),
    (r"(^|\.)teams\.(microsoft|live)\.com$", None, "Teams (web)"),
    (r"\.sharepoint\.com$", None, "SharePoint"),
    (r"(^|\.)onedrive\.live\.com$", None, "OneDrive"),
    (r"(^|\.)(www\.)?office\.com$", None, "Microsoft 365"),
    (r"(^|\.)app\.powerbi\.com$", None, "Power BI"),
    (r"(^|\.)web\.whatsapp\.com$", None, "WhatsApp Web"),
    (r"\.(salesforce|force|lightning\.force)\.com$", None, "Salesforce"),
    (r"(^|\.)app\.hubspot\.com$", None, "HubSpot"),
    (r"\.pipedrive\.com$", None, "Pipedrive"),
    (r"\.rdstation\.com(\.br)?$", None, "RD Station"),
    (r"\.zendesk\.com$", None, "Zendesk"),
    (r"\.freshdesk\.com$", None, "Freshdesk"),
    (r"\.atlassian\.net$", "wiki", "Confluence"),
    (r"\.atlassian\.net$", None, "Jira"),
    (r"(^|\.)trello\.com$", None, "Trello"),
    (r"(^|\.)app\.asana\.com$", None, "Asana"),
    (r"\.monday\.com$", None, "monday.com"),
    (r"(^|\.)(www\.)?notion\.so$", None, "Notion"),
    (r"(^|\.)app\.clickup\.com$", None, "ClickUp"),
    (r"\.bling\.com\.br$", None, "Bling"),
    (r"\.omie\.com\.br$", None, "Omie"),
    (r"\.contaazul\.com$", None, "Conta Azul"),
    (r"(\.|^)tiny\.com\.br$|\.tinyerp\.com\.br$", None, "Tiny ERP"),
    (r"\.totvs\.(com|app|com\.br)$|\.fluig\.com$", None, "TOTVS (web)"),
    (r"\.(ondemand|s4hana\.ondemand|sapbydesign|successfactors)\.com$|(^|\.)sap\.", None, "SAP (web)"),
    (r"\.oraclecloud\.com$", None, "Oracle Cloud"),
    (r"\.sankhya\.com\.br$", None, "Sankhya (web)"),
    (r"(^|\.)nfe\.fazenda\.gov\.br$", None, "Portal da NF-e"),
    (r"(^|\.)cav\.receita\.fazenda\.gov\.br$", None, "e-CAC (Receita Federal)"),
    (r"(^|\.)(www\.)?esocial\.gov\.br$|login\.esocial\.gov\.br$", None, "eSocial"),
    (r"(^|\.)sefaz\.|\.sefaz\.", None, "SEFAZ"),
    (r"(^|\.)nfse\.gov\.br$|\.nfse\.", None, "NFS-e"),
    (r"\.gov\.br$", None, "Portal do governo (gov.br)"),
    (r"(^|\.)bb\.com\.br$", None, "Banco do Brasil"),
    (r"(^|\.)itau\.com\.br$", None, "Itaú"),
    (r"bradesco", None, "Bradesco"),
    (r"(^|\.)santander\.com\.br$", None, "Santander"),
    (r"(^|\.)caixa\.gov\.br$", None, "Caixa"),
    (r"sicoob", None, "Sicoob"),
    (r"sicredi", None, "Sicredi"),
    (r"(^|\.)(bancointer\.com\.br|inter\.co)$", None, "Banco Inter"),
    (r"(^|\.)mercadolivre\.com\.br$|mercadolibre", None, "Mercado Livre"),
    (r"(^|\.)linkedin\.com$", None, "LinkedIn"),
    (r"(^|\.)youtube\.com$", None, "YouTube"),
    (r"(^|\.)canva\.com$", None, "Canva"),
    (r"(^|\.)chatgpt\.com$|(^|\.)chat\.openai\.com$", None, "ChatGPT"),
    (r"(^|\.)claude\.ai$", None, "Claude"),
    (r"(^|\.)github\.com$", None, "GitHub"),
]

_SUFIXOS_NAVEGADOR = re.compile(
    r"\s+[-–—|]\s+(Google Chrome|Microsoft​? Edge|Mozilla Firefox|Brave|Opera|Vivaldi)\s*$", re.I)
_SEP = re.compile(r"\s+[-–—|]\s+")


def reduzir_endereco(url):
    """Guarda só o domínio e o 1º trecho do caminho: https://docs.google.com/spreadsheets/d/abc?x=1
    -> ('docs.google.com', 'spreadsheets'). Números e códigos longos do caminho são descartados."""
    if not url:
        return None, None
    if "://" not in url:
        url = "https://" + url
    try:
        partes = urlsplit(url.strip())
    except ValueError:
        return None, None
    dominio = (partes.hostname or "").lower().removeprefix("www.")
    if not dominio or "." not in dominio and dominio != "localhost":
        return None, None
    trecho = next((t for t in partes.path.split("/") if t), "")
    if not re.fullmatch(r"[A-Za-z][A-Za-z_-]{1,30}", trecho):   # ignora ids, números, e-mails
        trecho = ""
    return dominio, trecho.lower() or None


def _nome_por_titulo(dominio, titulo):
    """Site desconhecido: usa a parte do título da aba que corresponde ao domínio
    (ex.: crm.empresa.com.br + "CRM Vendas - Oportunidades" -> "CRM Vendas")."""
    titulo = _SUFIXOS_NAVEGADOR.sub("", titulo or "").strip()
    partes = [p.strip() for p in _SEP.split(titulo) if p.strip()]
    rotulos = [r for r in (dominio or "").split(".") if r not in ("com", "br", "net", "org", "app", "io", "co", "www")]
    for parte in partes:
        compacto = re.sub(r"[^a-z0-9]", "", parte.lower())
        for r in rotulos:
            r2 = re.sub(r"[^a-z0-9]", "", r)
            if len(r2) >= 3 and (r2 in compacto or compacto.startswith(r2[:5]) or r2.startswith(compacto[:5])):
                return parte
    if len(partes) >= 2:
        return partes[-1] if len(partes[-1]) <= 30 else partes[0]
    if rotulos:
        return rotulos[0].replace("-", " ").title()
    return partes[0] if partes else None


def identificar(exe, titulo="", dominio=None, trecho=None, produto=None):
    """Retorna (sistema, navegador): ex. ('CRM Vendas', 'Chrome') ou ('Excel', None)."""
    exe = (exe or "").lower()
    navegador = NAVEGADORES.get(exe)
    if navegador:
        if dominio:
            for padrao, caminho, nome in SITES:
                if re.search(padrao, dominio) and (caminho is None or caminho == trecho):
                    return nome, navegador
            nome = _nome_por_titulo(dominio, titulo)
            if nome:
                return nome, navegador
        return navegador, None        # sem endereço (ex.: aba nova): fica o navegador
    if exe in PROGRAMAS:
        return PROGRAMAS[exe], None
    if produto:
        return produto, None
    return exe.removesuffix(".exe").replace("_", " ").title() or "Desconhecido", None
