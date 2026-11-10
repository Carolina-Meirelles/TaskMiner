"""Gera duas semanas de atividade fictícia, no mesmo formato que o agente grava.

Serve para testar e apresentar o projeto sem esperar 14 dias de coleta real.
Personagem: analista financeira que, além de tarefas soltas (Teams, e-mails, navegação),
executa três processos que o sistema deve descobrir sozinho:
  1. Lançamento de notas fiscais (várias vezes por dia)
  2. Conciliação bancária (todo dia de manhã)
  3. Relatório semanal de despesas (toda sexta-feira)
"""
import json
import os
import random
from datetime import datetime, timedelta

import db
import sistemas

FORNECEDORES = ["Papelaria Central", "Logística Rápida", "TecnoServ", "Limpeza Total", "Gráfica Aurora",
                "Café & Cia", "Energia Sul", "Transportes Lima", "InfoParts", "Segurança Prime",
                "Manutenção Alfa", "Água Pura", "Telecom Brasil", "Office Supply", "Frota Verde"]

EMAIL_USUARIO = "Caixa de Entrada - colaborador@empresa.com.br - Outlook"


class Gerador:
    def __init__(self, usuario):
        self.usuario = usuario
        self.t = 0.0
        self.eventos = []
        self.janela = (None, None)
        self.ritmo = 1.0   # multiplicador de tempo (processos de trabalho são mais lentos que o ruído)

    def _ev(self, tipo, detalhe=None):
        app, titulo = self.janela
        self.eventos.append((self.t, tipo, app, titulo, detalhe))

    def esperar(self, a, b):
        self.t += random.uniform(a, b) * self.ritmo

    def foco(self, app, titulo, permanencia=(3, 10), url=None):
        """url: endereço da página (só nos navegadores). O agente guarda apenas domínio + 1º trecho."""
        self.esperar(0.5, 2)
        self.janela = (app, titulo)
        detalhe = None
        if url:
            dominio, trecho = sistemas.reduzir_endereco(url)
            detalhe = {"dominio": dominio, "trecho": trecho}
        self._ev("foco", detalhe)
        self.esperar(*permanencia)

    def clique(self, tipo, nome, espera=(2, 8)):
        self._ev("clique", {"botao": "left", "tipo_elemento": tipo, "elemento": nome})
        self.esperar(*espera)

    def digitar(self, campo, caracteres, espera=(3, 12)):
        self._ev("digitacao", {"caracteres": caracteres, "campo": campo})
        self.esperar(*espera)

    def atalho(self, combo, acao, espera=(1, 4)):
        self._ev("atalho", {"combinacao": combo, "acao": acao})
        self.esperar(*espera)

    def tecla(self, nome, espera=(1, 3)):
        self._ev("tecla", {"tecla": nome})
        self.esperar(*espera)

    def ocioso(self):
        self._ev("ocioso")

    def ativo(self):
        self._ev("ativo")


# ---------------------------------------------------------------- atividades soltas (ruído)
def ruido(g, n=None):
    opcoes = [
        lambda: (g.foco("ms-teams.exe", "Chat | Microsoft Teams", (10, 60)),
                 g.digitar("Digite uma mensagem", random.randint(20, 120)), g.tecla("Enter")),
        lambda: (g.foco("outlook.exe", EMAIL_USUARIO, (20, 90)),
                 g.clique("ListItem", f"Comunicado interno {random.randint(1, 99)}")),
        lambda: g.foco("chrome.exe", "Notícias do dia - Portal de Notícias - Google Chrome", (30, 180), url="https://portaldenoticias.exemplo.com.br/ultimas"),
        lambda: (g.foco("chrome.exe", "Início - Portal do Colaborador - Google Chrome", (20, 90), url="https://colaborador.empresademo.com.br/inicio"),
                 g.clique("Hyperlink", random.choice(["Holerite", "Benefícios", "Férias"]))),
        lambda: g.foco("explorer.exe", "Documentos", (5, 30)),
        lambda: g.foco("chrome.exe", "WhatsApp - Google Chrome", (15, 90), url="https://web.whatsapp.com/"),
        lambda: g.foco("chrome.exe", "Meu Drive - Google Drive - Google Chrome", (10, 60), url="https://drive.google.com/drive/my-drive"),
        lambda: g.foco("ms-teams.exe", "Calendário | Microsoft Teams", (10, 40)),
        lambda: (g.foco("chrome.exe", "Previsão do tempo - Google Chrome", (10, 40), url="https://tempo.exemplo.com.br/sao-paulo")),
    ]
    for _ in range(n or random.randint(1, 2)):
        random.choice(opcoes)()


