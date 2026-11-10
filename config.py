"""Configurações do TaskMiner. Ajuste aqui sem precisar mexer no resto do código."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Carrega variáveis de um arquivo .env, se existir (ex.: ANTHROPIC_API_KEY=...)
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

DB_PATH = Path(os.environ.get("TASKMINING_DB", BASE_DIR / "dados" / "taskmining.db"))

# ---------------- Coleta ----------------
DIAS_DE_COLETA = 14            # duração total da observação
INTERVALO_VERIFICACAO = 0.5    # segundos entre leituras da janela ativa
LIMITE_OCIOSO = 120            # segundos sem mouse/teclado = colaborador ausente
CAPTURAR_ELEMENTOS_CLICADOS = True  # usa UI Automation para saber o nome do botão/campo clicado

# Identificação de sites: nos navegadores, guarda só o domínio do site (ex.: crm.empresa.com.br)
CAPTURAR_SITES = True
DOMINIOS_IGNORADOS = set()      # ex.: {"meubanco.com.br"} para nunca registrar um site
NOMES_BARRA_ENDERECO = [        # nome do campo de endereço em cada navegador/idioma
    "Barra de endereço e de pesquisa", "Address and search bar",          # Chrome, Brave
    "Barra de endereços e de pesquisa", "Pesquisar ou digitar endereço web",
    "Search or enter web address",                                          # Edge
    "Pesquise com o Google ou digite um endereço", "Search with Google or enter address",  # Firefox
]

# Aplicativos que NUNCA são observados (gerenciadores de senha, tela de bloqueio...)
APPS_IGNORADOS = {
    "keepass.exe", "keepassxc.exe", "1password.exe", "bitwarden.exe",
    "lockapp.exe", "logonui.exe",
}
# Se o título da janela contiver um destes termos, o título é ocultado e os cliques não são detalhados
TERMOS_SENSIVEIS_TITULO = [
    "senha", "password", "inprivate", "anônima", "anonima", "incognito", "privada",
]

# ---------------- Análise ----------------
DURACAO_MINIMA_SEGMENTO = 3    # janelas abertas por menos tempo (e sem ações) são ruído
TAMANHO_MIN_PADRAO = 3         # um processo tem pelo menos 3 telas/etapas
TAMANHO_MAX_PADRAO = 8
MIN_OCORRENCIAS = 4            # processo frequente: repetido 4+ vezes...
MIN_DIAS = 3                   # ...em pelo menos 3 dias diferentes
TAMANHO_LONGO = 4              # sequências longas (4+ etapas)...
MIN_OCORRENCIAS_LONGO = 2      # ...bastam 2 repetições (pega tarefas semanais)
COESAO_MIN = 0.5               # cada etapa precisa levar à próxima em 50%+ das vezes (filtra ruído)
SUPORTE_MIN_ACAO = 0.5        # ação entra no passo a passo se aparece em 50%+ das execuções

# Processos novos (fora do padrão): o TaskMiner pergunta ao gestor se viram processo fixo
NOVO_MIN_OCORRENCIAS = 2       # a sequência apareceu pelo menos 2 vezes, em 2 dias diferentes
NOVO_MAX_SUGESTOES = 5

# Gargalos
GARGALO_FATIA_ETAPA = 0.35     # uma etapa com 35%+ do tempo do processo
GARGALO_VARIACAO = 2.0         # 1 em 10 execuções leva 2x+ o tempo normal (p90 / mediana)
GARGALO_INTERRUPCOES = 0.10    # processo interrompido no meio em 10%+ das vezes
GARGALO_CAMPOS_MANUAIS = 3     # 3+ campos digitados à mão na mesma etapa

# ---------------- Painel web ----------------
SECRET_KEY = os.environ.get("TASKMINING_SECRET_KEY", "")   # vazio = gera uma e guarda em dados/.chave_secreta

# ---------------- IA (Claude) ----------------
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODELO = os.environ.get("CLAUDE_MODELO", "claude-sonnet-5-5")

# ---------------- Executor (IA que opera o computador do colaborador) ----------------
EXECUTOR_MAX_PASSOS = int(os.environ.get("EXECUTOR_MAX_PASSOS", "40"))   # trava de segurança por comando
EXECUTOR_TELA_MAX = 1280                  # lado maior da captura enviada ao Claude (reduz custo e latência)
EXECUTOR_PAUSA_ACAO = 0.8                 # segundos de espera depois de cada ação, antes da nova captura
EXECUTOR_SCREENSHOTS_NO_CONTEXTO = 3      # só as últimas N capturas ficam na conversa
# Versão da ferramenta de uso de computador da API. Se a Anthropic lançar uma nova, troque aqui
# (consulte https://docs.claude.com -> Tools -> Computer use).
EXECUTOR_TOOL_TYPE = os.environ.get("EXECUTOR_TOOL_TYPE", "computer_20250124")
EXECUTOR_BETA = os.environ.get("EXECUTOR_BETA", "computer-use-2025-01-24")
