"""TaskMiner — IA que observa o trabalho no computador e documenta os processos de cada função.

Uso:
  python main.py demo                                         # empresa de exemplo + painel (comece por aqui)
  python main.py painel   [--porta 5000] [--rede]             # abre o painel web (--rede: acessível por outros PCs)
  python main.py coletar  [--servidor URL --token CODIGO]     # Windows: inicia a coleta no PC do colaborador
  python main.py enviar                                       # força o envio dos dados pendentes ao servidor
  python main.py analisar --usuario ID [--sem-ia]             # analisa um colaborador pela linha de comando
  python main.py exportar --usuario ID                        # salva o manual em Markdown
  python main.py simular  [--usuario ID] [--perfil financeiro|comercial]
"""
import argparse
import getpass
import sys

import config
import db


def _usuario_padrao(con, informado):
    if informado:
        return informado
    usuarios = db.usuarios(con)
    if len(usuarios) == 1:
        return usuarios[0]
    if usuarios:
        sys.exit(f"Há vários colaboradores no banco ({', '.join(usuarios)}). Use --usuario.")
    sys.exit("Nenhum dado coletado ainda.")


def cmd_coletar(a):
    import agente
    agente.iniciar(a.usuario, a.dias, a.servidor, a.token)


def cmd_enviar(a):
    import envio
    con = db.conectar()
    servidor, token = a.servidor or db.get_meta(con, "servidor"), a.token or db.get_meta(con, "token")
    if not (servidor and token):
        sys.exit("Informe --servidor e --token (o comando completo está na página 'Minha coleta').")
    usuario = a.usuario or getpass.getuser()
    n = envio.enviar_pendentes(con, servidor, token, usuario)
    print(f"{n} evento(s) enviados para {servidor}.")


def cmd_simular(a):
    import simulador
    usuario = a.usuario or "ana.souza"
    n, dias = simulador.simular(usuario, perfil=a.perfil)
    print(f"{n} eventos fictícios gerados para {dias} dias úteis de '{usuario}' (perfil {a.perfil}).")


def _analisar(con, usuario, usar_ia=True, contexto=None, email_demo=None):
    import analise
    import documentador
    resultado = analise.analisar(con, usuario)
    print(f"  {len(resultado['processos'])} processos repetidos encontrados em {resultado['periodo']['dias']} dias.")
    documentador.documentar(resultado, usar_ia=usar_ia, contexto=contexto)
    if email_demo and not (usar_ia and config.ANTHROPIC_API_KEY):
        if documentador.aplicar_docs_demo(resultado, email_demo):
            print("  Usando a documentação de exemplo escrita pelo Claude (docs_demo.json).")
    db.salvar_resultado(con, usuario, resultado)


def cmd_analisar(a):
    con = db.conectar()
    usuario = _usuario_padrao(con, a.usuario)
    c = con.execute("SELECT * FROM contas WHERE usuario_coleta = ?", (usuario,)).fetchone()
    contexto = {"nome": c["nome"], "funcao": c["funcao"], "area": c["area"]} if c else None
    print(f"Analisando atividades de '{usuario}'...")
    _analisar(con, usuario, not a.sem_ia, contexto)
    print("Pronto! Veja o resultado no painel: python main.py painel")


def cmd_painel(a):
    import painel
    painel.rodar(a.porta, "0.0.0.0" if a.rede else "127.0.0.1")


def cmd_exportar(a):
    import documentador
    con = db.conectar()
    usuario = _usuario_padrao(con, a.usuario)
    r = db.carregar_resultado(con, usuario) or sys.exit("Rode a análise antes de exportar.")
    nome = f"Manual_de_Processos_{usuario.replace('@', '_')}.md"
    with open(nome, "w", encoding="utf-8") as f:
        f.write(documentador.exportar_markdown(r))
    print(f"Manual salvo em {nome}")


def cmd_demo(a):
    import simulador
    print("Criando a Empresa Demo e simulando 2 semanas de coleta de 2 colaboradores...")
    contas = simulador.criar_empresa_demo()
    con = db.conectar()
    for c in contas:
        if db.resumo_coleta(con, c["usuario_coleta"])["eventos"]:
            print(f"Analisando {c['nome']} ({c['area']})...")
            _analisar(con, c["usuario_coleta"], not a.sem_ia, {"nome": c["nome"], "funcao": c["funcao"], "area": c["area"]},
                      email_demo=c["email"])
    print("\nLogins de demonstração (senha de todos: %s)" % simulador.SENHA_DEMO)
    for c in contas:
        print(f"  {'ADMIN ' if c['papel'] == 'admin' else '      '}{c['email']:<28} {c['nome']} — {c['funcao']} ({c['area']})")
    print()
    cmd_painel(a)


def main():
    p = argparse.ArgumentParser(description="TaskMiner — mapeamento automático de processos")
    sub = p.add_subparsers(dest="comando", required=True)
    for nome, func, ajuda in [
        ("demo", cmd_demo, "empresa de exemplo + painel"),
        ("painel", cmd_painel, "abre o painel web"),
        ("coletar", cmd_coletar, "inicia a coleta no Windows"),
        ("enviar", cmd_enviar, "envia dados pendentes ao servidor"),
        ("analisar", cmd_analisar, "detecta e documenta os processos"),
        ("exportar", cmd_exportar, "exporta o manual em Markdown"),
        ("simular", cmd_simular, "gera dados de exemplo"),
    ]:
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("--usuario", help="identificador de coleta (e-mail do colaborador ou usuário do Windows)")
        s.add_argument("--dias", type=int)
        s.add_argument("--servidor", help="endereço do painel, ex.: http://192.168.0.10:5000")
        s.add_argument("--token", help="código de coleta do colaborador (página 'Minha coleta')")
        s.add_argument("--perfil", default="financeiro", choices=["financeiro", "comercial"])
        s.add_argument("--sem-ia", action="store_true", help="não chama o Claude")
        s.add_argument("--porta", type=int, default=5000)
        s.add_argument("--rede", action="store_true", help="deixa o painel acessível por outros computadores")
        s.set_defaults(func=func)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
