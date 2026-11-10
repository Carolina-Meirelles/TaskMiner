"""Calculadora das métricas ágeis a partir dos dados do board.

Entrada: um CSV exportado do board (GitHub Projects, Trello...) com uma linha por cartão:

    id,titulo,pontos,sprint,criado_em,iniciado_em,concluido_em
    H1,Levar sugestão ao backlog,5,1,2026-11-10,2026-11-11,2026-11-13

(datas AAAA-MM-DD; iniciado_em/concluido_em ficam vazios se o cartão ainda não começou/terminou)

Saída (na pasta indicada): metricas.md com as tabelas e os gráficos burndown_sprint_N.png,
velocity.png e cfd.png, prontos para o Relatório.

Uso:
    python ferramentas/metricas.py board.csv --saida docs/metricas
    python ferramentas/metricas.py ferramentas/exemplo_board.csv --saida /tmp/teste   # dados fictícios

As datas das Sprints seguem o Cronograma do Projeto M2 (terça a terça). As contas são feitas aqui, a
partir dos dados do board; a leitura do que os números dizem é do time.
"""
import argparse
import csv
import statistics
from datetime import date, timedelta
from pathlib import Path

SPRINTS = {1: (date(2026, 11, 10), date(2026, 11, 17)),
           2: (date(2026, 11, 17), date(2026, 11, 24)),
           3: (date(2026, 11, 24), date(2026, 12, 1))}


def _data(txt):
    txt = (txt or "").strip()
    return date.fromisoformat(txt) if txt else None


def ler(caminho):
    cartoes = []
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            cartoes.append({
                "id": linha["id"].strip(), "titulo": linha.get("titulo", "").strip(),
                "pontos": int(linha.get("pontos") or 0), "sprint": int(linha["sprint"]) if linha.get("sprint") else None,
                "criado": _data(linha["criado_em"]), "iniciado": _data(linha.get("iniciado_em")),
                "concluido": _data(linha.get("concluido_em")),
            })
    for c in cartoes:
        if c["concluido"] and c["iniciado"] and c["concluido"] < c["iniciado"]:
            raise ValueError(f"Cartão {c['id']}: concluído antes de iniciado. Confira as datas no board.")
    return cartoes


def lead_time(c):
    """Dias entre o cartão entrar no board e ficar pronto."""
    return (c["concluido"] - c["criado"]).days if c["concluido"] and c["criado"] else None


def cycle_time(c):
    """Dias entre começar a trabalhar no cartão e ficar pronto."""
    return (c["concluido"] - c["iniciado"]).days if c["concluido"] and c["iniciado"] else None


def por_sprint(cartoes):
    r = {}
    for n, (ini, fim) in SPRINTS.items():
        # a terça que fecha uma Sprint abre a seguinte: o cartão concluído nesse dia conta na Sprint que termina
        ini_ef = ini + timedelta(days=1) if n > 1 else ini
        feitos = [c for c in cartoes if c["concluido"] and ini_ef <= c["concluido"] <= fim]
        planejados = [c for c in cartoes if c["sprint"] == n]
        leads = [lead_time(c) for c in feitos if lead_time(c) is not None]
        cycles = [cycle_time(c) for c in feitos if cycle_time(c) is not None]
        r[n] = {
            "inicio": ini, "fim": fim,
            "planejados_pts": sum(c["pontos"] for c in planejados),
            "throughput": len(feitos),
            "velocity": sum(c["pontos"] for c in feitos if c["sprint"] == n),
            "lead_medio": round(statistics.mean(leads), 1) if leads else None,
            "cycle_medio": round(statistics.mean(cycles), 1) if cycles else None,
            "burndown": burndown(planejados, ini, fim),
        }
    return r


def burndown(planejados, ini, fim):
    """Pontos que faltam no fim de cada dia da Sprint."""
    total, dias, d = sum(c["pontos"] for c in planejados), [], ini
    while d <= fim:
        feitos = sum(c["pontos"] for c in planejados if c["concluido"] and c["concluido"] <= d)
        dias.append((d, total - feitos))
        d += timedelta(days=1)
    return dias


def cfd(cartoes):
    """Quantidade de cartões em cada estado por dia, do primeiro cartão até o fim da Sprint 3."""
    ini = min(c["criado"] for c in cartoes if c["criado"])
    fim = max([SPRINTS[3][1]] + [c["concluido"] for c in cartoes if c["concluido"]])
    serie, d = [], ini
    while d <= fim:
        a_fazer = sum(1 for c in cartoes if c["criado"] and c["criado"] <= d and not (c["iniciado"] and c["iniciado"] <= d))
        fazendo = sum(1 for c in cartoes if c["iniciado"] and c["iniciado"] <= d and not (c["concluido"] and c["concluido"] <= d))
        feito = sum(1 for c in cartoes if c["concluido"] and c["concluido"] <= d)
        serie.append((d, a_fazer, fazendo, feito))
        d += timedelta(days=1)
    return serie


