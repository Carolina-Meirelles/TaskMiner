"""Sugestões de melhoria para os processos documentados.

Junta três fontes, todas a partir do que foi observado na coleta:
  1. Padrões de desperdício (regras deste módulo): informação copiada de um sistema para outro,
     exportação e importação manual, arquivo movido à mão, e-mail escrito do zero a cada execução,
     dados digitados em mais de um sistema.
  2. Gargalos detectados pela análise (etapa lenta, tempo instável, interrupções, digitação manual).
  3. Recomendações escritas na documentação (pelo Claude ou pelo gerador por regras).

Cada sugestão tem: impacto (horas por semana gastas hoje nas etapas envolvidas), esforço estimado
(baixo, médio, alto) e prioridade. O impacto é o tempo envolvido hoje, não uma promessa de economia.
"""
import hashlib

ESFORCO_TXT = {"baixo": "Esforço baixo", "medio": "Esforço médio", "alto": "Esforço alto"}
STATUS = [("nova", "Nova"), ("analise", "Em análise"), ("andamento", "Em andamento"),
          ("concluida", "Concluída"), ("descartada", "Descartada")]


def _chave(*partes):
    return hashlib.sha1("|".join(str(p) for p in partes).encode()).hexdigest()[:12]


def _textos(passo):
    return [a["texto"] for a in passo["acoes"]]


def _tem(passo, *termos):
    t = " ".join(_textos(passo)).lower()
    return any(x.lower() in t for x in termos)


def _horas(passos_idx, proc, dias):
    seg = sum(proc["passos"][k]["duracao_media_s"] for k in passos_idx)
    return round(seg * proc["ocorrencias"] / max(dias, 1) * 5 / 3600, 2)


def _prioridade(horas, esforco):
    horas = horas or 0
    if esforco == "baixo":
        return "rapido", "Ganho rápido"
    if horas >= 1:
        return "alto", "Alto impacto"
    return "avaliar", "Avaliar"


def _item(proc, tipo, titulo, etapas, detalhe, sugestao, esforco, horas, origem):
    chave_p, rot_p = _prioridade(horas, esforco)
    return {
        "chave": _chave(proc["documento"]["nome"], tipo, ",".join(map(str, etapas))),
        "tipo": tipo, "titulo": titulo, "etapas": [e + 1 for e in etapas],
        "detalhe": detalhe, "sugestao": sugestao, "origem": origem,
        "esforco": esforco, "esforco_txt": ESFORCO_TXT[esforco],
        "horas_semana": horas, "prioridade": chave_p, "prioridade_txt": rot_p,
    }