def reuniao(g):
    g.foco("ms-teams.exe", "Reunião de alinhamento | Microsoft Teams", (1500, 3300))


# ---------------------------------------------------------------- processo 1: notas fiscais
def nota_fiscal(g):
    g.ritmo = random.uniform(2.5, 4)
    n, forn = random.randint(1000, 99999), random.choice(FORNECEDORES)
    g.foco("outlook.exe", EMAIL_USUARIO, (5, 25))
    g.clique("ListItem", f"NF {n} - {forn}")
    g.clique("Button", "Salvar todos os anexos", (4, 12))

    g.foco("acrord32.exe", f"NF_{n}.pdf - Adobe Acrobat Reader (64-bit)", (10, 40))
    g.atalho("Ctrl+F", "Localizar")
    g.digitar("Localizar", random.randint(5, 10))
    g.atalho("Ctrl+C", "Copiar")

    if random.random() < 0.1:  # às vezes é interrompida no meio
        r, g.ritmo = g.ritmo, 1.0
        ruido(g, 1)
        g.ritmo = r

    g.foco("saplogon.exe", "Registrar fatura recebida: Empresa 1000", (5, 15))
    g.digitar("Data da fatura", 10)
    g.tecla("Tab")
    g.digitar("Referência", random.randint(5, 9))
    g.digitar("Montante", random.randint(4, 9))
    if random.random() < 0.8:
        g.clique("ComboBox", "Código do imposto")
    g.clique("Button", "Simular", (5, 20))
    if random.random() < 0.2:      # SAP lento de vez em quando: espera o "Simular" responder
        g.esperar(60, 180)
    g.clique("Button", "Gravar", (3, 8))

    g.foco("excel.exe", "Controle_NFs_2026.xlsx - Excel", (5, 15))
    g.digitar("Célula", random.randint(30, 80), (10, 40))
    g.atalho("Ctrl+S", "Salvar")
    g.ritmo = 1.0


# ---------------------------------------------------------------- processo 2: conciliação
def conciliacao(g, data):
    g.ritmo = random.uniform(2.5, 4)
    g.foco("chrome.exe", "Banco Empresas - Extrato - Google Chrome", (15, 40), url="https://netempresas.bancoexemplo.com.br/extrato?conta=12345")
    g.clique("Hyperlink", "Extrato por período")
    g.clique("Button", "Exportar OFX", (5, 15))

    g.foco("explorer.exe", "Downloads", (5, 15))
    g.atalho("Ctrl+X", "Recortar")
    g.foco("explorer.exe", "Conciliação Bancária", (3, 10))
    g.atalho("Ctrl+V", "Colar")

    g.foco("excel.exe", "Conciliacao_Bancaria.xlsm - Excel", (10, 30))
    g.clique("Button", "Importar extrato", (10, 30))
    g.clique("Button", "Conciliar", (60, 240))
    g.digitar("Observações", random.randint(20, 150))
    g.atalho("Ctrl+S", "Salvar")

    g.foco("outlook.exe", f"Conciliação bancária {data:%d/%m} - Mensagem (HTML)", (5, 15))
    g.digitar("Para", random.randint(15, 25))
    g.digitar("Corpo da mensagem", random.randint(60, 200), (20, 60))
    g.clique("Button", "Enviar")
    g.ritmo = 1.0


