"""Ponto de entrada do servidor em produção (Render): gunicorn wsgi:app

Com DEMO=1, cria a Empresa Demo na primeira vez que o servidor sobe (o disco do plano gratuito
do Render é apagado a cada novo deploy, então a demonstração é recriada automaticamente).
"""
import os

import db

if os.environ.get("DEMO") == "1":
    con = db.conectar()
    if not db.usuarios_com_resultado(con):
        import main
        import simulador
        for c in simulador.criar_empresa_demo():
            if db.resumo_coleta(con, c["usuario_coleta"])["eventos"]:
                main._analisar(con, c["usuario_coleta"], True,
                               {"nome": c["nome"], "funcao": c["funcao"], "area": c["area"]}, email_demo=c["email"])
    con.close()

from painel import app  # noqa: E402

if __name__ == "__main__":
    app.run()
