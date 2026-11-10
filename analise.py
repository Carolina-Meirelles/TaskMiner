"""Análise dos eventos: identifica tarefas repetidas e monta o passo a passo de cada uma.

Etapas do algoritmo (task mining):
  1. Segmentação  — eventos viram "segmentos": períodos contínuos numa mesma janela,
                    com as ações (cliques, digitação, atalhos) feitas nela.
  2. Generalização — títulos são normalizados ("NF_4521.pdf" -> "NF_#.pdf") e partes do
                    título que variam muito (nome de cliente, assunto) viram "*".
                    Assim, cada segmento ganha um "contexto" (aplicativo + tipo de tela).
  3. Mineração    — busca sequências de contextos que se repetem em vários dias
                    (n-gramas de 3 a 8 etapas), escolhendo de forma gulosa as que
                    cobrem mais tempo/ocorrências sem sobreposição.
  4. Consolidação — para cada processo, as ações que aparecem em 50%+ das execuções
                    formam o passo a passo; calcula frequência, duração e horário típico.
"""
import json
import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

import config
import db
import sistemas
from privacidade import mascarar

TIPOS_ELEMENTO = {
    "Button": "botão", "SplitButton": "botão", "MenuItem": "menu", "TabItem": "aba",
    "ListItem": "item da lista", "Hyperlink": "link", "Edit": "campo", "CheckBox": "caixa de seleção",
    "ComboBox": "lista", "TreeItem": "item", "DataItem": "célula", "RadioButton": "opção",
    "Document": "documento", "Text": "texto", "Image": "imagem",
}

DIAS_SEMANA = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

_SUFIXOS = re.compile(
    r"\s+[-–—|]\s+(Google Chrome|Microsoft​? Edge|Mozilla Firefox|Excel|Word|PowerPoint|Outlook|"
    r"Microsoft Teams|Adobe Acrobat.*|Bloco de Notas|Notepad|Visual Studio Code)\s*$",
    re.I,
)
_PREFIXOS_EMAIL = re.compile(r"^((RE|RES|ENC|ENCAM|FW|FWD)\s*:\s*)+", re.I)
_SEPARADOR = re.compile(r"\s+[-–—|]\s+")


# ---------------------------------------------------------------------- utilitários
def nome_app(exe, titulo="", detalhe=None):
    """Nome do sistema usado (ex.: 'CRM Vendas', 'Gmail', 'SAP'), e não só do programa."""
    d = detalhe or {}
    return sistemas.identificar(exe, titulo, d.get("dominio"), d.get("trecho"), d.get("produto"))[0]


def normalizar_titulo(titulo):
    t = mascarar(titulo or "")
    for _ in range(2):
        t = _SUFIXOS.sub("", t)
    t = _PREFIXOS_EMAIL.sub("", t)
    t = re.sub(r"^\(\d+\)\s*", "", t)                                   # contadores "(3) Caixa..."
    t = re.sub(r"\b\d{1,2}[/.-]\d{1,2}(?:[/.-]\d{2,4})?\b", "<data>", t)
    t = re.sub(r"\d+", "#", t)
    t = re.sub(r"\s+", " ", t).strip(" -|")
    return t[:100] or "(sem título)"


def normalizar_nome(nome):
    n = re.sub(r"\d+", "#", mascarar(nome or "")).strip()
    return n[:60]