# ---------------------------------------------------------------- processo 3: relatório semanal
def relatorio_semanal(g, semana):
    g.ritmo = random.uniform(2.5, 4)
    g.foco("saplogon.exe", "Relatório de despesas por centro de custo", (10, 30))
    g.digitar("Período", 21)
    g.clique("Button", "Executar", (20, 60))
    g.clique("Button", "Exportar para planilha", (5, 15))

    g.foco("excel.exe", f"Despesas_Semana_{semana}.xlsx - Excel", (20, 60))
    g.clique("MenuItem", "Atualizar tudo", (5, 15))
    g.clique("Button", "Tabela Dinâmica", (60, 240))
    g.atalho("Ctrl+C", "Copiar")

    g.foco("powerpnt.exe", "Fechamento_Semanal.pptx - PowerPoint", (20, 60))
    g.atalho("Ctrl+V", "Colar", (30, 120))
    g.digitar("Título", random.randint(20, 50))
    g.atalho("Ctrl+S", "Salvar")

    g.foco("outlook.exe", "Relatório semanal de despesas - Mensagem (HTML)", (10, 30))
    g.digitar("Para", 40)
    g.clique("Button", "Anexar arquivo", (5, 15))
    g.digitar("Corpo da mensagem", random.randint(80, 200), (20, 60))
    g.clique("Button", "Enviar")
    g.ritmo = 1.0


# ---------------------------------------------------------------- atividade nova (fora do padrão)
def auditoria(g, data):
    """Começa só nos últimos dias da coleta: a analista passa a responder a auditoria externa."""
    g.ritmo = random.uniform(2.5, 4)
    g.foco("explorer.exe", "Comprovantes 2026", (10, 30))
    g.clique("ListItem", f"Comprovante_{random.randint(1000, 9999)}.pdf")
    g.atalho("Ctrl+C", "Copiar")
    g.foco("excel.exe", "Auditoria_Respostas.xlsx - Excel", (20, 60))
    g.digitar("Célula", random.randint(30, 90), (20, 60))
    g.atalho("Ctrl+S", "Salvar")
    g.foco("outlook.exe", "Auditoria - documentos solicitados - Mensagem (HTML)", (10, 30))
    g.clique("Button", "Anexar arquivo", (5, 15))
    g.digitar("Corpo da mensagem", random.randint(80, 200), (20, 60))
    g.clique("Button", "Enviar")
    g.ritmo = 1.0


# ---------------------------------------------------------------- perfil comercial
CLIENTES = ["Mercado Bom Preço", "Construtora Horizonte", "Farmácia Vida", "Hotel Atlântico", "Escola Saber",
            "Padaria Trigo de Ouro", "Clínica Bem Estar", "Auto Peças Rota", "Restaurante Sabor", "Loja Estilo"]


def pedido_venda(g, data=None):
    g.ritmo = random.uniform(2.5, 4)
    n, cli = random.randint(10000, 99999), random.choice(CLIENTES)
    g.foco("outlook.exe", EMAIL_USUARIO, (5, 20))
    g.clique("ListItem", f"Pedido {n} - {cli}")
    g.foco("chrome.exe", "CRM Vendas - Oportunidades - Google Chrome", (10, 30), url="https://crm.empresademo.com.br/oportunidades/lista")
    g.digitar("Buscar cliente", random.randint(6, 20))
    g.tecla("Enter")
    g.clique("Button", "Converter em pedido", (5, 15))
    if random.random() < 0.25:     # CRM às vezes demora para gerar o pedido
        g.esperar(40, 120)
    g.foco("saplogon.exe", "Criar ordem do cliente: Síntese", (5, 15))
    g.digitar("Emissor da ordem", 6)
    g.digitar("Material", random.randint(6, 10))
    g.digitar("Quantidade", random.randint(1, 4))
    g.tecla("Enter")
    if random.random() < 0.7:
        g.clique("Button", "Condições", (5, 20))
    g.clique("Button", "Gravar", (3, 8))
    g.foco("outlook.exe", f"Confirmação do pedido {n} - Mensagem (HTML)", (5, 15))
    g.digitar("Para", random.randint(15, 30))
    g.digitar("Corpo da mensagem", random.randint(80, 200), (15, 45))
    g.clique("Button", "Enviar")
    g.ritmo = 1.0


