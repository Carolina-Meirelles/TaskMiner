"""Painel web (Flask) com contas.

Perfis:
  - administrador: cadastra a empresa e os colaboradores (função e área), vê a documentação
    e os processos de TODOS os colaboradores da empresa e roda as análises;
  - colaborador: entra com o próprio login, vê só os próprios processos e as instruções
    para instalar o agente de coleta.

Também expõe a API usada pelo agente para enviar os eventos coletados (/api/eventos).
"""
import functools
import secrets
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from flask import (Flask, Response, abort, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import db
from documentador import exportar_markdown

app = Flask(__name__)


def _chave_secreta():
    if config.SECRET_KEY:
        return config.SECRET_KEY
    arq = Path(config.DB_PATH).parent / ".chave_secreta"
    arq.parent.mkdir(parents=True, exist_ok=True)
    if not arq.exists():
        arq.write_text(secrets.token_hex(32))
    return arq.read_text().strip()


app.secret_key = _chave_secreta()
app.config.update(MAX_CONTENT_LENGTH=12 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax", PERMANENT_SESSION_LIFETIME=8 * 3600)

SENHA_MINIMA = 8


# ---------------------------------------------------------------------- infraestrutura
def con():
    if "con" not in g:
        g.con = db.conectar()
    return g.con


@app.teardown_appcontext
def _fechar(_):
    c = g.pop("con", None)
    if c:
        c.close()


@app.before_request
def _carregar_usuario():
    g.eu = None
    if "conta_id" in session:
        c = db.conta(con(), session["conta_id"])
        if c and c["ativo"]:
            g.eu = c
            g.empresa = db.empresa(con(), c["empresa_id"])
        else:
            session.clear()
    # proteção CSRF para formulários (a API do agente usa token próprio)
    if request.method == "POST" and not request.path.startswith("/api/"):
        esperado = session.get("csrf")
        if not esperado or not secrets.compare_digest(request.form.get("csrf", ""), esperado):
            abort(400, "Formulário expirado. Volte e tente de novo.")


@app.context_processor
def _globais():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return {"csrf": session["csrf"], "eu": g.get("eu"), "empresa": g.get("empresa"),
            "fmt_data": _fmt_data, "status_coleta": _status_coleta, "config_dias": config.DIAS_DE_COLETA}


def _fmt_data(ts_ou_iso):
    if not ts_ou_iso:
        return "—"
    if isinstance(ts_ou_iso, (int, float)):
        return datetime.fromtimestamp(ts_ou_iso).strftime("%d/%m/%Y %H:%M")
    return f"{ts_ou_iso[8:10]}/{ts_ou_iso[5:7]}/{ts_ou_iso[:4]}"


def login_obrigatorio(f):
    @functools.wraps(f)
    def envolto(*a, **k):
        if not g.eu:
            return redirect(url_for("entrar", proximo=request.path))
        return f(*a, **k)
    return envolto


def admin_obrigatorio(f):
    @functools.wraps(f)
    @login_obrigatorio
    def envolto(*a, **k):
        if g.eu["papel"] != "admin":
            abort(403)
        return f(*a, **k)
    return envolto


def _colaborador_visivel(conta_id):
    """Admin vê qualquer colaborador da própria empresa; colaborador só vê a si mesmo."""
    c = db.conta(con(), conta_id)
    if not c or c["empresa_id"] != g.eu["empresa_id"]:
        abort(404)
    if g.eu["papel"] != "admin" and c["id"] != g.eu["id"]:
        abort(403)
    return c


def _status_coleta(c):
    """Situação da coleta/análise de um colaborador, para exibir como etiqueta."""
    usuario = c["usuario_coleta"]
    resumo = db.resumo_coleta(con(), usuario)
    analisado = db.resultado_ts(con(), usuario)
    if analisado:
        novos = resumo["ultimo"] and resumo["ultimo"] > analisado
        return {"chave": "documentado", "texto": "Documentado" + (" · há dados novos" if novos else ""), **resumo}
    if not resumo["eventos"]:
        return {"chave": "aguardando", "texto": "Aguardando coleta", **resumo}
    completo = (time.time() - resumo["inicio"]) >= config.DIAS_DE_COLETA * 86400 or resumo["dias"] >= 10
    if completo:
        return {"chave": "pronto", "texto": "Pronto para análise", **resumo}
    return {"chave": "coletando", "texto": f"Coletando · {resumo['dias']} dia(s)", **resumo}


def _validar_senha(senha, confirmacao=None):
    if len(senha or "") < SENHA_MINIMA:
        return f"A senha precisa ter pelo menos {SENHA_MINIMA} caracteres."
    if confirmacao is not None and senha != confirmacao:
        return "As senhas não conferem."
    return None


def _entrar_como(conta_id):
    session.clear()
    session.permanent = True
    session["conta_id"] = conta_id
    session["csrf"] = secrets.token_urlsafe(24)


# ---------------------------------------------------------------------- cadastro e login
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    """Cadastra uma nova empresa e o seu administrador."""
    f = request.form
    if request.method == "POST":
        erro = None
        if not f.get("empresa", "").strip() or not f.get("nome", "").strip() or "@" not in f.get("email", ""):
            erro = "Preencha o nome da empresa, o seu nome e um e-mail válido."
        erro = erro or _validar_senha(f.get("senha"), f.get("senha2"))
        if not erro and db.conta_por_email(con(), f["email"]):
            erro = "Já existe uma conta com esse e-mail."
        if erro:
            flash(erro, "erro")
            return render_template("cadastro.html", f=f)
        empresa_id = db.criar_empresa(con(), f["empresa"].strip(), f.get("cnpj", "").strip() or None)
        conta_id = db.criar_conta(con(), empresa_id, f["nome"].strip(), f["email"], generate_password_hash(f["senha"]),
                                  papel="admin", funcao=f.get("funcao", "").strip() or "Administrador(a)",
                                  area=f.get("area", "").strip() or None, token_coleta=secrets.token_urlsafe(24))
        _entrar_como(conta_id)
        flash("Empresa cadastrada. Agora cadastre os colaboradores que participarão do mapeamento.", "ok")
        return redirect(url_for("colaboradores"))
    return render_template("cadastro.html", f={})


@app.route("/entrar", methods=["GET", "POST"])
def entrar():
    if request.method == "POST":
        c = db.conta_por_email(con(), request.form.get("email"))
        if c and c["ativo"] and check_password_hash(c["senha_hash"], request.form.get("senha", "")):
            _entrar_como(c["id"])
            proximo = request.args.get("proximo", "")
            return redirect(proximo if proximo.startswith("/") and not proximo.startswith("//") else url_for("inicio"))
        time.sleep(0.5)  # dificulta tentativas em massa
        flash("E-mail ou senha incorretos.", "erro")
    return render_template("entrar.html", email=request.form.get("email", ""))


@app.route("/sair", methods=["POST"])
def sair():
    session.clear()
    return redirect(url_for("entrar"))


@app.route("/")
@login_obrigatorio
def inicio():
    if g.eu["papel"] == "admin":
        return redirect(url_for("empresa_processos"))
    return redirect(url_for("colaborador", conta_id=g.eu["id"]))


# ---------------------------------------------------------------------- administrador
@app.route("/empresa")
@admin_obrigatorio
def empresa_painel():
    contas = db.contas_da_empresa(con(), g.eu["empresa_id"])
    linhas, processos = [], []
    horas_semana = 0.0
    for c in contas:
        st = _status_coleta(c)
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        linha = {"c": c, "st": st, "r": r}
        if r:
            e = r["estatisticas"]
            horas_semana += e["tempo_em_processos_s"] / max(r["periodo"]["dias"], 1) * 5 / 3600
            for p in r["processos"]:
                processos.append({"p": p, "c": c})
        linhas.append(linha)

    areas = {}
    for linha in linhas:
        areas.setdefault(linha["c"]["area"] or "Sem área definida", []).append(linha)
    resumo = {
        "colaboradores": sum(1 for c in contas if c["ativo"]),
        "areas": len([a for a in areas if a != "Sem área definida"]),
        "processos": len(processos),
        "horas_semana": round(horas_semana, 1),
        "documentados": sum(1 for l in linhas if l["r"]),
    }
    processos.sort(key=lambda x: -x["p"]["tempo_total_s"])
    gargalos = _gargalos_da_empresa([(l["c"], l["r"]) for l in linhas if l["r"]])
    resumo["gargalos_alta"] = sum(1 for x in gargalos if x["severidade"] == "alta")
    return render_template("empresa.html", areas=areas, processos=processos, resumo=resumo, gargalos=gargalos[:3],
                           total_gargalos=len(gargalos))


@app.route("/empresa/dados", methods=["POST"])
@admin_obrigatorio
def empresa_dados():
    nome = request.form.get("nome", "").strip()
    if not nome:
        flash("O nome da empresa não pode ficar vazio.", "erro")
    else:
        db.atualizar_empresa(con(), g.eu["empresa_id"], nome, request.form.get("cnpj", "").strip() or None)
        flash("Dados da empresa salvos.", "ok")
    return redirect(url_for("colaboradores"))


@app.route("/empresa/exportar")
@admin_obrigatorio
def empresa_exportar():
    """Manual com a documentação de todos os colaboradores, organizado por área."""
    partes = [f"# Manual de Processos — {g.empresa['nome']}", "",
              f"Gerado em {datetime.now():%d/%m/%Y %H:%M}.", ""]
    for c in db.contas_da_empresa(con(), g.eu["empresa_id"]):
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        if r:
            md = exportar_markdown(r, nome=c["nome"], funcao=c["funcao"], area=c["area"])
            partes.append(md.replace("\n#", "\n##").replace("# Manual de Processos", "## Colaborador", 1))
            partes.append("\n---\n")
    import melhorias as _m
    lista, _, _, _ = _contexto_melhorias(db.contas_da_empresa(con(), g.eu["empresa_id"]))
    if lista:
        rot = dict(_m.STATUS)
        partes += ["# Sugestões de melhoria", "", "| Prioridade | Sugestão | Processo | Responsável | Impacto | Esforço | Situação |",
                   "|---|---|---|---|---|---|---|"]
        for i in lista:
            imp = f"{str(i['horas_semana']).replace('.', ',')} h/sem" if i["horas_semana"] else "—"
            partes.append(f"| {i['prioridade_txt']} | **{i['titulo']}** — {i['sugestao']} | {i['processo']} | {i['responsavel']} | "
                          f"{imp} | {i['esforco_txt'].replace('Esforço ', '')} | {rot[i['status']]} |")
        partes.append("")
    nome_arq = "".join(ch if ch.isalnum() else "_" for ch in g.empresa["nome"])
    return Response("\n".join(partes), mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=Manual_{nome_arq}.md"})


@app.route("/colaboradores")
@admin_obrigatorio
def colaboradores():
    contas = db.contas_da_empresa(con(), g.eu["empresa_id"])
    return render_template("colaboradores.html", contas=contas, areas=db.areas_da_empresa(con(), g.eu["empresa_id"]),
                           f={})


@app.route("/colaboradores/novo", methods=["POST"])
@admin_obrigatorio
def colaborador_novo():
    f = request.form
    erro = None
    if not f.get("nome", "").strip() or "@" not in f.get("email", ""):
        erro = "Informe o nome e um e-mail válido."
    erro = erro or _validar_senha(f.get("senha"))
    if not erro and db.conta_por_email(con(), f["email"]):
        erro = "Já existe uma conta com esse e-mail."
    if erro:
        flash(erro, "erro")
        contas = db.contas_da_empresa(con(), g.eu["empresa_id"])
        return render_template("colaboradores.html", contas=contas,
                               areas=db.areas_da_empresa(con(), g.eu["empresa_id"]), f=f), 400
    try:
        conta_id = db.criar_conta(
            con(), g.eu["empresa_id"], f["nome"].strip(), f["email"], generate_password_hash(f["senha"]),
            papel="admin" if f.get("papel") == "admin" else "colaborador",
            funcao=f.get("funcao", "").strip() or None, area=f.get("area", "").strip() or None,
            usuario_coleta=f.get("usuario_coleta", "").strip() or None, token_coleta=secrets.token_urlsafe(24),
        )
    except sqlite3.IntegrityError:
        flash("Esse identificador de coleta já está em uso por outra conta.", "erro")
        return redirect(url_for("colaboradores"))
    flash(f"{f['nome'].strip()} cadastrado(a). Envie o e-mail e a senha inicial para a pessoa entrar.", "ok")
    return redirect(url_for("colaborador_editar", conta_id=conta_id))


@app.route("/colaboradores/<int:conta_id>/editar", methods=["GET", "POST"])
@admin_obrigatorio
def colaborador_editar(conta_id):
    c = _colaborador_visivel(conta_id)
    if request.method == "POST":
        f = request.form
        acao = f.get("acao", "salvar")
        if acao == "novo_token":
            db.atualizar_conta(con(), c["id"], token_coleta=secrets.token_urlsafe(24))
            flash("Novo código de coleta gerado. O código antigo deixou de funcionar.", "ok")
            return redirect(url_for("colaborador_editar", conta_id=c["id"]))
        if acao == "alternar_ativo":
            if c["id"] == g.eu["id"]:
                flash("Você não pode desativar a sua própria conta.", "erro")
            else:
                db.atualizar_conta(con(), c["id"], ativo=0 if c["ativo"] else 1)
                flash("Conta desativada: a pessoa não entra mais e o agente para de enviar dados." if c["ativo"]
                      else "Conta reativada.", "ok")
            return redirect(url_for("colaborador_editar", conta_id=c["id"]))

        campos = {"nome": f.get("nome", "").strip(), "email": f.get("email", "").strip(),
                  "funcao": f.get("funcao", "").strip() or None, "area": f.get("area", "").strip() or None,
                  "usuario_coleta": f.get("usuario_coleta", "").strip() or c["usuario_coleta"]}
        if c["id"] != g.eu["id"]:
            campos["papel"] = "admin" if f.get("papel") == "admin" else "colaborador"
        erro = None
        if not campos["nome"] or "@" not in campos["email"]:
            erro = "Informe o nome e um e-mail válido."
        outra = db.conta_por_email(con(), campos["email"])
        if not erro and outra and outra["id"] != c["id"]:
            erro = "Já existe outra conta com esse e-mail."
        if not erro and f.get("senha"):
            erro = _validar_senha(f["senha"])
            campos["senha_hash"] = generate_password_hash(f["senha"])
        if erro:
            flash(erro, "erro")
        else:
            try:
                db.atualizar_conta(con(), c["id"], **campos)
                flash("Alterações salvas.", "ok")
            except sqlite3.IntegrityError:
                flash("Esse identificador de coleta já está em uso por outra conta.", "erro")
        return redirect(url_for("colaborador_editar", conta_id=c["id"]))
    return render_template("colaborador_editar.html", c=c, st=_status_coleta(c),
                           areas=db.areas_da_empresa(con(), g.eu["empresa_id"]), servidor=request.host_url.rstrip("/"))


@app.route("/colaborador/<int:conta_id>/analisar", methods=["POST"])
@admin_obrigatorio
def colaborador_analisar(conta_id):
    import analise
    import documentador
    c = _colaborador_visivel(conta_id)
    try:
        r = _reanalisar(c)
    except ValueError:
        flash("Ainda não há dados coletados para esse colaborador.", "erro")
        return redirect(url_for("colaborador", conta_id=c["id"]))
    flash(f"Análise concluída: {len(r['processos'])} processo(s) identificado(s).", "ok")
    return redirect(url_for("colaborador", conta_id=c["id"]))


# ---------------------------------------------------------------------- colaborador (e admin)
@app.route("/colaborador/<int:conta_id>")
@login_obrigatorio
def colaborador(conta_id):
    c = _colaborador_visivel(conta_id)
    r = db.carregar_resultado(con(), c["usuario_coleta"])
    return render_template("colaborador.html", c=c, r=r, st=_status_coleta(c),
                           semana=_rotina_semanal(r) if r else [], novos=_candidatos([c]))


@app.route("/colaborador/<int:conta_id>/processo/<pid>")
@login_obrigatorio
def processo(conta_id, pid):
    c = _colaborador_visivel(conta_id)
    r = db.carregar_resultado(con(), c["usuario_coleta"]) or abort(404)
    p = next((p for p in r["processos"] if p["id"] == pid), None) or abort(404)
    return render_template("processo.html", c=c, r=r, p=p)


@app.route("/colaborador/<int:conta_id>/exportar")
@login_obrigatorio
def exportar(conta_id):
    c = _colaborador_visivel(conta_id)
    r = db.carregar_resultado(con(), c["usuario_coleta"]) or abort(404)
    nome_arq = "".join(ch if ch.isalnum() else "_" for ch in c["nome"])
    return Response(exportar_markdown(r, nome=c["nome"], funcao=c["funcao"], area=c["area"]),
                    mimetype="text/markdown; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=Manual_de_Processos_{nome_arq}.md"})


@app.route("/minha-coleta")
@login_obrigatorio
def minha_coleta():
    return render_template("minha_coleta.html", c=g.eu, st=_status_coleta(g.eu), servidor=request.host_url.rstrip("/"))


@app.route("/minha-conta", methods=["GET", "POST"])
@login_obrigatorio
def minha_conta():
    if request.method == "POST":
        f = request.form
        if not check_password_hash(g.eu["senha_hash"], f.get("atual", "")):
            flash("A senha atual está incorreta.", "erro")
        else:
            erro = _validar_senha(f.get("senha"), f.get("senha2"))
            if erro:
                flash(erro, "erro")
            else:
                db.atualizar_conta(con(), g.eu["id"], senha_hash=generate_password_hash(f["senha"]))
                flash("Senha alterada.", "ok")
        return redirect(url_for("minha_conta"))
    return render_template("minha_conta.html")


# ---------------------------------------------------------------------- gráficos e gargalos
def _dados_empresa():
    """Junta resultados de todos os colaboradores da empresa."""
    itens = []
    for c in db.contas_da_empresa(con(), g.eu["empresa_id"]):
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        if r:
            itens.append((c, r))
    return itens


def _gargalos_da_empresa(itens):
    lista = []
    for c, r in itens:
        for p in r["processos"]:
            for gg in p.get("gargalos", []):
                lista.append({**gg, "processo": p["documento"]["nome"], "responsavel": c["nome"],
                              "area": c["area"] or "Sem área definida",
                              "link": url_for("processo", conta_id=c["id"], pid=p["id"])})
    ordem = {"alta": 0, "media": 1}
    lista.sort(key=lambda x: (ordem[x["severidade"]], -(x["horas_semana"] or 0)))
    return lista


@app.route("/empresa/graficos")
@admin_obrigatorio
def empresa_graficos():
    itens = _dados_empresa()
    por_area, gargalos_area, processos = {}, {}, []
    for c, r in itens:
        area = c["area"] or "Sem área definida"
        h = r["estatisticas"]["tempo_em_processos_s"] / r["periodo"]["dias"] * 5 / 3600
        por_area[area] = por_area.get(area, 0) + h
        for p in r["processos"]:
            processos.append({"rotulo": p["documento"]["nome"], "sub": f"{c['nome']} · {area}",
                              "valor": p["horas_semana"], "texto": f"{str(p['horas_semana']).replace('.', ',')} h",
                              "destaque": any(x["severidade"] == "alta" for x in p.get("gargalos", []))})
            ga = gargalos_area.setdefault(area, {"alta": 0, "media": 0})
            for x in p.get("gargalos", []):
                ga[x["severidade"]] += 1
    areas = [{"rotulo": a, "valor": round(v, 2), "texto": f"{str(round(v, 1)).replace('.', ',')} h"}
             for a, v in sorted(por_area.items(), key=lambda x: -x[1])]
    processos.sort(key=lambda x: -x["valor"])
    return render_template("empresa_graficos.html", areas=areas, processos=processos[:10],
                           gargalos_area=gargalos_area, itens=itens)


@app.route("/empresa/gargalos")
@admin_obrigatorio
def empresa_gargalos():
    return redirect(url_for("empresa_melhorias") + "#gargalos")


def _empresa_gargalos_antiga():
    lista = _gargalos_da_empresa(_dados_empresa())
    areas = sorted({x["area"] for x in lista})
    return render_template("empresa_gargalos.html", gargalos=lista, areas=areas,
                           horas=round(sum(x["horas_semana"] or 0 for x in lista if x["tipo"] == "instavel"), 1))


@app.route("/colaborador/<int:conta_id>/graficos")
@login_obrigatorio
def colaborador_graficos(conta_id):
    c = _colaborador_visivel(conta_id)
    r = db.carregar_resultado(con(), c["usuario_coleta"])
    if not r:
        flash("Os gráficos aparecem depois que os processos forem documentados.", "info")
        return redirect(url_for("colaborador", conta_id=c["id"]))
    linhas = [{"rotulo": p["documento"]["nome"], "sub": p["frequencia"], "valor": p["horas_semana"],
               "texto": f"{str(p['horas_semana']).replace('.', ',')} h"} for p in r["processos"]]
    return render_template("colaborador_graficos.html", c=c, r=r, linhas=linhas)


# ---------------------------------------------------------------------- manual de processos
DIAS_UTEIS = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]


def _rotina_semanal(r):
    """Distribui os processos pelos dias da semana em que foram observados, por horário."""
    from datetime import datetime as _dt
    semana = {k: [] for k in range(5)}
    for p in r["processos"]:
        dias = {_dt.fromtimestamp(e[0]).weekday() for e in p.get("execucoes", [])}
        if p["tipo_frequencia"] == "diaria":
            dias = set(range(5))
        for d in dias:
            if d < 5:
                semana[d].append(p)
    for d in semana:
        semana[d].sort(key=lambda p: p["horario_tipico"])
    return [(DIAS_UTEIS[d], semana[d]) for d in range(5)]


@app.route("/colaborador/<int:conta_id>/manual")
@login_obrigatorio
def colaborador_manual(conta_id):
    c = _colaborador_visivel(conta_id)
    r = db.carregar_resultado(con(), c["usuario_coleta"])
    if not r:
        flash("O manual fica disponível depois que os processos forem documentados.", "info")
        return redirect(url_for("colaborador", conta_id=c["id"]))
    return render_template("manual.html", c=c, r=r, semana=_rotina_semanal(r))


@app.route("/processos")
@admin_obrigatorio
def empresa_processos():
    """Tela principal do administrador: as atividades de todos, com o passo a passo."""
    areas, colabs = {}, []
    for c in db.contas_da_empresa(con(), g.eu["empresa_id"]):
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        areas.setdefault(c["area"] or "Sem área definida", []).append((c, r))
        if r:
            colabs.append(c)
    total = sum(len(r["processos"]) for itens in areas.values() for _, r in itens if r)
    return render_template("processos_empresa.html", areas=dict(sorted(areas.items())), total=total, colabs=colabs,
                           novos=_candidatos(db.contas_da_empresa(con(), g.eu["empresa_id"])))


@app.route("/empresa/manual")
@admin_obrigatorio
def empresa_manual():
    areas = {}
    for c in db.contas_da_empresa(con(), g.eu["empresa_id"]):
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        areas.setdefault(c["area"] or "Sem área definida", []).append((c, r))
    total = sum(len(r["processos"]) for itens in areas.values() for _, r in itens if r)
    return render_template("empresa_manual.html", areas=dict(sorted(areas.items())), total=total)


# ---------------------------------------------------------------------- melhorias e gargalos
def _contexto_melhorias(contas):
    import melhorias
    itens = []
    for c in contas:
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        if r:
            itens.append((c, r, lambda pid, cid=c["id"]: url_for("processo", conta_id=cid, pid=pid)))
    lista = melhorias.da_empresa(itens)
    status = db.status_melhorias(con(), g.eu["empresa_id"])
    for it in lista:
        st = status.get(it["chave"])
        it["status"] = st["status"] if st else "nova"
        it["status_por"] = st["por"] if st else None
    gargalos = _gargalos_da_empresa([(c, r) for c, r, _ in itens])
    matriz = {}
    for it in lista:
        if it["status"] in ("concluida", "descartada"):
            continue
        imp = "alto" if (it["horas_semana"] or 0) >= 1 else "baixo"
        matriz[(imp, it["esforco"])] = matriz.get((imp, it["esforco"]), 0) + 1
    resumo = {
        "abertas": sum(1 for i in lista if i["status"] not in ("concluida", "descartada")),
        "alto": sum(1 for i in lista if i["prioridade"] == "alto" and i["status"] not in ("concluida", "descartada")),
        "rapido": sum(1 for i in lista if i["prioridade"] == "rapido" and i["status"] not in ("concluida", "descartada")),
        "concluidas": sum(1 for i in lista if i["status"] == "concluida"),
        "gargalos": len(gargalos), "gargalos_alta": sum(1 for x in gargalos if x["severidade"] == "alta"),
    }
    return lista, gargalos, matriz, resumo


@app.route("/melhorias")
@admin_obrigatorio
def empresa_melhorias():
    import melhorias
    lista, gargalos, matriz, resumo = _contexto_melhorias(db.contas_da_empresa(con(), g.eu["empresa_id"]))
    return render_template("melhorias.html", lista=lista, gargalos=gargalos, matriz=matriz, resumo=resumo,
                           status_opcoes=melhorias.STATUS, areas=sorted({i["area"] for i in lista}),
                           c=None, editavel=True)


@app.route("/colaborador/<int:conta_id>/melhorias")
@login_obrigatorio
def colaborador_melhorias(conta_id):
    import melhorias
    c = _colaborador_visivel(conta_id)
    lista, gargalos, matriz, resumo = _contexto_melhorias([c])
    return render_template("melhorias.html", lista=lista, gargalos=gargalos, matriz=matriz, resumo=resumo,
                           status_opcoes=melhorias.STATUS, areas=[], c=c, editavel=g.eu["papel"] == "admin")


@app.route("/melhorias/status", methods=["POST"])
@admin_obrigatorio
def melhoria_status():
    import melhorias
    chave, status = request.form.get("chave", ""), request.form.get("status", "")
    if status in dict(melhorias.STATUS) and chave:
        db.salvar_status_melhoria(con(), g.eu["empresa_id"], chave[:80], status, g.eu["nome"])
        flash("Situação da sugestão atualizada.", "ok")
    volta = request.form.get("volta", "")
    return redirect((volta if volta.startswith("/") and not volta.startswith("//") else url_for("empresa_melhorias")) + "#s-" + chave)


# ---------------------------------------------------------------------- processos novos (fora do padrão)
def _reanalisar(c):
    """Refaz a análise do colaborador respeitando as decisões do gestor sobre processos novos e
    mantendo a documentação já escrita dos processos que continuam iguais."""
    import analise
    import documentador
    usuario = c["usuario_coleta"]
    dec = db.decisoes_processos(con(), c["empresa_id"], usuario)
    aprovados = {a for a, d in dec.items() if d["decisao"] == "fixo"}
    rejeitados = {a for a, d in dec.items() if d["decisao"] == "pontual"}
    antigo = db.carregar_resultado(con(), usuario) or {}
    docs = {}
    for p in antigo.get("processos", []):
        assin = p.get("assinatura") or (analise.assinatura(p["contextos"]) if p.get("contextos") else None)
        if assin and p.get("documento"):
            docs[assin] = p["documento"]
    r = analise.analisar(con(), usuario, aprovados=aprovados, rejeitados=rejeitados)
    for p in r["processos"]:
        if p["assinatura"] in docs:
            p["documento"] = docs[p["assinatura"]]
        if p["assinatura"] in aprovados:
            p["fixado_em"] = dec[p["assinatura"]]["ts"]
            p["fixado_por"] = dec[p["assinatura"]]["por"]
    funcao_antiga = antigo.get("descricao_funcao")
    documentador.documentar(r, usar_ia=True, contexto={"nome": c["nome"], "funcao": c["funcao"], "area": c["area"]})
    if funcao_antiga and funcao_antiga.get("gerado_por") == "Claude" and r["descricao_funcao"].get("gerado_por") != "Claude":
        novos_nomes = [p["documento"]["nome"] for p in r["processos"] if p["assinatura"] in aprovados]
        funcao_antiga = dict(funcao_antiga)
        funcao_antiga["responsabilidades"] = list(dict.fromkeys(
            (funcao_antiga.get("responsabilidades") or []) + novos_nomes))
        r["descricao_funcao"] = funcao_antiga
    for cand in r.get("candidatos", []):
        cand["nome_sugerido"] = documentador.nome_sugerido(cand)
    db.salvar_resultado(con(), usuario, r)
    return r


def _candidatos(contas):
    """Processos novos ainda sem decisão, de uma lista de colaboradores."""
    import documentador
    lista = []
    for c in contas:
        r = db.carregar_resultado(con(), c["usuario_coleta"])
        if not r:
            continue
        dec = db.decisoes_processos(con(), c["empresa_id"], c["usuario_coleta"])
        for cand in r.get("candidatos", []):
            if cand["assinatura"] in dec:
                continue
            cand.setdefault("nome_sugerido", documentador.nome_sugerido(cand))
            lista.append({"c": c, "p": cand})
    return lista


@app.route("/processos/novo/decidir", methods=["POST"])
@admin_obrigatorio
def decidir_processo_novo():
    c = _colaborador_visivel(int(request.form.get("conta_id", 0)))
    assin, decisao = request.form.get("assinatura", "")[:40], request.form.get("decisao")
    volta = request.form.get("volta", "")
    volta = volta if volta.startswith("/") and not volta.startswith("//") else url_for("empresa_processos")
    if decisao not in ("fixo", "pontual") or not assin:
        abort(400)
    r = db.carregar_resultado(con(), c["usuario_coleta"]) or {}
    cand = next((x for x in r.get("candidatos", []) if x["assinatura"] == assin), None)
    if not cand:
        flash("Esse processo novo não foi encontrado na análise atual.", "erro")
        return redirect(volta)
    db.salvar_decisao_processo(con(), c["empresa_id"], c["usuario_coleta"], assin, decisao, g.eu["nome"])
    novo = _reanalisar(c)
    if decisao == "fixo":
        p = next((x for x in novo["processos"] if x["assinatura"] == assin), None)
        flash(f"“{p['documento']['nome'] if p else 'Processo'}” agora é um processo fixo de {c['nome']}, com o passo a passo "
              f"no manual.", "ok")
        if p:
            return redirect(url_for("processo", conta_id=c["id"], pid=p["id"]))
    else:
        flash("Marcado como atividade pontual: não vai mais aparecer como processo novo.", "ok")
    return redirect(volta)


# ---------------------------------------------------------------------- API do agente
def _conta_do_token():
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    return db.conta_por_token(con(), token) if token else None


@app.route("/api/eventos", methods=["POST"])
def api_eventos():
    c = _conta_do_token()
    if not c:
        return jsonify(erro="Código de coleta inválido ou conta desativada."), 401
    dados = request.get_json(silent=True) or {}
    eventos = dados.get("eventos") or []
    if not isinstance(eventos, list) or len(eventos) > 5000:
        return jsonify(erro="Lote inválido."), 400
    import json as _json
    linhas = []
    for e in eventos:
        try:
            linhas.append((float(e["ts"]), c["usuario_coleta"], str(e["tipo"])[:20], (e.get("app") or None),
                           (e.get("titulo") or None),
                           _json.dumps(e["detalhe"], ensure_ascii=False) if e.get("detalhe") else None))
        except (KeyError, TypeError, ValueError):
            return jsonify(erro="Evento mal formado."), 400
    con().executemany("INSERT INTO eventos (ts, usuario, tipo, app, titulo, detalhe) VALUES (?, ?, ?, ?, ?, ?)", linhas)
    con().commit()
    return jsonify(recebidos=len(linhas))


@app.route("/api/consentimento", methods=["POST"])
def api_consentimento():
    c = _conta_do_token()
    if not c:
        return jsonify(erro="Código de coleta inválido ou conta desativada."), 401
    texto = (request.get_json(silent=True) or {}).get("texto", "")
    if not db.tem_consentimento(con(), c["usuario_coleta"]):
        db.registrar_consentimento(con(), c["usuario_coleta"], texto[:5000])
    return jsonify(ok=True, colaborador=c["nome"])


# ---------------------------------------------------------------------- executor (IA que opera o computador)
INSTRUCAO_MAX = 1000


def _pode_ver_comando(cmd):
    if not cmd or cmd["empresa_id"] != g.eu["empresa_id"]:
        abort(404)
    if g.eu["papel"] != "admin" and cmd["conta_id"] != g.eu["id"]:
        abort(403)
    return cmd


@app.route("/executor")
@login_obrigatorio
def executor():
    admin = g.eu["papel"] == "admin"
    cmds = db.comandos_da_empresa(con(), g.eu["empresa_id"], None if admin else g.eu["id"])
    equipe = [c for c in db.contas_da_empresa(con(), g.eu["empresa_id"]) if c["ativo"]] if admin else []
    return render_template("executor.html", comandos=cmds, equipe=equipe, ativo=db.executor_ativo(con(), g.eu["id"]),
                           servidor=request.host_url.rstrip("/"), tem_chave=bool(config.ANTHROPIC_API_KEY),
                           max_passos=config.EXECUTOR_MAX_PASSOS)


@app.route("/executor/ativar", methods=["POST"])
@login_obrigatorio
def executor_ativar():
    ativar = request.form.get("ativo") == "1"
    db.definir_executor_ativo(con(), g.eu["id"], ativar)
    flash("Executor liberado neste computador." if ativar else "Executor desligado: nenhum comando será executado.",
          "ok")
    return redirect(url_for("executor"))


@app.route("/executor/novo", methods=["POST"])
@login_obrigatorio
def executor_novo():
    instrucao = (request.form.get("instrucao") or "").strip()
    if len(instrucao) < 8 or len(instrucao) > INSTRUCAO_MAX:
        flash(f"Descreva a tarefa com 8 a {INSTRUCAO_MAX} caracteres.", "erro")
        return redirect(url_for("executor"))
    alvo = g.eu
    if g.eu["papel"] == "admin" and request.form.get("conta_id"):
        alvo = db.conta(con(), request.form.get("conta_id", type=int))
        if not alvo or alvo["empresa_id"] != g.eu["empresa_id"] or not alvo["ativo"]:
            abort(404)
    cid = db.criar_comando(con(), g.eu["empresa_id"], alvo["id"], g.eu["id"], instrucao)
    if alvo["id"] == g.eu["id"]:
        db.atualizar_comando(con(), cid, status="aprovado")   # o próprio dono pediu: já vale como aprovação
        flash("Comando na fila. Ele roda no seu computador assim que o executor local estiver aberto.", "ok")
    else:
        flash(f"Comando enviado para {alvo['nome']} aprovar. Nada roda antes da aprovação dela(e).", "ok")
    return redirect(url_for("executor"))


@app.route("/executor/<int:cmd_id>/decidir", methods=["POST"])
@login_obrigatorio
def executor_decidir(cmd_id):
    cmd = _pode_ver_comando(db.comando(con(), cmd_id))
    acao = request.form.get("acao")
    dono = cmd["conta_id"] == g.eu["id"]
    if acao in ("aprovar", "recusar") and dono and cmd["status"] == "aguardando":
        db.atualizar_comando(con(), cmd_id, status="aprovado" if acao == "aprovar" else "recusado",
                             **({} if acao == "aprovar" else {"fim_em": time.time()}))
    elif acao == "cancelar" and cmd["status"] in ("aguardando", "aprovado", "executando"):
        db.atualizar_comando(con(), cmd_id, status="cancelado", fim_em=time.time(), resumo="Cancelado pelo painel.")
    else:
        flash("Essa ação não está disponível para este comando.", "erro")
    return redirect(request.referrer or url_for("executor"))


@app.route("/executor/<int:cmd_id>")
@login_obrigatorio
def executor_detalhe(cmd_id):
    cmd = _pode_ver_comando(db.comando(con(), cmd_id))
    import json as _json
    log = [{"ts": r["ts"], "acao": _json.loads(r["acao"])} for r in db.log_do_comando(con(), cmd_id)]
    return render_template("executor_detalhe.html", cmd=cmd, log=log, dono=db.conta(con(), cmd["conta_id"]))


# --- API do executor local (autenticada pelo código pessoal do colaborador)
def _executor_conta():
    c = _conta_do_token()
    if not c:
        return None, (jsonify(erro="Código de coleta inválido ou conta desativada."), 401)
    if not db.executor_ativo(con(), c["id"]):
        return None, (jsonify(erro="O executor está desligado para esta conta. Libere em 'Executor' no painel."), 403)
    return c, None


def _comando_da_conta(c, cmd_id):
    cmd = db.comando(con(), cmd_id)
    return cmd if cmd and cmd["conta_id"] == c["id"] else None


@app.route("/api/executor/proximo", methods=["POST"])
def api_executor_proximo():
    c, erro = _executor_conta()
    if erro:
        return erro
    cmd = db.proximo_comando_aprovado(con(), c["id"])
    return jsonify(comando={"id": cmd["id"], "instrucao": cmd["instrucao"]} if cmd else None)


@app.route("/api/executor/iniciar", methods=["POST"])
def api_executor_iniciar():
    import executor_ia
    c, erro = _executor_conta()
    if erro:
        return erro
    d = request.get_json(silent=True) or {}
    cmd = _comando_da_conta(c, d.get("comando_id"))
    if not cmd or cmd["status"] != "aprovado":
        return jsonify(erro="Comando indisponível (não aprovado, já iniciado ou cancelado)."), 409
    try:
        executor_ia.iniciar(con(), cmd, int(d["tela_w"]), int(d["tela_h"]))
    except (KeyError, TypeError, ValueError):
        return jsonify(erro="Tamanho de tela inválido."), 400
    return jsonify(ok=True, max_passos=config.EXECUTOR_MAX_PASSOS)


@app.route("/api/executor/passo", methods=["POST"])
def api_executor_passo():
    import executor_ia
    c, erro = _executor_conta()
    if erro:
        return erro
    d = request.get_json(silent=True) or {}
    cmd = _comando_da_conta(c, d.get("comando_id"))
    if not cmd:
        return jsonify(erro="Comando não encontrado."), 404
    if cmd["status"] != "executando":
        return jsonify(fim=True, status=cmd["status"], resumo=cmd["resumo"] or "Comando interrompido pelo painel.")
    if not isinstance(d.get("screenshot"), str) or not d["screenshot"]:
        return jsonify(erro="Captura de tela ausente."), 400
    try:
        return jsonify(executor_ia.proximo_passo(con(), cmd["id"], d["screenshot"], d.get("tool_use_id")))
    except executor_ia.ErroExecutor as e:
        return jsonify(erro=str(e)), 400


@app.route("/api/executor/fim", methods=["POST"])
def api_executor_fim():
    c, erro = _executor_conta()
    if erro:
        return erro
    d = request.get_json(silent=True) or {}
    cmd = _comando_da_conta(c, d.get("comando_id"))
    if not cmd:
        return jsonify(erro="Comando não encontrado."), 404
    status = d.get("status") if d.get("status") in ("bloqueado", "falhou", "cancelado", "concluido") else "falhou"
    if cmd["status"] in ("aprovado", "executando"):
        db.atualizar_comando(con(), cmd["id"], status=status, resumo=str(d.get("resumo") or "")[:2000],
                             fim_em=time.time())
    return jsonify(ok=True)



@app.errorhandler(403)
def _proibido(_):
    return render_template("erro.html", titulo="Acesso restrito",
                           msg="Essa página é só para o administrador da empresa."), 403


@app.errorhandler(404)
def _nao_encontrado(_):
    return render_template("erro.html", titulo="Página não encontrada",
                           msg="O endereço não existe ou você não tem acesso a ele."), 404


def rodar(porta=5000, host="127.0.0.1"):
    print(f"Painel disponível em http://localhost:{porta}")
    if host == "0.0.0.0":
        print("Aberto na rede: os colaboradores acessam pelo IP deste computador.")
    app.run(host=host, port=porta, debug=False)