def graficos(res, serie_cfd, pasta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    arquivos = []
    for n, s in res.items():
        if not s["planejados_pts"]:
            continue
        dias = [d for d, _ in s["burndown"]]
        real = [p for _, p in s["burndown"]]
        ideal = [s["planejados_pts"] * (1 - k / (len(dias) - 1)) for k in range(len(dias))]
        fig, ax = plt.subplots(figsize=(6, 3.2))
        ax.plot(dias, ideal, "--", color="#9aa0a6", label="ideal")
        ax.plot(dias, real, "-o", color="#2a78d6", markersize=4, label="real")
        ax.set_title(f"Burndown · Sprint {n}")
        ax.set_ylabel("pontos restantes")
        ax.set_ylim(bottom=0)
        ax.legend(frameon=False)
        ax.set_xticks(dias)
        ax.set_xticklabels([d.strftime("%d/%m") for d in dias], rotation=45)
        fig.tight_layout()
        nome = pasta / f"burndown_sprint_{n}.png"
        fig.savefig(nome, dpi=150)
        plt.close(fig)
        arquivos.append(nome)
    fig, ax = plt.subplots(figsize=(5, 3))
    ns = list(res)
    ax.bar([f"Sprint {n}" for n in ns], [res[n]["velocity"] for n in ns], color="#2a78d6", width=0.5)
    for k, n in enumerate(ns):
        ax.text(k, res[n]["velocity"] + 0.3, str(res[n]["velocity"]), ha="center")
    ax.set_title("Velocity (pontos entregues)")
    fig.tight_layout()
    fig.savefig(pasta / "velocity.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    dias = [d for d, *_ in serie_cfd]
    ax.stackplot(dias, [x[3] for x in serie_cfd], [x[2] for x in serie_cfd], [x[1] for x in serie_cfd],
                 labels=["Feito", "Fazendo", "A fazer"], colors=["#1baf7a", "#eb6834", "#cde2fb"], alpha=0.95)
    ax.set_title("CFD (fluxo acumulado)")
    ax.set_ylabel("cartões")
    ax.legend(loc="upper left", frameon=False)
    ax.set_xticks(dias[::2])
    ax.set_xticklabels([d.strftime("%d/%m") for d in dias[::2]], rotation=45)
    fig.tight_layout()
    fig.savefig(pasta / "cfd.png", dpi=150)
    plt.close(fig)
    return arquivos + [pasta / "velocity.png", pasta / "cfd.png"]


def relatorio(cartoes, res, pasta, exemplo=False):
    fmt = lambda v: "—" if v is None else str(v).replace(".", ",")
    linhas = ["# Métricas do board", ""]
    if exemplo:
        linhas += ["> **DADOS FICTÍCIOS DE EXEMPLO.** Substitua pelo CSV real do board antes de usar no Relatório.", ""]
    linhas += ["## Por Sprint", "", "| Sprint | Período | Planejado (pts) | Velocity (pts) | Throughput (cartões) | Lead Time médio (dias) | Cycle Time médio (dias) |",
               "|---|---|---|---|---|---|---|"]
    for n, s in res.items():
        linhas.append(f"| {n} | {s['inicio']:%d/%m} a {s['fim']:%d/%m} | {s['planejados_pts']} | {s['velocity']} | "
                      f"{s['throughput']} | {fmt(s['lead_medio'])} | {fmt(s['cycle_medio'])} |")
    linhas += ["", "## Por cartão", "", "| Cartão | Título | Pontos | Sprint | Lead Time (dias) | Cycle Time (dias) |", "|---|---|---|---|---|---|"]
    for c in cartoes:
        linhas.append(f"| {c['id']} | {c['titulo']} | {c['pontos']} | {c['sprint'] or '—'} | {fmt(lead_time(c))} | {fmt(cycle_time(c))} |")
    linhas += ["", "Lead Time = conclusão − entrada no board · Cycle Time = conclusão − início do trabalho ·",
               "Throughput = cartões concluídos na Sprint · Velocity = pontos das histórias planejadas e concluídas na Sprint.", "",
               "## Gráficos", "", "![Velocity](velocity.png)", "", "![CFD](cfd.png)", ""]
    for n in res:
        if res[n]["planejados_pts"]:
            linhas += [f"![Burndown Sprint {n}](burndown_sprint_{n}.png)", ""]
    linhas += ["## O que os números dizem (preencher pelo time)", "", "- Sprint 1:", "- Sprint 2:", "- Sprint 3:", ""]
    (pasta / "metricas.md").write_text("\n".join(linhas), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Métricas ágeis a partir do CSV do board")
    ap.add_argument("csv")
    ap.add_argument("--saida", default="docs/metricas")
    a = ap.parse_args()
    pasta = Path(a.saida)
    pasta.mkdir(parents=True, exist_ok=True)
    cartoes = ler(a.csv)
    res = por_sprint(cartoes)
    graficos(res, cfd(cartoes), pasta)
    relatorio(cartoes, res, pasta, exemplo="exemplo" in Path(a.csv).name)
    for n, s in res.items():
        print(f"Sprint {n}: velocity {s['velocity']} pts, throughput {s['throughput']}, "
              f"lead médio {s['lead_medio']} d, cycle médio {s['cycle_medio']} d")
    print(f"Relatório e gráficos em {pasta}/")


if __name__ == "__main__":
    main()