def previsao_vendas(g, data=None):
    g.ritmo = random.uniform(2.5, 4)
    g.foco("chrome.exe", "CRM Vendas - Relatórios - Google Chrome", (10, 30), url="https://crm.empresademo.com.br/relatorios/funil")
    g.clique("Hyperlink", "Funil por etapa", (10, 30))
    g.clique("Button", "Exportar para Excel", (5, 15))
    g.foco("excel.exe", "Forecast_Comercial.xlsx - Excel", (20, 60))
    g.clique("MenuItem", "Atualizar tudo", (10, 30))
    g.digitar("Célula", random.randint(20, 60), (20, 60))
    g.atalho("Ctrl+S", "Salvar")
    g.foco("ms-teams.exe", "Equipe Comercial | Microsoft Teams", (10, 30))
    g.digitar("Digite uma mensagem", random.randint(40, 140))
    g.clique("Button", "Anexar")
    g.tecla("Enter")
    g.ritmo = 1.0


def resultado_metas(g, data):
    g.ritmo = random.uniform(2.5, 4)
    g.foco("chrome.exe", "CRM Vendas - Painel de metas - Google Chrome", (20, 60), url="https://crm.empresademo.com.br/metas")
    g.clique("Button", "Filtrar semana anterior", (10, 30))
    g.clique("Button", "Exportar para Excel", (5, 15))
    g.foco("excel.exe", f"Metas_Semana_{data.isocalendar().week}.xlsx - Excel", (20, 60))
    g.clique("Button", "Gráfico Dinâmico", (40, 120))
    g.atalho("Ctrl+C", "Copiar")
    g.foco("powerpnt.exe", "Reuniao_Comercial.pptx - PowerPoint", (20, 60))
    g.atalho("Ctrl+V", "Colar", (30, 90))
    g.atalho("Ctrl+S", "Salvar")
    g.foco("outlook.exe", "Resultado semanal de metas - Mensagem (HTML)", (10, 30))
    g.digitar("Para", 35)
    g.clique("Button", "Anexar arquivo", (5, 15))
    g.clique("Button", "Enviar")
    g.ritmo = 1.0


PERFIS = {
    # abertura: processo de todo início de dia; repetitivo: várias vezes por dia;
    # semanal: (dia da semana 0=segunda, hora, processo)
    "financeiro": {"abertura": lambda g, d: conciliacao(g, d), "repetitivo": lambda g, d: nota_fiscal(g),
                   "novo": (3, 10, auditoria),   # nos últimos 3 dias úteis, por volta das 10h
                   "semanal": (4, 15, lambda g, d: relatorio_semanal(g, d.isocalendar().week)),
                   "manha": (3, 5), "tarde": (4, 6)},
    "comercial": {"abertura": previsao_vendas, "repetitivo": pedido_venda,
                  "semanal": (0, 14, resultado_metas), "manha": (2, 4), "tarde": (3, 5)},
}


# ---------------------------------------------------------------- um dia de trabalho
def dia_de_trabalho(g, data, perfil, faltam_dias=99):
    def ate(h, m=0):
        return datetime(data.year, data.month, data.day, h, m).timestamp()

    dia_semanal, hora_semanal, semanal = perfil["semanal"]
    g.t = ate(8, 30) + random.uniform(0, 900)
    ruido(g, 2)
    perfil["abertura"](g, data)
    ruido(g)

    reunioes = random.choice([0, 1, 1, 2])
    manha = random.randint(*perfil["manha"])
    dias_novo, hora_novo, novo = perfil.get("novo", (0, 0, None))
    fez_novo = not novo or faltam_dias > dias_novo
    while g.t < ate(11, 50):
        if not fez_novo and g.t > ate(hora_novo):
            novo(g, data)
            fez_novo = True
        elif manha > 0 and random.random() < 0.6:
            perfil["repetitivo"](g, data)
            manha -= 1
        elif reunioes > 0 and random.random() < 0.08:
            reuniao(g)
            reunioes -= 1
        else:
            ruido(g)
            g.esperar(30, 240)

    g.ocioso()
    g.t = ate(13) + random.uniform(0, 900)
    g.ativo()

    tarde = random.randint(*perfil["tarde"])
    fez_semanal = data.weekday() != dia_semanal
    while g.t < ate(17, 20):
        if not fez_semanal and g.t > ate(hora_semanal):
            semanal(g, data)
            fez_semanal = True
        elif tarde > 0 and random.random() < 0.6:
            perfil["repetitivo"](g, data)
            tarde -= 1
        elif reunioes > 0 and random.random() < 0.08:
            reuniao(g)
            reunioes -= 1
        else:
            ruido(g)
            g.esperar(30, 240)
    g.ocioso()