def gerar(proc, dias):
    """Lista de sugestões de um processo, da mais prioritária para a menos."""
    passos, itens = proc["passos"], []
    por_semana = round(proc["ocorrencias"] / max(dias, 1) * 5)

    # 1) copiar de um sistema e colar em outro
    for k in range(len(passos) - 1):
        a, b = passos[k], passos[k + 1]
        if a["app"] != b["app"] and _tem(a, "Ctrl+C") and _tem(b, "Ctrl+V"):
            itens.append(_item(
                proc, "copiar_colar", f"Informação copiada do {a['app']} e colada no {b['app']}", [k, k + 1],
                f"Nas etapas {k + 1} e {k + 2}, a informação passa do {a['app']} para o {b['app']} com copiar e colar, "
                f"cerca de {por_semana} vez(es) por semana.",
                f"Ligar o {b['app']} direto aos dados do {a['app']} (vínculo, importação ou integração), para que a "
                f"informação se atualize sem copiar e colar.", "medio", _horas([k, k + 1], proc, dias), "padrao"))

    # 2) exportar num sistema e importar/atualizar em outro
    for k, a in enumerate(passos):
        if not _tem(a, "Exportar"):
            continue
        for j in range(k + 1, len(passos)):
            b = passos[j]
            if b["app"] not in (a["app"], "Explorador de Arquivos") and _tem(b, "Importar", "Atualizar tudo", "Ctrl+V"):
                itens.append(_item(
                    proc, "exportar_importar", f"Exportação manual do {a['app']} para o {b['app']}", list(range(k, j + 1)),
                    f"Os dados saem do {a['app']} por exportação (etapa {k + 1}) e são carregados à mão no {b['app']} "
                    f"(etapa {j + 1}).",
                    f"Agendar a exportação ou conectar o {b['app']} direto à fonte (conector, API ou ferramenta de BI).",
                    "medio", _horas(range(k, j + 1), proc, dias), "padrao"))
                break

    # 3) arquivo movido à mão entre pastas
    moves = [k for k, p in enumerate(passos) if p["app"] == "Explorador de Arquivos" and _tem(p, "Ctrl+X", "Ctrl+V", "Recortar", "Colar")]
    if moves:
        itens.append(_item(
            proc, "mover_arquivo", "Arquivo movido à mão entre pastas", moves,
            f"Na(s) etapa(s) {', '.join(str(k + 1) for k in moves)}, um arquivo é recortado e colado em outra pasta "
            f"a cada execução.",
            "Configurar o navegador ou o sistema para salvar o arquivo direto na pasta de destino, ou usar uma "
            "regra simples de automação (Power Automate, script).", "baixo", _horas(moves, proc, dias), "padrao"))

    # 4) e-mail escrito do zero a cada execução
    for k, p in enumerate(passos):
        if p["app"].startswith("Outlook") and _tem(p, "Enviar") and _tem(p, "Corpo da mensagem", "Para"):
            itens.append(_item(
                proc, "email_manual", "E-mail escrito à mão a cada execução", [k],
                f"Na etapa {k + 1}, destinatários e texto do e-mail são digitados de novo toda vez "
                f"(cerca de {por_semana} por semana).",
                "Criar um modelo de e-mail (Etapas Rápidas ou Modelos do Outlook) com destinatários e texto prontos, "
                "ou gerar o e-mail automaticamente a partir do sistema.", "baixo", _horas([k], proc, dias), "padrao"))
            break

    # 5) dados digitados em mais de um sistema no mesmo processo
    ignorar = ("Para", "Corpo", "mensagem", "Localizar", "Buscar", "Título", "Observações", "Período")
    campos = {k: [t for t in _textos(p) if t.startswith("Preencher o campo") and not any(x in t for x in ignorar)]
              for k, p in enumerate(passos)}
    com_digitacao = [k for k, c in campos.items() if c]
    apps = {passos[k]["app"] for k in com_digitacao}
    if len(apps) >= 2 and sum(len(c) for c in campos.values()) >= 3:
        itens.append(_item(
            proc, "redigitacao", f"Dados digitados em {len(apps)} sistemas no mesmo processo", com_digitacao,
            f"Há preenchimento manual de campos em {', '.join(sorted(apps))}; provavelmente parte das informações "
            f"é a mesma, digitada mais de uma vez.",
            "Definir um sistema como origem dos dados e alimentar os outros a partir dele (integração ou "
            "importação), eliminando a redigitação e o risco de divergência.", "alto",
            _horas(com_digitacao, proc, dias), "padrao"))

    # 6) gargalos detectados
    esforco_g = {"etapa_lenta": "medio", "instavel": "medio", "interrupcoes": "baixo", "manual": "alto"}
    for g in proc.get("gargalos", []):
        it = _item(proc, "gargalo_" + g["tipo"], g["titulo"], [g["etapa"]], g["detalhe"], g["sugestao"],
                   esforco_g.get(g["tipo"], "medio"), g.get("horas_semana"), "gargalo")
        it["severidade"] = g["severidade"]
        itens.append(it)

    # 7) recomendações da documentação
    d = proc["documento"]
    autor = "Sugestão do Claude" if d.get("gerado_por") == "Claude" else "Sugestão da documentação"
    for texto in d.get("oportunidades_de_automacao", []) or []:
        itens.append(_item(proc, "doc", autor, [], texto, texto, "medio", None, "documentacao"))
        itens[-1]["chave"] = _chave(d["nome"], "doc", texto)

    ordem = {"alto": 0, "rapido": 1, "avaliar": 2}
    itens.sort(key=lambda i: (ordem[i["prioridade"]], -(i["horas_semana"] or 0)))
    return itens


def da_empresa(itens_colab):
    """itens_colab: [(conta, resultado, link_processo(pid))]. Junta e ordena as sugestões de todos."""
    lista = []
    for c, r, link in itens_colab:
        for p in r["processos"]:
            for it in gerar(p, r["periodo"]["dias"]):
                lista.append({**it, "processo": p["documento"]["nome"], "responsavel": c["nome"],
                              "conta_id": c["id"], "area": c["area"] or "Sem área definida", "link": link(p["id"]),
                              "chave": f"{c['id']}-{it['chave']}"})
        for texto in (r.get("descricao_funcao") or {}).get("recomendacoes", []) or []:
            lista.append({"chave": f"{c['id']}-{_chave('funcao', texto)}", "tipo": "funcao", "titulo": "Recomendação para a função" + (" (Claude)" if (r.get("descricao_funcao") or {}).get("gerado_por") == "Claude" else ""),
                          "etapas": [], "detalhe": texto, "sugestao": texto, "origem": "documentacao",
                          "esforco": "medio", "esforco_txt": ESFORCO_TXT["medio"], "horas_semana": None,
                          "prioridade": "avaliar", "prioridade_txt": "Avaliar", "processo": "Função como um todo",
                          "responsavel": c["nome"], "conta_id": c["id"], "area": c["area"] or "Sem área definida",
                          "link": None})
    ordem = {"alto": 0, "rapido": 1, "avaliar": 2}
    lista.sort(key=lambda i: (ordem[i["prioridade"]], -(i["horas_semana"] or 0)))
    return lista
