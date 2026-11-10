"""Gera o BPMN da função principal do TaskMiner: arquivo .bpmn (BPMN 2.0, abre no bpmn.io / Camunda
Modeler) e uma imagem SVG com as mesmas posições. Uso: python gerar_bpmn.py"""
from pathlib import Path
from xml.sax.saxutils import escape

AQUI = Path(__file__).resolve().parent
X0, LARG, ALT_RAIA, CAB = 30, 1600, 150, 30

RAIAS = [("raia_admin", "Administrador (gestor ou Scrum Master)"),
         ("raia_colab", "Colaborador"),
         ("raia_agente", "Agente TaskMiner (Windows)"),
         ("raia_painel", "Painel TaskMiner (servidor)")]
Y = {r: 20 + i * ALT_RAIA for i, (r, _) in enumerate(RAIAS)}


def meio(raia):
    return Y[raia] + ALT_RAIA // 2


# id: (tipo, raia, x, rótulo)   — tipo: inicio, fim, tarefa, xor
N = {
    "inicio":     ("inicio", "raia_admin", 90, "Time quer melhorar seus processos"),
    "t_cadastrar": ("tarefa", "raia_admin", 160, "Cadastrar colaborador com função e área"),
    "t_instalar": ("tarefa", "raia_colab", 160, "Instalar o agente com o código pessoal"),
    "g_termo":    ("xor", "raia_colab", 340, "Aceita o termo de consentimento?"),
    "fim_cancel": ("fim", "raia_colab", 470, "Coleta cancelada"),
    "t_coletar":  ("tarefa", "raia_agente", 420, "Registrar janelas, sistemas, cliques e atalhos"),
    "t_enviar":   ("tarefa", "raia_agente", 590, "Enviar eventos ao servidor"),
    "g_periodo":  ("xor", "raia_agente", 770, "Completou o período de coleta?"),
    "t_minerar":  ("tarefa", "raia_painel", 750, "Identificar processos repetidos e gargalos"),
    "g_ia":       ("xor", "raia_painel", 930, "Chave da API do Claude configurada?"),
    "t_claude":   ("tarefa", "raia_painel", 1030, "Claude escreve o POP e as sugestões"),
    "t_regras":   ("tarefa", "raia_painel", 1030, "Gerador por regras escreve o POP"),
    "g_junta":    ("xor", "raia_painel", 1200, ""),
    "t_revisar":  ("tarefa", "raia_admin", 1180, "Revisar processos, gargalos e sugestões"),
    "t_backlog":  ("tarefa", "raia_admin", 1350, "Levar melhorias ao backlog do time"),
    "fim":        ("fim", "raia_admin", 1530, "Backlog de melhoria atualizado"),
}
TAM = {"inicio": (36, 36), "fim": (36, 36), "tarefa": (130, 64), "xor": (50, 50)}
DESLOC_Y = {"t_claude": -36, "t_regras": 36}     # duas tarefas paralelas na mesma raia


def caixa(n):
    tipo, raia, x, _ = N[n]
    w, h = TAM[tipo]
    y = meio(raia) - h // 2 + DESLOC_Y.get(n, 0)
    return x, y, w, h


def ponto(n, lado):
    x, y, w, h = caixa(n)
    return {"e": (x, y + h / 2), "d": (x + w, y + h / 2), "c": (x + w / 2, y), "b": (x + w / 2, y + h)}[lado]


# (id, origem, destino, rótulo, pontos intermediários, lados)
F = [
    ("f1", "inicio", "t_cadastrar", "", None, ("d", "e")),
    ("f2", "t_cadastrar", "t_instalar", "", None, ("b", "c")),
    ("f3", "t_instalar", "g_termo", "", None, ("d", "e")),
    ("f4", "g_termo", "fim_cancel", "Não", None, ("d", "e")),
    ("f5", "g_termo", "t_coletar", "Sim", "vh", ("b", "e")),
    ("f6", "t_coletar", "t_enviar", "", None, ("d", "e")),
    ("f7", "t_enviar", "g_periodo", "", None, ("d", "e")),
    ("f8", "g_periodo", "t_coletar", "Não", "loop", ("c", "c")),
    ("f9", "g_periodo", "t_minerar", "Sim", None, ("b", "c")),
    ("f10", "t_minerar", "g_ia", "", None, ("d", "e")),
    ("f11", "g_ia", "t_claude", "Sim", "vh", ("c", "e")),
    ("f12", "g_ia", "t_regras", "Não", "vh", ("b", "e")),
    ("f13", "t_claude", "g_junta", "", "hv", ("d", "c")),
    ("f14", "t_regras", "g_junta", "", "hv", ("d", "b")),
    ("f15", "g_junta", "t_revisar", "", None, ("c", "b")),
    ("f16", "t_revisar", "t_backlog", "", None, ("d", "e")),
    ("f17", "t_backlog", "fim", "", None, ("d", "e")),
]