def simular(usuario="ana.souza", dias=14, semente=42, perfil="financeiro"):
    random.seed(semente)
    con = db.conectar()
    con.execute("DELETE FROM eventos WHERE usuario = ?", (usuario,))
    con.execute("DELETE FROM resultados WHERE usuario = ?", (usuario,))

    g = Gerador(usuario)
    hoje = datetime.now().date()
    datas = [hoje - timedelta(days=k) for k in range(dias, 0, -1)]
    uteis = [d for d in datas if d.weekday() < 5]
    for k, data in enumerate(uteis):
        dia_de_trabalho(g, data, PERFIS[perfil], faltam_dias=len(uteis) - k)

    con.executemany(
        "INSERT INTO eventos (ts, usuario, tipo, app, titulo, detalhe) VALUES (?, ?, ?, ?, ?, ?)",
        [(ts, usuario, tipo, app, titulo, None if det is None else json.dumps(det, ensure_ascii=False))
         for ts, tipo, app, titulo, det in g.eventos],
    )
    con.commit()
    db.set_meta(con, f"inicio_coleta:{usuario}", datetime.combine(datas[0], datetime.min.time()).timestamp())
    con.close()
    return len(g.eventos), len(uteis)


# ---------------------------------------------------------------- empresa de demonstração
SENHA_DEMO = os.environ.get("DEMO_SENHA", "demo12345")   # senha fictícia, só para as contas de demonstração
EQUIPE_DEMO = [
    # nome, e-mail, função, área, papel, perfil simulado (None = ainda sem coleta)
    ("Marina Costa", "marina@demo.com.br", "Gerente de Operações", "Diretoria", "admin", None),
    ("Ana Souza", "ana.souza@demo.com.br", "Analista de Contas a Pagar", "Financeiro", "colaborador", "financeiro"),
    ("Bruno Lima", "bruno.lima@demo.com.br", "Executivo de Vendas", "Comercial", "colaborador", "comercial"),
    ("Carla Mendes", "carla.mendes@demo.com.br", "Analista de RH", "Recursos Humanos", "colaborador", None),
]


def criar_empresa_demo():
    """Cria a 'Empresa Demo' com 4 contas; Ana e Bruno com 2 semanas de coleta simulada."""
    import secrets
    from werkzeug.security import generate_password_hash

    con = db.conectar()
    existente = db.conta_por_email(con, EQUIPE_DEMO[0][1])
    if existente:
        empresa_id = existente["empresa_id"]
    else:
        empresa_id = db.criar_empresa(con, "Empresa Demo Ltda.", "12.345.678/0001-90")
    contas = []
    for k, (nome, email, funcao, area, papel, perfil) in enumerate(EQUIPE_DEMO):
        c = db.conta_por_email(con, email)
        if not c:
            db.criar_conta(con, empresa_id, nome, email, generate_password_hash(SENHA_DEMO), papel=papel,
                           funcao=funcao, area=area, token_coleta=secrets.token_urlsafe(24))
            c = db.conta_por_email(con, email)
        contas.append((c, perfil))
    con.close()
    for k, (c, perfil) in enumerate(contas):
        if perfil:
            simular(c["usuario_coleta"], perfil=perfil, semente=42 + k)
    return [c for c, _ in contas]
