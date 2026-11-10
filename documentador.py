"""Transforma os processos detectados em documentação legível (POP) usando a API do Claude.

Sem chave de API configurada, gera a documentação por modelo (template), para o projeto
continuar funcionando offline.
"""
import json
import re

import config

PROMPT_PROCESSO = """Você é um analista de processos de negócio. Os dados abaixo foram coletados automaticamente
durante {dias} dias observando o computador de um colaborador{perfil}. Eles descrevem uma tarefa que ele repete.
Cada "passo" é uma tela de um sistema usada em sequência, com as ações que aparecem na maioria das execuções.
Em sites, "sistema" é o nome do site/sistema web identificado e "site" é o domínio; use o nome do sistema
nas instruções (ex.: "No CRM Vendas..."), não o nome do navegador.
Observação: por privacidade, o conteúdo digitado não é registrado (só o nome do campo); números viram "#",
e-mails viram "[email]" e partes variáveis do título viram "*".

DADOS OBSERVADOS:
{dados}

Escreva a documentação desse processo como um Procedimento Operacional Padrão (POP), em português do Brasil.
Responda APENAS com um JSON válido, sem texto antes ou depois, neste formato:
{{
  "nome": "nome curto do processo começando com verbo no infinitivo",
  "objetivo": "1 a 2 frases",
  "gatilho": "o que provavelmente dispara o processo",
  "responsavel": "cargo provável de quem executa",
  "passos": [{{"titulo": "título curto da etapa", "descricao": "1 a 2 frases de contexto da etapa", "sistema": "aplicativo",
              "subpassos": ["instrução curta no imperativo", "..."], "tempo": "tempo típico da etapa, ex.: cerca de 3 min"}}],
  "entradas": ["..."],
  "saidas": ["..."],
  "pontos_de_atencao": ["..."],
  "oportunidades_de_automacao": ["..."],
  "analise_gargalos": "1 a 3 frases interpretando os gargalos detectados (se houver) e qual atacar primeiro"
}}
Regras: baseie-se só nos dados; quando inferir algo, use "provavelmente"; agrupe ações pequenas em passos
compreensíveis (de 4 a 10 passos); não invente nomes de sistemas que não aparecem."""

PROMPT_FUNCAO = """Com base nos processos que um colaborador{perfil} executa (detectados automaticamente em {dias} dias
de observação do computador), escreva a descrição da função dele, em português do Brasil.
Se a função cadastrada for informada, use-a como cargo e aponte diferenças entre o cargo e o que foi observado.

PROCESSOS:
{processos}

TEMPO POR SISTEMA: {apps}
PERCENTUAL DO TEMPO ATIVO GASTO EM TAREFAS REPETITIVAS: {pct}%

Responda APENAS com um JSON válido:
{{
  "cargo_provavel": "...",
  "resumo": "parágrafo de 3 a 4 frases descrevendo a função",
  "responsabilidades": ["..."],
  "sistemas_utilizados": ["..."],
  "competencias": ["..."],
  "recomendacoes": ["sugestões para a gestão, ex.: automações, treinamentos"]
}}"""