def caminho(f):
    _, o, d, _, modo, (lo, ld) = f
    a, b = ponto(o, lo), ponto(d, ld)
    if modo == "vh":
        return [a, (a[0], b[1]), b]
    if modo == "hv":
        return [a, (b[0], a[1]), b]
    if modo == "loop":
        topo = Y[N[o][1]] + 14
        return [a, (a[0], topo), (b[0], topo), b]
    if a[0] == b[0] or a[1] == b[1]:
        return [a, b]
    return [a, (a[0], (a[1] + b[1]) / 2), (b[0], (a[1] + b[1]) / 2), b]


def bpmn_xml():
    tag = {"inicio": "startEvent", "fim": "endEvent", "tarefa": "task", "xor": "exclusiveGateway"}
    ent = {n: [f[0] for f in F if f[2] == n] for n in N}
    sai = {n: [f[0] for f in F if f[1] == n] for n in N}
    proc = []
    for n, (tipo, _, _, rot) in N.items():
        filhos = "".join(f"<bpmn:incoming>{i}</bpmn:incoming>" for i in ent[n]) + \
                 "".join(f"<bpmn:outgoing>{i}</bpmn:outgoing>" for i in sai[n])
        proc.append(f'<bpmn:{tag[tipo]} id="{n}" name="{escape(rot)}">{filhos}</bpmn:{tag[tipo]}>')
    for fid, o, d, rot, _, _ in F:
        proc.append(f'<bpmn:sequenceFlow id="{fid}" name="{escape(rot)}" sourceRef="{o}" targetRef="{d}" />')
    lanes = "".join(
        f'<bpmn:lane id="{r}" name="{escape(nome)}">' +
        "".join(f"<bpmn:flowNodeRef>{n}</bpmn:flowNodeRef>" for n in N if N[n][1] == r) + "</bpmn:lane>"
        for r, nome in RAIAS)
    di = [f'<bpmndi:BPMNShape id="part_di" bpmnElement="participante" isHorizontal="true"><dc:Bounds x="{X0}" y="20" width="{LARG}" height="{ALT_RAIA * len(RAIAS)}" /></bpmndi:BPMNShape>']
    for r, _ in RAIAS:
        di.append(f'<bpmndi:BPMNShape id="{r}_di" bpmnElement="{r}" isHorizontal="true"><dc:Bounds x="{X0 + CAB}" y="{Y[r]}" width="{LARG - CAB}" height="{ALT_RAIA}" /></bpmndi:BPMNShape>')
    for n in N:
        x, y, w, h = caixa(n)
        extra = ' isMarkerVisible="true"' if N[n][0] == "xor" else ""
        di.append(f'<bpmndi:BPMNShape id="{n}_di" bpmnElement="{n}"{extra}><dc:Bounds x="{x}" y="{y}" width="{w}" height="{h}" /></bpmndi:BPMNShape>')
    for f in F:
        pts = "".join(f'<di:waypoint x="{px:.0f}" y="{py:.0f}" />' for px, py in caminho(f))
        di.append(f'<bpmndi:BPMNEdge id="{f[0]}_di" bpmnElement="{f[0]}">{pts}</bpmndi:BPMNEdge>')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" xmlns:dc="http://www.omg.org/spec/DD/20100524/DC" xmlns:di="http://www.omg.org/spec/DD/20100524/DI" id="defs_taskminer" targetNamespace="http://taskminer.exemplo/bpmn">
  <bpmn:collaboration id="colaboracao"><bpmn:participant id="participante" name="TaskMiner — transformar o trabalho observado em backlog de melhoria" processRef="processo" /></bpmn:collaboration>
  <bpmn:process id="processo" isExecutable="false">
    <bpmn:laneSet id="raias">{lanes}</bpmn:laneSet>
    {"".join(proc)}
  </bpmn:process>
  <bpmndi:BPMNDiagram id="diagrama"><bpmndi:BPMNPlane id="plano" bpmnElement="colaboracao">{"".join(di)}</bpmndi:BPMNPlane></bpmndi:BPMNDiagram>