def dia_de(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def fmt_duracao(seg):
    seg = int(round(seg))
    if seg < 60:
        return f"{seg}s"
    if seg < 3600:
        return f"{seg // 60}min {seg % 60:02d}s"
    return f"{seg // 3600}h {(seg % 3600) // 60:02d}min"


# ---------------------------------------------------------------------- 1. segmentação
@dataclass
class Segmento:
    dia: str
    inicio: float
    fim: float
    app: str                                    # sistema (ex.: "CRM Vendas", "Excel")
    titulo_norm: str
    navegador: str = None                       # navegador usado, quando é um site
    site: str = None                            # domínio do site
    acoes: list = field(default_factory=list)   # (ts, chave, texto)
    contexto: str = ""

    @property
    def duracao(self):
        return max(0.0, self.fim - self.inicio)


def descrever_acao(tipo, det):
    """Converte um evento em (chave, texto legível). Retorna None se não for útil no passo a passo."""
    if tipo == "clique":
        nome = normalizar_nome(det.get("elemento"))
        if not nome:
            return None
        tipo_el = TIPOS_ELEMENTO.get(det.get("tipo_elemento"), "elemento")
        verbo = "Clicar com o botão direito em" if det.get("botao") == "right" else "Clicar em"
        return f"clique|{tipo_el}|{nome}", f"{verbo} {tipo_el} “{nome}”"
    if tipo == "digitacao":
        campo = normalizar_nome(det.get("campo"))
        texto = f"Preencher o campo “{campo}”" if campo else "Digitar texto"
        return f"digitacao|{campo}", texto
    if tipo == "atalho":
        combo, acao = det.get("combinacao", "?"), det.get("acao")
        return f"atalho|{combo}", f"Usar o atalho {combo}" + (f" ({acao})" if acao else "")
    if tipo == "tecla":
        return f"tecla|{det.get('tecla')}", f"Pressionar {det.get('tecla')}"
    return None


def construir_segmentos(eventos):
    segmentos, atual, ultimo_ts = [], None, None

    def fechar(ts):
        nonlocal atual
        if atual is not None:
            atual.fim = ts
            segmentos.append(atual)
            atual = None

    for e in eventos:
        ts, tipo = e["ts"], e["tipo"]
        ultimo_ts = ts
        det = json.loads(e["detalhe"]) if e["detalhe"] else {}
        if tipo == "foco":
            fechar(ts)
            sistema, navegador = sistemas.identificar(e["app"], e["titulo"], det.get("dominio"),
                                                      det.get("trecho"), det.get("produto"))
            tela = normalizar_titulo(e["titulo"])
            if navegador:   # "CRM Vendas - Oportunidades" no sistema "CRM Vendas" -> tela "Oportunidades"
                resto = [p for p in _SEPARADOR.split(tela) if p.strip() and p.strip().lower() != sistema.lower()]
                tela = " - ".join(resto) if resto else tela
            atual = Segmento(dia=dia_de(ts), inicio=ts, fim=ts, app=sistema, titulo_norm=tela,
                             navegador=navegador, site=det.get("dominio"))
        elif tipo in ("ocioso", "pausa"):
            fechar(ts)
        elif atual is not None:
            acao = descrever_acao(tipo, det)
            if acao:
                atual.acoes.append((ts, *acao))
    if ultimo_ts is not None:
        fechar(ultimo_ts)
    return [s for s in segmentos if s.duracao >= config.DURACAO_MINIMA_SEGMENTO or s.acoes]


# ---------------------------------------------------------------------- 2. generalização
def generalizar(segmentos):
    """Define o contexto de cada segmento, trocando partes variáveis do título por '*'."""
    partes = lambda t: [p.strip() for p in _SEPARADOR.split(t) if p.strip()]
    dias_por_parte = defaultdict(set)
    for s in segmentos:
        for p in set(partes(s.titulo_norm)):
            dias_por_parte[(s.app, p)].add(s.dia)

    for s in segmentos:
        modelo = []
        for p in partes(s.titulo_norm):
            p = p if len(dias_por_parte[(s.app, p)]) >= config.MIN_DIAS else "*"
            if not (p == "*" and modelo and modelo[-1] == "*"):
                modelo.append(p)
        s.contexto = f"{s.app} | {' - '.join(modelo) or '*'}"

    # junta segmentos consecutivos com o mesmo contexto (ex.: alternou entre duas planilhas iguais)
    mesclados = []
    for s in segmentos:
        ant = mesclados[-1] if mesclados else None
        if ant and ant.dia == s.dia and ant.contexto == s.contexto and s.inicio - ant.fim < 60:
            ant.fim = s.fim
            ant.acoes.extend(s.acoes)
        else:
            mesclados.append(s)
    return mesclados


# ---------------------------------------------------------------------- 3. mineração
def _sem_sobreposicao(ocorrencias, n, coberto=None):
    resultado, fim_por_dia = [], {}
    for dia, i in ocorrencias:
        if i < fim_por_dia.get(dia, -1):
            continue
        if coberto and any(j in coberto[dia] for j in range(i, i + n)):
            continue
        resultado.append((dia, i))
        fim_por_dia[dia] = i + n
    return resultado


def _e_processo(ocorrencias, n):
    dias = len({d for d, _ in ocorrencias})
    if len(ocorrencias) >= config.MIN_OCORRENCIAS and dias >= config.MIN_DIAS:
        return True
    return n >= config.TAMANHO_LONGO and len(ocorrencias) >= config.MIN_OCORRENCIAS_LONGO and dias >= 2


def _coesao(padrao, pares, saidas, entradas):
    """Quão "amarradas" são as etapas: para cada transição A->B, a maior entre
    P(B vem depois de A) e P(A vem antes de B). Retorna a transição mais fraca.
    Atividades soltas (ruído) se combinam ao acaso e têm coesão baixa."""
    valores = []
    for a, b in zip(padrao, padrao[1:]):
        n = pares[(a, b)]
        valores.append(max(n / saidas[a] if saidas[a] else 0, n / entradas[b] if entradas[b] else 0))
    return min(valores) if valores else 0


def _bordas_firmes(padrao, pares, saidas, entradas):
    """Para processos com poucas repetições (ex.: semanais), a primeira e a última transição
    precisam ser fortes NOS DOIS sentidos; senão uma tela qualquer, aberta por acaso logo
    antes ou depois nas duas semanas, seria incluída no processo."""
    for a, b in (padrao[:2], padrao[-2:]):
        n = pares[(a, b)]
        if min(n / saidas[a] if saidas[a] else 0, n / entradas[b] if entradas[b] else 0) < config.COESAO_MIN:
            return False
    return True


def assinatura(padrao):
    """Identificador estável de uma sequência de telas (usado para guardar a decisão do gestor)."""
    import hashlib
    return hashlib.sha1("||".join(padrao).encode()).hexdigest()[:12]


def minerar_padroes(por_dia, aprovados=None, rejeitados=None):
    """Retorna (processos, novos).

    processos: sequências que passam nos critérios (ou que o gestor já aprovou como processo fixo).
    novos: sequências que se repetem, com etapas bem ligadas, mas ainda pouco para virar processo
           sozinhas: o TaskMiner pergunta ao gestor se devem virar processo fixo.
    """
    aprovados, rejeitados = aprovados or set(), rejeitados or set()
    ocorrencias = defaultdict(list)
    pares, saidas, entradas = Counter(), Counter(), Counter()
    for dia in sorted(por_dia):
        ctx = [s.contexto for s in por_dia[dia]]
        for a, b in zip(ctx, ctx[1:]):
            pares[(a, b)] += 1
            saidas[a] += 1
            entradas[b] += 1
        for n in range(config.TAMANHO_MIN_PADRAO, config.TAMANHO_MAX_PADRAO + 1):
            for i in range(len(ctx) - n + 1):
                padrao = tuple(ctx[i:i + n])
                if len(set(padrao)) >= 2:
                    ocorrencias[padrao].append((dia, i))

    candidatos, quase = [], []
    for padrao, occ in ocorrencias.items():
        aprovado = assinatura(padrao) in aprovados
        if not aprovado and _coesao(padrao, pares, saidas, entradas) < config.COESAO_MIN:
            continue
        o = _sem_sobreposicao(occ, len(padrao))
        firmes = _bordas_firmes(padrao, pares, saidas, entradas)
        if aprovado:
            candidatos.append((10 ** 6 + len(padrao) * len(o), padrao, occ, True))
        elif len(o) < config.MIN_OCORRENCIAS and not firmes:
            continue
        elif _e_processo(o, len(padrao)):
            candidatos.append((len(padrao) * len(o), padrao, occ, False))
        elif (len(o) >= config.NOVO_MIN_OCORRENCIAS and len({d for d, _ in o}) >= 2 and firmes
              and assinatura(padrao) not in rejeitados):
            quase.append((len(padrao) * len(o), padrao, occ))
    candidatos.sort(key=lambda c: (-c[0], -len(c[1])))

    coberto, escolhidos = defaultdict(set), []
    for _, padrao, occ, aprovado in candidatos:
        # uma sequência formada só por telas de um processo já escolhido é um pedaço ou uma
        # "rotação" dele (ex.: começar no meio de um ciclo repetido) e não um processo novo
        if any(set(padrao) <= set(esc) for esc, _ in escolhidos):
            continue
        o = _sem_sobreposicao(occ, len(padrao), coberto)
        if not (aprovado and o) and not _e_processo(o, len(padrao)):
            continue
        escolhidos.append((padrao, o))
        for dia, i in o:
            coberto[dia].update(range(i, i + len(padrao)))

    # processos novos: o mais completo primeiro; ignora pedaços de processos já conhecidos ou de outro novo
    quase.sort(key=lambda c: (-len(c[1]), -c[0]))
    novos = []
    for _, padrao, occ in quase:
        if any(set(padrao) <= set(esc) for esc, _ in escolhidos + novos):
            continue
        o = _sem_sobreposicao(occ, len(padrao), coberto)
        if len(o) < config.NOVO_MIN_OCORRENCIAS or len({d for d, _ in o}) < 2:
            continue
        novos.append((padrao, o))
    return escolhidos, novos[:config.NOVO_MAX_SUGESTOES]


# ---------------------------------------------------------------------- 4. consolidação
def _frequencia(occ, dias_monitorados, inicios):
    dias = sorted({d for d, _ in occ})
    if len(dias) >= 0.7 * len(dias_monitorados):
        por_dia = len(occ) / len(dias)
        vezes = "1 vez" if round(por_dia) <= 1 else f"cerca de {round(por_dia)} vezes"
        return "diaria", f"Diária — {vezes} por dia"
    dias_semana = {datetime.fromtimestamp(t).weekday() for t in inicios}
    if len(dias_semana) == 1:
        return "semanal", f"Semanal — às {DIAS_SEMANA[dias_semana.pop()]}s"
    return "recorrente", f"Recorrente — {len(occ)} vezes em {len(dias)} dos {len(dias_monitorados)} dias"


def _percentil(valores, q):
    v = sorted(valores)
    if not v:
        return 0
    pos = (len(v) - 1) * q
    i = int(pos)
    return v[i] + (v[min(i + 1, len(v) - 1)] - v[i]) * (pos - i)


def _estatisticas_etapa(duracoes):
    return {
        "mediana_s": round(_percentil(duracoes, .5)),
        "p25_s": round(_percentil(duracoes, .25)),
        "p75_s": round(_percentil(duracoes, .75)),
        "p90_s": round(_percentil(duracoes, .9)),
        "min_s": round(min(duracoes)),
        "max_s": round(max(duracoes)),
    }


def _interrupcoes(padrao, por_dia):
    """Conta execuções em que o colaborador saiu do processo no meio (abriu outra tela que não faz
    parte dele) e depois voltou para terminar. Retorna {etapa_depois_da_qual_saiu: quantidade}."""
    n, resultado = len(padrao), Counter()
    for segs in por_dia.values():
        ctx = [s.contexto for s in segs]
        for i in range(len(ctx) - n):
            janela = ctx[i:i + n + 1]
            for j in range(1, n):
                if janela[j] not in padrao and tuple(janela[:j] + janela[j + 1:]) == padrao:
                    resultado[j - 1] += 1
                    break
    return {str(k): v for k, v in resultado.items()}


def detectar_gargalos(proc, dias_monitorados):
    """Regras que apontam onde o processo perde tempo. Cada gargalo traz a etapa, a evidência
    medida nos dados e uma sugestão de ação."""
    gargalos = []
    passos, n_exec = proc["passos"], proc["ocorrencias"]
    if n_exec < 2:
        return gargalos
    total_medio = sum(p["duracao_media_s"] for p in passos) or 1
    por_semana = n_exec / dias_monitorados * 5

    # 1. etapa que concentra o tempo do processo
    k = max(range(len(passos)), key=lambda i: passos[i]["duracao_media_s"])
    fatia = passos[k]["duracao_media_s"] / total_medio
    if fatia >= config.GARGALO_FATIA_ETAPA and len(passos) >= 3:
        p = passos[k]
        gargalos.append({
            "tipo": "etapa_lenta", "titulo": "Etapa concentra o tempo do processo",
            "etapa": k, "severidade": "alta" if fatia >= 0.5 else "media",
            "detalhe": f"A etapa {k + 1} ({p['app']}) leva em média {fmt_duracao(p['duracao_media_s'])}, "
                       f"{round(fatia * 100)}% do tempo de cada execução.",
            "sugestao": "Verifique se há espera pelo sistema, conferência manual ou informação faltando "
                        "nessa etapa; é o ponto com mais retorno para simplificar ou automatizar.",
            "horas_semana": round(p["duracao_media_s"] * por_semana / 3600, 2),
            "metrica": "por semana nesta etapa",
        })

    # 2. etapas com tempo instável (algumas execuções demoram muito mais que o normal)
    for k, p in enumerate(passos):
        if p["mediana_s"] < 20 or n_exec < 4:
            continue
        razao = p["p90_s"] / p["mediana_s"]
        if razao >= config.GARGALO_VARIACAO:
            excedente = sum(max(0, ex[2][k] - p["mediana_s"]) for ex in proc["execucoes"])
            gargalos.append({
                "tipo": "instavel", "titulo": "Tempo instável",
                "etapa": k, "severidade": "alta" if razao >= 3 else "media",
                "detalhe": f"Na etapa {k + 1} ({p['app']}) o normal é {fmt_duracao(p['mediana_s'])}, mas 1 em cada 10 "
                           f"execuções passa de {fmt_duracao(p['p90_s'])} (até {fmt_duracao(p['max_s'])}).",
                "sugestao": "Picos assim costumam vir de lentidão do sistema, casos fora do padrão ou dependência "
                            "de outra pessoa. Vale registrar quando acontece para achar a causa.",
                "horas_semana": round(excedente / dias_monitorados * 5 / 3600, 2),
                "metrica": "por semana acima do tempo normal",
            })

    # 3. interrupções no meio do processo
    total_int = sum(proc["interrupcoes"].values())
    taxa = total_int / (n_exec + total_int)
    if total_int >= 2 and taxa >= config.GARGALO_INTERRUPCOES:
        k = int(max(proc["interrupcoes"], key=proc["interrupcoes"].get))
        gargalos.append({
            "tipo": "interrupcoes", "titulo": "Interrupções frequentes",
            "etapa": k, "severidade": "alta" if taxa >= 0.25 else "media",
            "detalhe": f"Em {round(taxa * 100)}% das vezes ({total_int} execuções) o colaborador saiu do processo "
                       f"no meio, principalmente depois da etapa {k + 1} ({passos[k]['app']}).",
            "sugestao": "Interrupções aumentam o tempo e o risco de erro. Veja se falta alguma informação nesse "
                        "ponto ou se o processo pode ser feito em blocos, sem pausas.",
            "horas_semana": None, "metrica": None,
        })

    # 4. muita digitação manual numa mesma etapa
    for k, p in enumerate(passos):
        campos = [a for a in p["acoes"] if a["texto"].startswith("Preencher o campo")]
        if len(campos) >= config.GARGALO_CAMPOS_MANUAIS:
            gargalos.append({
                "tipo": "manual", "titulo": "Digitação manual repetitiva",
                "etapa": k, "severidade": "alta" if proc["tipo_frequencia"] == "diaria" else "media",
                "detalhe": f"A etapa {k + 1} ({p['app']}) tem {len(campos)} campos preenchidos à mão em toda "
                           f"execução, cerca de {round(por_semana)} vezes por semana.",
                "sugestao": "Dados digitados de novo a cada execução são candidatos a importação automática, "
                            "integração entre sistemas ou um robô (RPA).",
                "horas_semana": round(p["duracao_media_s"] * por_semana / 3600, 2),
                "metrica": "por semana nesta etapa",
            })

    ordem = {"alta": 0, "media": 1}
    gargalos.sort(key=lambda g: (ordem[g["severidade"]], -(g["horas_semana"] or 0)))
    return gargalos


def descrever_processo(pid, padrao, occ, por_dia, dias_monitorados):
    n = len(padrao)
    instancias = [por_dia[d][i:i + n] for d, i in occ]
    passos = []
    for p in range(n):
        segs = [inst[p] for inst in instancias]
        contagem, posicoes, textos, exemplos = Counter(), defaultdict(list), {}, defaultdict(list)
        for s in segs:
            repeticoes = Counter()
            for k, (_, chave, texto) in enumerate(s.acoes):
                candidatas = [(chave, texto)]
                if chave.startswith("clique|"):
                    # versão genérica: "clicar em um item da lista" (o nome muda a cada execução,
                    # ex.: cada e-mail de nota fiscal tem um assunto diferente)
                    _, tipo_el, nome = chave.split("|", 2)
                    candidatas.append((f"cliquevar|{tipo_el}", f"Clicar em {tipo_el}"))
                    exemplos[f"cliquevar|{tipo_el}#{repeticoes[f'cliquevar|{tipo_el}'] + 1}"].append(nome)
                for ch, tx in candidatas:
                    repeticoes[ch] += 1
                    chave_n = f"{ch}#{repeticoes[ch]}"     # permite a mesma ação 2x no mesmo passo
                    contagem[chave_n] += 1
                    posicoes[chave_n].append(k / max(len(s.acoes), 1))
                    textos.setdefault(chave_n, tx)
        frequentes = [c for c in contagem if contagem[c] / len(segs) >= config.SUPORTE_MIN_ACAO]
        # descarta a versão genérica quando ações específicas daquele tipo já explicam os cliques
        especificos = Counter(c.split("|")[1] for c in frequentes if c.startswith("clique|"))
        frequentes = [c for c in frequentes if not c.startswith("cliquevar|")
                      or especificos[c.split("|")[1].split("#")[0]] < int(c.rsplit("#", 1)[1])]
        frequentes.sort(key=lambda c: statistics.mean(posicoes[c]))
        for c in frequentes:
            if c in exemplos:  # exemplo do grupo de nomes mais comum (ex.: "NF # - ...")
                grupo = Counter(n.split()[0] for n in exemplos[c] if n).most_common(1)[0][0]
                exemplo = next(n for n in exemplos[c] if n.split()[0] == grupo)
                textos[c] += f" (varia a cada execução — ex.: “{exemplo}”)"
        navs = Counter(x.navegador for x in segs if x.navegador)
        sites = Counter(x.site for x in segs if x.site)
        passos.append({
            "app": segs[0].app,
            "navegador": navs.most_common(1)[0][0] if navs else None,
            "site": sites.most_common(1)[0][0] if sites else None,
            "tela": Counter(s.titulo_norm for s in segs).most_common(1)[0][0],
            "duracao_media_s": round(statistics.mean(s.duracao for s in segs)),
            "acoes": [{"texto": textos[c], "frequencia": round(contagem[c] / len(segs), 2)} for c in frequentes],
        })

    inicios = [inst[0].inicio for inst in instancias]
    duracoes = [inst[-1].fim - inst[0].inicio for inst in instancias]
    for k, passo in enumerate(passos):
        passo.update(_estatisticas_etapa([inst[k].duracao for inst in instancias]))
    execucoes = [[round(inst[0].inicio), round(inst[-1].fim - inst[0].inicio), [round(x.duracao) for x in inst]]
                 for inst in instancias]
    minutos = sorted(datetime.fromtimestamp(t).hour * 60 + datetime.fromtimestamp(t).minute for t in inicios)
    mediana = minutos[len(minutos) // 2]
    tipo_freq, texto_freq = _frequencia(occ, dias_monitorados, inicios)
    return {
        "id": pid,
        "contextos": list(padrao),
        "aplicativos": [a for k, a in enumerate(p["app"] for p in passos) if k == 0 or passos[k - 1]["app"] != a],
        "ocorrencias": len(occ),
        "dias": sorted({d for d, _ in occ}),
        "tipo_frequencia": tipo_freq,
        "frequencia": texto_freq,
        "horario_tipico": f"{mediana // 60:02d}:{mediana % 60:02d}",
        "janela_horario": f"{minutos[0] // 60:02d}:{minutos[0] % 60:02d}–{minutos[-1] // 60:02d}:{minutos[-1] % 60:02d}",
        "duracao_media_s": round(statistics.mean(duracoes)),
        "duracao_media": fmt_duracao(statistics.mean(duracoes)),
        "tempo_total_s": round(sum(duracoes)),
        "tempo_total": fmt_duracao(sum(duracoes)),
        "execucoes_semana": round(len(occ) / len(dias_monitorados) * 5, 1),
        "horas_semana": round(sum(duracoes) / len(dias_monitorados) * 5 / 3600, 2),
        "passos": passos,
        "execucoes": execucoes,
        "interrupcoes": _interrupcoes(padrao, por_dia),
    }


# ---------------------------------------------------------------------- gráficos
def _dados_graficos(processos, dias):
    """Agregados prontos para os gráficos do painel."""
    calor = [[0] * 11 for _ in range(5)]          # seg–sex × 08h–18h (execuções iniciadas)
    por_dia = {d: {} for d in dias}
    for p in processos:
        for inicio, _, _ in p["execucoes"]:
            t = datetime.fromtimestamp(inicio)
            if t.weekday() < 5 and 8 <= t.hour <= 18:
                calor[t.weekday()][t.hour - 8] += 1
            d = t.strftime("%Y-%m-%d")
            if d in por_dia:
                por_dia[d][p["id"]] = por_dia[d].get(p["id"], 0) + 1
    return {
        "calor": calor,
        "calor_horas": list(range(8, 19)),
        "execucoes_por_dia": [{"dia": d, "por_processo": por_dia[d]} for d in dias],
    }


# ---------------------------------------------------------------------- pipeline
def analisar(con, usuario, aprovados=None, rejeitados=None):
    eventos = db.eventos_do_usuario(con, usuario)
    if not eventos:
        raise ValueError(f"Nenhum evento coletado para o usuário '{usuario}'.")

    segmentos = generalizar(construir_segmentos(eventos))
    por_dia = defaultdict(list)
    for s in segmentos:
        por_dia[s.dia].append(s)
    dias = sorted(por_dia)

    aprovados, rejeitados = set(aprovados or ()), set(rejeitados or ())
    achados, novos = minerar_padroes(por_dia, aprovados, rejeitados)
    processos = []
    for k, (padrao, occ) in enumerate(achados):
        p = descrever_processo(f"p{k + 1}", padrao, occ, por_dia, dias)
        p["assinatura"] = assinatura(padrao)
        p["fixado_pelo_gestor"] = p["assinatura"] in aprovados
        processos.append(p)
    candidatos = []
    for k, (padrao, occ) in enumerate(novos):
        c = descrever_processo(f"n{k + 1}", padrao, occ, por_dia, dias)
        c["assinatura"] = assinatura(padrao)
        primeiro = min(c["dias"])
        c["primeira_vez"] = primeiro
        c["recente"] = dias.index(primeiro) >= len(dias) * 0.6     # começou na parte final da coleta
        candidatos.append(c)
    processos.sort(key=lambda p: -p["tempo_total_s"])
    for k, p in enumerate(processos, 1):
        p["id"] = f"p{k}"
        p["gargalos"] = detectar_gargalos(p, len(dias))

    tempo_ativo = sum(s.duracao for s in segmentos)
    por_app = Counter()
    for s in segmentos:
        por_app[s.app] += s.duracao
    tempo_por_dia = {d: round(sum(s.duracao for s in por_dia[d])) for d in dias}
    tempo_processos = sum(p["tempo_total_s"] for p in processos)

    return {
        "usuario": usuario,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "periodo": {"inicio": dias[0], "fim": dias[-1], "dias": len(dias)},
        "estatisticas": {
            "eventos": len(eventos),
            "trocas_de_janela": len(segmentos),
            "tempo_ativo_s": round(tempo_ativo),
            "tempo_ativo": fmt_duracao(tempo_ativo),
            "media_diaria": fmt_duracao(tempo_ativo / len(dias)),
            "tempo_em_processos_s": tempo_processos,
            "tempo_em_processos": fmt_duracao(tempo_processos),
            "percentual_repetitivo": round(100 * tempo_processos / tempo_ativo, 1) if tempo_ativo else 0,
            "tempo_por_app": [{"app": a, "segundos": round(t), "texto": fmt_duracao(t)} for a, t in por_app.most_common(10)],
            "tempo_por_dia": [{"dia": d, "segundos": t} for d, t in tempo_por_dia.items()],
        },
        "graficos": _dados_graficos(processos, dias),
        "candidatos": candidatos,
        "rotina": sorted(
            [{"id": p["id"], "horario": p["horario_tipico"], "frequencia": p["frequencia"],
              "tipo_frequencia": p["tipo_frequencia"]} for p in processos],
            key=lambda r: r["horario"],
        ),
        "processos": processos,
    }