# ---------------------------------------------------------------------- chamada ao Claude
def _claude(prompt, max_tokens=3000):
    if not config.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        resp = cliente.messages.create(
            model=config.CLAUDE_MODELO,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        texto = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        return _extrair_json(texto)
    except Exception as erro:
        print(f"  Aviso: falha ao chamar o Claude ({erro}). Usando documentação por modelo.")
        return None


def _extrair_json(texto):
    texto = re.sub(r"^```(?:json)?|```$", "", texto.strip(), flags=re.M).strip()
    inicio, fim = texto.find("{"), texto.rfind("}")
    return json.loads(texto[inicio:fim + 1])


# ---------------------------------------------------------------------- documentação por modelo
# Usada quando não há chave da API: transforma o que foi observado em um POP legível por regras.

# palavras encontradas nas telas/ações -> (nome do processo, objetivo)
TEMAS = [
    (("nf_", "nf ", "nota fiscal", "fatura recebida", "notas fiscais"), "Lançar notas fiscais de fornecedores",
     "Registrar no sistema as notas fiscais recebidas e manter o controle de notas atualizado."),
    (("auditoria",), "Responder pedidos da auditoria",
     "Separar os comprovantes pedidos pela auditoria, registrar a resposta e enviar os documentos."),
    (("concilia",), "Fazer a conciliação bancária",
     "Conferir os lançamentos do extrato bancário com os registros internos e comunicar o resultado."),
    (("despesas", "centro de custo"), "Gerar o relatório de despesas",
     "Consolidar as despesas do período e enviar o relatório aos responsáveis."),
    (("ordem do cliente", "pedido"), "Registrar pedidos de venda",
     "Transformar o pedido recebido do cliente em ordem de venda no sistema e confirmar com o cliente."),
    (("forecast", "funil", "previsão de vendas"), "Atualizar a previsão de vendas",
     "Atualizar a projeção de vendas a partir do funil comercial e compartilhar com a equipe."),
    (("metas",), "Apresentar o resultado de metas",
     "Levantar o resultado das metas do período e apresentar à liderança."),
    (("folha", "holerite", "ponto"), "Processar a folha e o ponto", "Conferir e processar os dados de ponto e folha."),
    (("boleto", "contas a pagar", "pagamento"), "Programar pagamentos", "Registrar e programar os pagamentos devidos."),
    (("cotação", "cotacao", "compra"), "Fazer cotações e compras", "Cotar e registrar as compras necessárias."),
    (("estoque", "inventário", "inventario"), "Controlar o estoque", "Atualizar e conferir as movimentações de estoque."),
    (("contrato",), "Gerir contratos", "Preparar, revisar e arquivar contratos."),
    (("chamado", "ticket"), "Atender chamados", "Registrar e responder os chamados recebidos."),
    (("cadastro", "cliente"), "Cadastrar clientes", "Cadastrar e atualizar os dados de clientes."),
    (("relatório", "relatorio"), "Elaborar relatório periódico", "Montar e enviar o relatório periódico."),
]
TELAS_GENERICAS = ("caixa de entrada", "documentos", "downloads", "(sem título)", "*", "chat", "nova guia")


def _tema(proc):
    texto = " ".join([p["tela"] for p in proc["passos"]] + [a["texto"] for p in proc["passos"] for a in p["acoes"]]).lower()
    for chaves, nome, objetivo in TEMAS:
        if any(k in texto for k in chaves):
            return nome, objetivo
    principal = max(proc["passos"], key=lambda p: p["duracao_media_s"])
    return f"Executar rotina em {principal['app']}", f"Rotina recorrente que passa por {', '.join(proc['aplicativos'])}."


def _imperativo(texto):
    """'Clicar em botão “Gravar”' -> 'Clique no botão “Gravar”'."""
    m = re.match(r"Clicar em (\w[\w ]*?) \(varia a cada execução — ex\.: (“.*”)\)$", texto)
    if m:
        return f"Selecione o {m.group(1)} correspondente à tarefa (ex.: {m.group(2)})"
    regras = [
        (r"^Clicar com o botão direito em (.+)$", r"Clique com o botão direito em \1"),
        (r"^Clicar em botão (.+)$", r"Clique no botão \1"),
        (r"^Clicar em link (.+)$", r"Clique no link \1"),
        (r"^Clicar em menu (.+)$", r"Abra o menu \1"),
        (r"^Clicar em aba (.+)$", r"Abra a aba \1"),
        (r"^Clicar em lista (.+)$", r"Escolha a opção na lista \1"),
        (r"^Clicar em item da lista (.+)$", r"Selecione o item \1"),
        (r"^Clicar em caixa de seleção (.+)$", r"Marque a caixa \1"),
        (r"^Clicar em (.+)$", r"Clique em \1"),
        (r"^Preencher o campo “Célula”$", "Preencha a linha da planilha com os dados"),
        (r"^Preencher o campo “Corpo da mensagem”$", "Escreva o texto da mensagem"),
        (r"^Preencher o campo “Para”$", "Informe os destinatários no campo “Para”"),
        (r"^Preencher o campo (.+)$", r"Preencha o campo \1"),
        (r"^Digitar texto$", "Digite as informações necessárias"),
        (r"^Usar o atalho Ctrl\+S \(Salvar\)$", "Salve o arquivo (Ctrl+S)"),
        (r"^Usar o atalho Ctrl\+C \(Copiar\)$", "Copie a informação (Ctrl+C)"),
        (r"^Usar o atalho Ctrl\+V \(Colar\)$", "Cole a informação (Ctrl+V)"),
        (r"^Usar o atalho Ctrl\+X \(Recortar\)$", "Recorte o arquivo (Ctrl+X)"),
        (r"^Usar o atalho Ctrl\+F \(Localizar\)$", "Abra a busca (Ctrl+F)"),
        (r"^Usar o atalho (.+)$", r"Use o atalho \1"),
        (r"^Pressionar Tab$", "Passe para o próximo campo (Tab)"),
        (r"^Pressionar Enter$", "Confirme com Enter"),
        (r"^Pressionar (.+)$", r"Pressione \1"),
    ]
    for padrao, troca in regras:
        if re.match(padrao, texto):
            return re.sub(padrao, troca, texto)
    return texto


def _titulo_etapa(p):
    tela, app = p["tela"], p["app"]
    acoes = " ".join(a["texto"] for a in p["acoes"]).lower()
    if app == "Outlook" and ("mensagem" in tela.lower() or "enviar" in acoes):
        assunto = re.sub(r"\s*-\s*Mensagem.*$", "", tela).replace("<data>", "do dia").replace("#", "nº")
        return f"Enviar o e-mail “{assunto}”"
    if app == "Outlook" and "anexo" in acoes:
        return "Abrir o e-mail e salvar os anexos"
    if app == "Outlook":
        return "Abrir o e-mail recebido"
    if app == "Explorador de Arquivos":
        if "colar" in acoes:
            return f"Colar o arquivo na pasta “{tela}”"
        if "recortar" in acoes:
            return f"Pegar o arquivo na pasta “{tela}”"
        return f"Abrir a pasta “{tela}”"
    if app == "Teams":
        return f"Compartilhar no Teams ({tela.split(' | ')[0]})"
    limpa = re.sub(r"\s*[:|-]\s*(Empresa #|Síntese|\*)\s*$", "", tela).replace("#", "nº").strip()
    if re.search(r"\.xls[xm]?$", limpa, re.I):
        return f"Atualizar a planilha “{limpa}”"
    if re.search(r"\.pptx?$", limpa, re.I):
        return f"Montar a apresentação “{limpa}”"
    if re.search(r"\.docx?$", limpa, re.I):
        return f"Editar o documento “{limpa}”"
    if re.search(r"\.pdf$", limpa, re.I):
        return f"Consultar o documento “{limpa}”"
    if p.get("navegador"):
        return f"Acessar “{limpa}” no {app}" if limpa and limpa.lower() != app.lower() else f"Acessar o {app}"
    if tela.lower().startswith(TELAS_GENERICAS) or not limpa:
        return f"Trabalhar no {app}"
    return f"{limpa} ({app})" if app.lower() not in limpa.lower() else limpa


def _fmt(s):
    s = int(round(s))
    return f"{s} s" if s < 60 else f"{s // 60} min {s % 60:02d} s" if s % 60 else f"{s // 60} min"


def _doc_modelo_processo(proc, contexto=None):
    nome, objetivo = _tema(proc)
    passos, entradas, saidas, atencao = [], [], [], []
    for k, p in enumerate(proc["passos"]):
        sub = [_imperativo(a["texto"]) for a in p["acoes"]]
        opcionais = [_imperativo(a["texto"]) for a in p["acoes"] if a["frequencia"] < 0.95]
        if not sub:
            sub = [f"Confira as informações exibidas em “{p['tela']}”"]
        tempo = f"cerca de {_fmt(p.get('mediana_s', p['duracao_media_s']))}"
        if p.get("navegador"):
            descricao = f"No {p['app']} ({p.get('site') or 'site'}, pelo {p['navegador']}), abra a página “{p['tela']}”."
        else:
            descricao = f"No {p['app']}, abra “{p['tela']}”."
        if opcionais:
            descricao += f" Algumas ações nem sempre são necessárias ({'; '.join(o[0].lower() + o[1:] for o in opcionais)})."
        passos.append({"titulo": _titulo_etapa(p), "descricao": descricao, "sistema": p["app"],
                       "subpassos": sub, "tempo": tempo})
        txt = " ".join(a["texto"] for a in p["acoes"]).lower()
        if "anexo" in txt and p["app"] == "Outlook" and k == 0:
            entradas.append("E-mail recebido com documento anexo")
        if "exportar" in txt and not entradas:
            entradas.append(f"Dados exportados do {p['app']}")
        if "salvar" in txt and p["app"] in ("Excel", "Word", "PowerPoint"):
            saidas.append(f"Arquivo “{p['tela']}” atualizado")
        if "gravar" in txt:
            saidas.append(f"Registro gravado no {p['app']}")
        if "enviar" in txt and p["app"] in ("Outlook",):
            saidas.append("E-mail enviado aos destinatários")
    if not entradas:
        entradas.append(f"Informações disponíveis no {proc['passos'][0]['app']} ao iniciar")
    for g in proc.get("gargalos", []):
        atencao.append(f"Etapa {g['etapa'] + 1}: {g['detalhe']}")
    gatilho = {
        "diaria": f"Rotina diária, normalmente por volta de {proc['horario_tipico']}"
                  + (" e repetida ao longo do dia conforme chegam as demandas." if proc["ocorrencias"] > 15 else "."),
        "semanal": f"Rotina semanal ({proc['frequencia'].split('— ')[-1]}), por volta de {proc['horario_tipico']}.",
    }.get(proc["tipo_frequencia"], f"Executado conforme a demanda ({proc['frequencia']}).")
    if entradas and entradas[0].startswith("E-mail recebido"):
        gatilho = "Chegada de e-mail com documento anexo. " + gatilho
    automacao = []
    if proc["tipo_frequencia"] == "diaria" and proc["ocorrencias"] >= 20:
        automacao.append("Processo frequente e com passos estáveis: bom candidato a automação (RPA) ou integração.")
    if any(g["tipo"] == "manual" for g in proc.get("gargalos", [])):
        automacao.append("Evitar a redigitação de dados entre sistemas com importação automática ou integração.")
    return {
        "nome": nome, "objetivo": objetivo, "gatilho": gatilho,
        "responsavel": (contexto or {}).get("funcao") or "Colaborador observado",
        "passos": passos, "entradas": list(dict.fromkeys(entradas)), "saidas": list(dict.fromkeys(saidas)),
        "pontos_de_atencao": atencao, "oportunidades_de_automacao": automacao,
    }


def _doc_modelo_funcao(resultado, contexto=None):
    procs = resultado["processos"]
    cargo = (contexto or {}).get("funcao")
    nomes = [p["documento"]["nome"] for p in procs]
    diarios = [p["documento"]["nome"].lower() for p in procs if p["tipo_frequencia"] == "diaria"]
    semanais = [p["documento"]["nome"].lower() for p in procs if p["tipo_frequencia"] == "semanal"]
    resumo = (f"Durante {resultado['periodo']['dias']} dias foram identificados {len(procs)} processos recorrentes, "
              f"que ocupam {str(resultado['estatisticas']['percentual_repetitivo']).replace('.', ',')}% do tempo ativo.")
    if diarios:
        resumo += f" No dia a dia, a função envolve {', '.join(diarios)}."
    if semanais:
        resumo += f" Semanalmente, é responsável por {', '.join(semanais)}."
    return {
        "cargo_provavel": cargo or "Não identificado",
        "resumo": resumo,
        "responsabilidades": nomes,
        "sistemas_utilizados": [a["app"] for a in resultado["estatisticas"]["tempo_por_app"]],
        "competencias": [],
        "recomendacoes": [f"Atacar o gargalo “{g['titulo'].lower()}” em {p['documento']['nome'].lower()}."
                          for p in procs for g in p.get("gargalos", [])[:1] if g["severidade"] == "alta"],
    }


# ---------------------------------------------------------------------- pipeline
def _resumo_para_ia(proc):
    return json.dumps({
        "frequencia": proc["frequencia"],
        "execucoes_observadas": proc["ocorrencias"],
        "horario_tipico": proc["horario_tipico"],
        "duracao_media": proc["duracao_media"],
        "passos": [{"sistema": p["app"], "site": p.get("site"), "navegador": p.get("navegador"), "tela": p["tela"], "tempo_medio_s": p["duracao_media_s"],
                    "tempo_normal_s": p.get("mediana_s"), "tempo_p90_s": p.get("p90_s"),
                    "acoes": [a["texto"] for a in p["acoes"]]} for p in proc["passos"]],
        "gargalos_detectados": [{"etapa": g["etapa"] + 1, "tipo": g["titulo"], "evidencia": g["detalhe"]}
                                for g in proc.get("gargalos", [])],
    }, ensure_ascii=False, indent=2)


def _perfil(contexto):
    if not contexto:
        return ""
    partes = [f"função cadastrada: {contexto['funcao']}" if contexto.get("funcao") else "",
              f"área: {contexto['area']}" if contexto.get("area") else ""]
    partes = [p for p in partes if p]
    return f" ({'; '.join(partes)})" if partes else ""


def nome_sugerido(proc):
    """Nome provável de um processo ainda não documentado (ex.: um processo novo detectado)."""
    return _tema(proc)[0]


def documentar(resultado, usar_ia=True, contexto=None):
    """contexto: dados cadastrados do colaborador (nome, funcao, area), quando houver."""
    dias = resultado["periodo"]["dias"]
    perfil = _perfil(contexto)
    ia = usar_ia and bool(config.ANTHROPIC_API_KEY)
    if usar_ia and not ia:
        print("  ANTHROPIC_API_KEY não configurada: gerando documentação por modelo.")

    for proc in resultado["processos"]:
        if proc.get("documento"):            # já documentado antes (ex.: reanálise): não refaz nem gasta API
            continue
        doc = _claude(PROMPT_PROCESSO.format(dias=dias, perfil=perfil, dados=_resumo_para_ia(proc))) if ia else None
        proc["documento"] = doc or _doc_modelo_processo(proc, contexto)
        proc["documento"]["gerado_por"] = "Claude" if doc else "modelo automático"
        print(f"  {proc['id']}: {proc['documento']['nome']}")

    funcao = None
    if ia and resultado["processos"]:
        lista = "\n".join(f"- {p['documento']['nome']} ({p['frequencia']}, ~{p['duracao_media']} por execução): "
                          f"{p['documento'].get('objetivo', '')}" for p in resultado["processos"])
        apps = ", ".join(f"{a['app']} {a['texto']}" for a in resultado["estatisticas"]["tempo_por_app"])
        funcao = _claude(PROMPT_FUNCAO.format(dias=dias, perfil=perfil, processos=lista, apps=apps,
                                              pct=resultado["estatisticas"]["percentual_repetitivo"]))
    resultado["descricao_funcao"] = funcao or _doc_modelo_funcao(resultado, contexto)
    resultado["descricao_funcao"]["gerado_por"] = "Claude" if funcao else "modelo automático"
    return resultado


# ---------------------------------------------------------------------- exportação
def exportar_markdown(resultado, nome=None, funcao=None, area=None):
    f, est = resultado["descricao_funcao"], resultado["estatisticas"]
    linhas = [
        f"# Manual de Processos — {nome or resultado['usuario']}",
        "",
    ]
    if funcao or area:
        linhas += [f"**Função cadastrada:** {funcao or '-'} · **Área:** {area or '-'}", ""]
    linhas += [
        f"Período observado: {resultado['periodo']['inicio']} a {resultado['periodo']['fim']} "
        f"({resultado['periodo']['dias']} dias com atividade). Tempo ativo médio: {est['media_diaria']} por dia. "
        f"Tarefas repetitivas: {est['percentual_repetitivo']}% do tempo ativo.",
        "",
        "## Descrição da função",
        "",
        f"**Cargo provável:** {f.get('cargo_provavel', '-')}",
        "",
        f.get("resumo", ""),
        "",
    ]
    for titulo, chave in [("Responsabilidades", "responsabilidades"), ("Sistemas utilizados", "sistemas_utilizados"),
                          ("Competências", "competencias"), ("Recomendações", "recomendacoes")]:
        if f.get(chave):
            linhas += [f"**{titulo}:**", ""] + [f"- {x}" for x in f[chave]] + [""]

    linhas += ["## Rotina diária", "", "| Horário típico | Processo | Frequência |", "|---|---|---|"]
    por_id = {p["id"]: p for p in resultado["processos"]}
    for r in resultado["rotina"]:
        linhas.append(f"| {r['horario']} | {por_id[r['id']]['documento']['nome']} | {r['frequencia']} |")
    linhas.append("")

    for p in resultado["processos"]:
        d = p["documento"]
        linhas += [
            f"## {d['nome']}", "",
            f"- **Objetivo:** {d.get('objetivo', '-')}",
            f"- **Quando fazer:** {d.get('gatilho', '-')}",
            f"- **Frequência:** {p['frequencia']} (horário típico {p['horario_tipico']}, entre {p['janela_horario']})",
            f"- **Duração média:** {p['duracao_media']} — {p['ocorrencias']} execuções observadas, {p['tempo_total']} no total",
            f"- **Sistemas:** {', '.join(p['aplicativos'])}", "",
        ]
        if p.get("gargalos"):
            linhas += ["### Gargalos identificados", ""]
            for g in p["gargalos"]:
                impacto = f" Impacto: {str(g['horas_semana']).replace('.', ',')} h {g['metrica']}." if g.get("horas_semana") else ""
                linhas.append(f"- **[{'Alta' if g['severidade'] == 'alta' else 'Média'}] {g['titulo']}** — {g['detalhe']}{impacto} "
                              f"*Sugestão:* {g['sugestao']}")
            if d.get("analise_gargalos"):
                linhas += ["", d["analise_gargalos"]]
            linhas.append("")
        linhas += ["### Passo a passo", ""]
        for k, passo in enumerate(d["passos"], 1):
            tempo = f" · {passo['tempo']}" if passo.get("tempo") else ""
            linhas.append(f"{k}. **{passo['titulo']}** ({passo.get('sistema', '')}{tempo})")
            if passo.get("descricao"):
                linhas.append(f"   {passo['descricao']}")
            for j, sp in enumerate(passo.get("subpassos") or [], 1):
                linhas.append(f"   {k}.{j}. {sp}")
        linhas.append("")
        for titulo, chave in [("Entradas", "entradas"), ("Saídas", "saidas"),
                              ("Pontos de atenção", "pontos_de_atencao"),
                              ("Oportunidades de automação", "oportunidades_de_automacao")]:
            if d.get(chave):
                linhas += [f"**{titulo}:**", ""] + [f"- {x}" for x in d[chave]] + [""]
    return "\n".join(linhas)


def aplicar_docs_demo(resultado, email):
    """Na Empresa Demo sem chave de API, usa a documentação de exemplo escrita pelo Claude
    (docs_demo.json) para os processos simulados. Retorna True se aplicou."""
    from pathlib import Path
    arq = Path(__file__).resolve().parent / "docs_demo.json"
    if not arq.exists():
        return False
    pacote = json.loads(arq.read_text(encoding="utf-8")).get(email)
    if not pacote:
        return False
    aplicou = False
    for proc in resultado["processos"]:
        doc = pacote["processos"].get(proc["id"])
        if doc and _tema(proc)[0].split()[0] == doc["nome"].split()[0]:   # confere que é o mesmo processo
            proc["documento"] = {**doc, "gerado_por": "Claude"}
            aplicou = True
    if aplicou and pacote.get("funcao"):
        resultado["descricao_funcao"] = {**pacote["funcao"], "gerado_por": "Claude"}
    return aplicou