</bpmn:definitions>
'''


def quebra(txt, n=19):
    linhas, atual = [], ""
    for p in txt.split():
        if len(atual) + len(p) + 1 > n and atual:
            linhas.append(atual)
            atual = p
        else:
            atual = (atual + " " + p).strip()
    return linhas + ([atual] if atual else [])


def svg():
    W, H = X0 + LARG + 20, 20 + ALT_RAIA * len(RAIAS) + 30
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="Arial, Helvetica, sans-serif">',
         '<defs><marker id="seta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>',
         f'<rect width="{W}" height="{H}" fill="#ffffff"/>',
         f'<rect x="{X0}" y="20" width="{LARG}" height="{ALT_RAIA * len(RAIAS)}" fill="none" stroke="#333" stroke-width="1.5"/>',
         f'<line x1="{X0 + CAB}" y1="20" x2="{X0 + CAB}" y2="{20 + ALT_RAIA * len(RAIAS)}" stroke="#333" stroke-width="1.5"/>']
    for i, (r, nome) in enumerate(RAIAS):
        y = Y[r]
        if i:
            s.append(f'<line x1="{X0 + CAB}" y1="{y}" x2="{X0 + LARG}" y2="{y}" stroke="#333"/>')
        cy = y + ALT_RAIA / 2
        partes = quebra(nome, 22)
        s.append(f'<text transform="translate({X0 + 19},{cy}) rotate(-90)" text-anchor="middle" font-size="11" font-weight="bold">' +
                 "".join(f'<tspan x="0" dy="{(-6 * (len(partes) - 1)) if k == 0 else 12}">{escape(t)}</tspan>' for k, t in enumerate(partes)) + "</text>")
    for f in F:
        pts = caminho(f)
        s.append(f'<polyline points="{" ".join(f"{x:.0f},{y:.0f}" for x, y in pts)}" fill="none" stroke="#333" stroke-width="1.4" marker-end="url(#seta)"/>')
        if f[3]:
            (x1, y1), (x2, y2) = pts[0], pts[1]
            lx, ly = (x1 + x2) / 2 + 6, (y1 + y2) / 2 - 5
            if f[0] == "f9":
                lx, ly = x1 - 30, y1 + 18
            if f[0] == "f11":
                lx, ly = pts[1][0] + 14, pts[1][1] - 6
            if f[0] == "f12":
                lx, ly = pts[1][0] + 14, pts[1][1] - 6
            s.append(f'<text x="{lx:.0f}" y="{ly:.0f}" font-size="11" fill="#333" font-weight="bold">{f[3]}</text>')
    for n, (tipo, _, _, rot) in N.items():
        x, y, w, h = caixa(n)
        if tipo == "tarefa":
            s.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="#fff" stroke="#333" stroke-width="1.5"/>')
            linhas = quebra(rot)
            for k, t in enumerate(linhas):
                s.append(f'<text x="{x + w / 2}" y="{y + h / 2 + (k - (len(linhas) - 1) / 2) * 13 + 4}" text-anchor="middle" font-size="11">{escape(t)}</text>')
        elif tipo in ("inicio", "fim"):
            sw = 1.5 if tipo == "inicio" else 4
            s.append(f'<circle cx="{x + w / 2}" cy="{y + h / 2}" r="{w / 2}" fill="#fff" stroke="#333" stroke-width="{sw}"/>')
            for k, t in enumerate(quebra(rot, 16)):
                s.append(f'<text x="{x + w / 2}" y="{y + h + 14 + k * 12}" text-anchor="middle" font-size="10.5">{escape(t)}</text>')
        else:
            cx, cy = x + w / 2, y + h / 2
            s.append(f'<polygon points="{cx},{y} {x + w},{cy} {cx},{y + h} {x},{cy}" fill="#fff" stroke="#333" stroke-width="1.5"/>')
            s.append(f'<path d="M{cx - 9},{cy - 9} L{cx + 9},{cy + 9} M{cx + 9},{cy - 9} L{cx - 9},{cy + 9}" stroke="#333" stroke-width="3"/>')
            linhas = quebra(rot, 18)
            if n == "g_periodo":      # à direita, abaixo (o retorno "Não" ocupa o topo)
                for k, t in enumerate(linhas):
                    s.append(f'<text x="{x + w + 8}" y="{y + h + 4 + k * 12}" font-size="10.5" font-style="italic">{escape(t)}</text>')
            elif n == "g_ia":         # à esquerda, acima
                for k, t in enumerate(linhas):
                    s.append(f'<text x="{x - 6}" y="{y - 6 - (len(linhas) - 1 - k) * 12}" text-anchor="end" font-size="10.5" font-style="italic">{escape(t)}</text>')
            else:
                for k, t in enumerate(linhas):
                    s.append(f'<text x="{cx}" y="{y - 8 - (len(linhas) - 1 - k) * 12}" text-anchor="middle" font-size="10.5" font-style="italic">{escape(t)}</text>')
    s.append("</svg>")
    return "\n".join(s)


if __name__ == "__main__":
    (AQUI / "taskminer_funcao_principal.bpmn").write_text(bpmn_xml(), encoding="utf-8")
    (AQUI / "taskminer_funcao_principal.svg").write_text(svg(), encoding="utf-8")
    print("Gerados: taskminer_funcao_principal.bpmn e .svg")
