"""Configuração dos testes: cada teste usa um banco SQLite temporário e dados fictícios."""
import importlib
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))


@pytest.fixture()
def banco(tmp_path, monkeypatch):
    monkeypatch.setenv("TASKMINING_DB", str(tmp_path / "teste.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import config
    importlib.reload(config)
    config.ANTHROPIC_API_KEY = ""
    import db
    importlib.reload(db)
    return db


@pytest.fixture()
def empresa_demo(banco):
    """Empresa Demo com 2 semanas simuladas de 2 colaboradores, já analisadas."""
    import simulador
    import main
    contas = simulador.criar_empresa_demo()
    con = banco.conectar()
    for c in contas:
        if banco.resumo_coleta(con, c["usuario_coleta"])["eventos"]:
            main._analisar(con, c["usuario_coleta"], False,
                           {"nome": c["nome"], "funcao": c["funcao"], "area": c["area"]}, email_demo=c["email"])
    return {c["email"]: c for c in contas}


@pytest.fixture()
def cliente(empresa_demo):
    import painel
    painel.app.config["TESTING"] = True
    return painel.app.test_client


def entrar(cliente_factory, email, senha="demo12345"):
    import re
    c = cliente_factory()
    html = c.get("/entrar").get_data(as_text=True)
    csrf = re.search(r'name="csrf" value="([^"]+)"', html).group(1)
    resp = c.post("/entrar", data={"csrf": csrf, "email": email, "senha": senha})
    return c, csrf, resp
