"""Acesso ao banco SQLite onde ficam os eventos coletados e os resultados da análise."""
import json
import sqlite3
import time
from pathlib import Path

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS eventos (
    id      INTEGER PRIMARY KEY,
    ts      REAL NOT NULL,          -- timestamp (segundos)
    usuario TEXT NOT NULL,
    tipo    TEXT NOT NULL,          -- foco | clique | digitacao | atalho | tecla | ocioso | ativo | pausa | retomada
    app     TEXT,                   -- executável (ex.: excel.exe)
    titulo  TEXT,                   -- título da janela (já mascarado)
    detalhe TEXT                    -- JSON com dados extras
);
CREATE INDEX IF NOT EXISTS idx_eventos_usuario_ts ON eventos(usuario, ts);

CREATE TABLE IF NOT EXISTS consentimento (
    usuario TEXT NOT NULL,
    ts      REAL NOT NULL,
    texto   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS resultados (
    usuario TEXT PRIMARY KEY,
    ts      REAL NOT NULL,
    dados   TEXT NOT NULL           -- JSON com processos, estatísticas e documentação
);

-- ---------------- contas (painel web) ----------------
CREATE TABLE IF NOT EXISTS empresas (
    id        INTEGER PRIMARY KEY,
    nome      TEXT NOT NULL,
    cnpj      TEXT,
    criado_em REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS contas (
    id             INTEGER PRIMARY KEY,
    empresa_id     INTEGER NOT NULL REFERENCES empresas(id),
    nome           TEXT NOT NULL,
    email          TEXT NOT NULL UNIQUE,
    senha_hash     TEXT NOT NULL,
    papel          TEXT NOT NULL DEFAULT 'colaborador',   -- admin | colaborador
    funcao         TEXT,
    area           TEXT,
    usuario_coleta TEXT UNIQUE,     -- chave dos eventos coletados deste colaborador
    token_coleta   TEXT UNIQUE,     -- usado pelo agente para enviar dados ao servidor
    ativo          INTEGER NOT NULL DEFAULT 1,
    criado_em      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_contas_empresa ON contas(empresa_id);

CREATE TABLE IF NOT EXISTS processos_decisao (
    empresa_id INTEGER NOT NULL,
    usuario    TEXT NOT NULL,          -- identificador de coleta do colaborador
    assinatura TEXT NOT NULL,          -- sequência de telas (analise.assinatura)
    decisao    TEXT NOT NULL,          -- fixo | pontual
    por        TEXT,
    ts         REAL NOT NULL,
    PRIMARY KEY (empresa_id, usuario, assinatura)
);

-- ---------------- executor (IA que opera o computador) ----------------
CREATE TABLE IF NOT EXISTS comandos (
    id          INTEGER PRIMARY KEY,
    empresa_id  INTEGER NOT NULL,
    conta_id    INTEGER NOT NULL,       -- colaborador cujo computador executa
    criado_por  INTEGER NOT NULL,       -- conta que pediu (o próprio colaborador ou um admin)
    instrucao   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'aguardando',  -- aguardando | aprovado | executando | concluido | falhou | bloqueado | cancelado | recusado
    resumo      TEXT,
    passos      INTEGER NOT NULL DEFAULT 0,
    tela_w      INTEGER,
    tela_h      INTEGER,
    conversa    TEXT,                   -- JSON: mensagens trocadas com o Claude (screenshots antigos removidos)
    criado_em   REAL NOT NULL,
    iniciado_em REAL,
    fim_em      REAL
);
CREATE INDEX IF NOT EXISTS idx_comandos_conta ON comandos(conta_id, status);

CREATE TABLE IF NOT EXISTS comandos_log (
    id         INTEGER PRIMARY KEY,
    comando_id INTEGER NOT NULL,
    ts         REAL NOT NULL,
    acao       TEXT NOT NULL           -- JSON da ação executada (sem screenshots)
);

CREATE TABLE IF NOT EXISTS melhorias_status (
    empresa_id INTEGER NOT NULL,
    chave      TEXT NOT NULL,          -- identifica a sugestão (colaborador + processo + tipo + etapas)
    status     TEXT NOT NULL,          -- nova | analise | andamento | concluida | descartada
    nota       TEXT,
    por        TEXT,
    ts         REAL NOT NULL,
    PRIMARY KEY (empresa_id, chave)
);
"""


def conectar(caminho=None):
    caminho = Path(caminho or config.DB_PATH)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def inserir_evento(con, ts, usuario, tipo, app=None, titulo=None, detalhe=None):
    con.execute(
        "INSERT INTO eventos (ts, usuario, tipo, app, titulo, detalhe) VALUES (?, ?, ?, ?, ?, ?)",
        (ts, usuario, tipo, app, titulo,
         json.dumps(detalhe, ensure_ascii=False) if detalhe else None),
    )


def eventos_do_usuario(con, usuario):
    return con.execute(
        "SELECT ts, tipo, app, titulo, detalhe FROM eventos WHERE usuario = ? ORDER BY ts, id",
        (usuario,),
    ).fetchall()


def usuarios(con):
    return [r[0] for r in con.execute("SELECT DISTINCT usuario FROM eventos ORDER BY usuario")]


def get_meta(con, chave, padrao=None):
    r = con.execute("SELECT valor FROM meta WHERE chave = ?", (chave,)).fetchone()
    return r[0] if r else padrao


def set_meta(con, chave, valor):
    con.execute("INSERT OR REPLACE INTO meta (chave, valor) VALUES (?, ?)", (chave, str(valor)))
    con.commit()


def tem_consentimento(con, usuario):
    return con.execute("SELECT 1 FROM consentimento WHERE usuario = ?", (usuario,)).fetchone() is not None


def registrar_consentimento(con, usuario, texto):
    con.execute("INSERT INTO consentimento (usuario, ts, texto) VALUES (?, ?, ?)", (usuario, time.time(), texto))
    con.commit()


def salvar_resultado(con, usuario, resultado):
    con.execute(
        "INSERT OR REPLACE INTO resultados (usuario, ts, dados) VALUES (?, ?, ?)",
        (usuario, time.time(), json.dumps(resultado, ensure_ascii=False)),
    )
    con.commit()


def carregar_resultado(con, usuario):
    r = con.execute("SELECT dados FROM resultados WHERE usuario = ?", (usuario,)).fetchone()
    if not r:
        return None
    resultado = json.loads(r[0])
    if "graficos" not in resultado:
        # análise feita por uma versão anterior (sem gargalos/gráficos): refaz com os mesmos dados
        import analise
        import documentador
        try:
            novo = analise.analisar(con, usuario)
        except ValueError:
            return resultado
        conta = con.execute("SELECT nome, funcao, area FROM contas WHERE usuario_coleta = ?", (usuario,)).fetchone()
        documentador.documentar(novo, contexto=dict(conta) if conta else None)
        salvar_resultado(con, usuario, novo)
        return novo
    return resultado


def usuarios_com_resultado(con):
    return [r[0] for r in con.execute("SELECT usuario FROM resultados ORDER BY usuario")]


# ---------------------------------------------------------------------- empresas e contas
def criar_empresa(con, nome, cnpj=None):
    cur = con.execute("INSERT INTO empresas (nome, cnpj, criado_em) VALUES (?, ?, ?)", (nome, cnpj, time.time()))
    con.commit()
    return cur.lastrowid


def empresa(con, empresa_id):
    return con.execute("SELECT * FROM empresas WHERE id = ?", (empresa_id,)).fetchone()


def atualizar_empresa(con, empresa_id, nome, cnpj):
    con.execute("UPDATE empresas SET nome = ?, cnpj = ? WHERE id = ?", (nome, cnpj, empresa_id))
    con.commit()


def criar_conta(con, empresa_id, nome, email, senha_hash, papel="colaborador", funcao=None, area=None,
                usuario_coleta=None, token_coleta=None):
    email = email.strip().lower()
    cur = con.execute(
        "INSERT INTO contas (empresa_id, nome, email, senha_hash, papel, funcao, area, usuario_coleta, token_coleta, criado_em)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (empresa_id, nome, email, senha_hash, papel, funcao, area, usuario_coleta or email, token_coleta, time.time()),
    )
    con.commit()
    return cur.lastrowid


def conta(con, conta_id):
    return con.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone()


def conta_por_email(con, email):
    return con.execute("SELECT * FROM contas WHERE email = ?", ((email or "").strip().lower(),)).fetchone()


def conta_por_token(con, token):
    return con.execute("SELECT * FROM contas WHERE token_coleta = ? AND ativo = 1", (token,)).fetchone()


def contas_da_empresa(con, empresa_id):
    return con.execute(
        "SELECT * FROM contas WHERE empresa_id = ? ORDER BY COALESCE(area, ''), nome", (empresa_id,)
    ).fetchall()


def atualizar_conta(con, conta_id, **campos):
    permitidos = {"nome", "email", "senha_hash", "papel", "funcao", "area", "usuario_coleta", "token_coleta", "ativo"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if "email" in campos:
        campos["email"] = campos["email"].strip().lower()
    if not campos:
        return
    sets = ", ".join(f"{k} = ?" for k in campos)
    con.execute(f"UPDATE contas SET {sets} WHERE id = ?", (*campos.values(), conta_id))
    con.commit()


def areas_da_empresa(con, empresa_id):
    return [r[0] for r in con.execute(
        "SELECT DISTINCT area FROM contas WHERE empresa_id = ? AND area IS NOT NULL AND area != '' ORDER BY area",
        (empresa_id,))]


def resumo_coleta(con, usuario):
    """Dias com atividade, total de eventos e último evento de um colaborador."""
    r = con.execute(
        "SELECT COUNT(*), MIN(ts), MAX(ts), COUNT(DISTINCT date(ts, 'unixepoch', 'localtime')) FROM eventos WHERE usuario = ?",
        (usuario,),
    ).fetchone()
    return {"eventos": r[0], "inicio": r[1], "ultimo": r[2], "dias": r[3]}


def resultado_ts(con, usuario):
    r = con.execute("SELECT ts FROM resultados WHERE usuario = ?", (usuario,)).fetchone()
    return r[0] if r else None


def status_melhorias(con, empresa_id):
    return {r["chave"]: dict(r) for r in con.execute(
        "SELECT chave, status, nota, por, ts FROM melhorias_status WHERE empresa_id = ?", (empresa_id,))}


def salvar_status_melhoria(con, empresa_id, chave, status, por, nota=None):
    con.execute("INSERT OR REPLACE INTO melhorias_status (empresa_id, chave, status, nota, por, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (empresa_id, chave, status, nota, por, time.time()))
    con.commit()


def decisoes_processos(con, empresa_id, usuario):
    return {r["assinatura"]: dict(r) for r in con.execute(
        "SELECT assinatura, decisao, por, ts FROM processos_decisao WHERE empresa_id = ? AND usuario = ?",
        (empresa_id, usuario))}


def salvar_decisao_processo(con, empresa_id, usuario, assinatura, decisao, por):
    con.execute("INSERT OR REPLACE INTO processos_decisao (empresa_id, usuario, assinatura, decisao, por, ts) "
                "VALUES (?, ?, ?, ?, ?, ?)", (empresa_id, usuario, assinatura, decisao, por, time.time()))
    con.commit()


# ---------------------------------------------------------------------- executor
def executor_ativo(con, conta_id):
    return get_meta(con, f"executor_ativo:{conta_id}", "0") == "1"



def definir_executor_ativo(con, conta_id, ativo):
    set_meta(con, f"executor_ativo:{conta_id}", "1" if ativo else "0")


def criar_comando(con, empresa_id, conta_id, criado_por, instrucao):
    cur = con.execute(
        "INSERT INTO comandos (empresa_id, conta_id, criado_por, instrucao, criado_em) VALUES (?, ?, ?, ?, ?)",
        (empresa_id, conta_id, criado_por, instrucao, time.time()))
    con.commit()
    return cur.lastrowid


def comando(con, comando_id):
    return con.execute("SELECT * FROM comandos WHERE id = ?", (comando_id,)).fetchone()


def comandos_da_empresa(con, empresa_id, conta_id=None, limite=50):
    if conta_id:
        return con.execute("SELECT c.*, a.nome AS colaborador FROM comandos c JOIN contas a ON a.id = c.conta_id "
                           "WHERE c.empresa_id = ? AND c.conta_id = ? ORDER BY c.id DESC LIMIT ?",
                           (empresa_id, conta_id, limite)).fetchall()
    return con.execute("SELECT c.*, a.nome AS colaborador FROM comandos c JOIN contas a ON a.id = c.conta_id "
                       "WHERE c.empresa_id = ? ORDER BY c.id DESC LIMIT ?", (empresa_id, limite)).fetchall()


def atualizar_comando(con, comando_id, **campos):
    permitidos = {"status", "resumo", "passos", "tela_w", "tela_h", "conversa", "iniciado_em", "fim_em"}
    campos = {k: v for k, v in campos.items() if k in permitidos}
    if campos:
        sets = ", ".join(f"{k} = ?" for k in campos)
        con.execute(f"UPDATE comandos SET {sets} WHERE id = ?", (*campos.values(), comando_id))
        con.commit()


def proximo_comando_aprovado(con, conta_id):
    return con.execute("SELECT * FROM comandos WHERE conta_id = ? AND status = 'aprovado' ORDER BY id LIMIT 1",
                       (conta_id,)).fetchone()


def registrar_acao(con, comando_id, acao):
    con.execute("INSERT INTO comandos_log (comando_id, ts, acao) VALUES (?, ?, ?)",
                (comando_id, time.time(), json.dumps(acao, ensure_ascii=False)))
    con.commit()


def log_do_comando(con, comando_id):
    return con.execute("SELECT ts, acao FROM comandos_log WHERE comando_id = ? ORDER BY id", (comando_id,)).fetchall()
