"""Calculadora de métricas do board (ferramentas/metricas.py)."""
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import metricas  # noqa: E402


def cartao(id_, pts, sprint, criado, iniciado=None, concluido=None):
    d = lambda s: date.fromisoformat(s) if s else None
    return {"id": id_, "titulo": id_, "pontos": pts, "sprint": sprint,
            "criado": d(criado), "iniciado": d(iniciado), "concluido": d(concluido)}


def test_lead_e_cycle_time():
    c = cartao("A", 5, 1, "2026-11-10", "2026-11-11", "2026-11-13")
    assert metricas.lead_time(c) == 3
    assert metricas.cycle_time(c) == 2


def test_cartao_nao_concluido_nao_tem_lead_time():
    assert metricas.lead_time(cartao("B", 3, 1, "2026-11-10", "2026-11-12")) is None


def test_velocity_throughput_e_burndown():
    cs = [cartao("A", 5, 1, "2026-11-10", "2026-11-11", "2026-11-13"),
          cartao("B", 3, 1, "2026-11-10", "2026-11-12", "2026-11-16"),
          cartao("C", 2, 1, "2026-11-10", "2026-11-14")]
    s1 = metricas.por_sprint(cs)[1]
    assert s1["velocity"] == 8 and s1["throughput"] == 2 and s1["planejados_pts"] == 10
    bd = dict(s1["burndown"])
    assert bd[date(2026, 11, 10)] == 10 and bd[date(2026, 11, 13)] == 5 and bd[date(2026, 11, 17)] == 2


def test_datas_invertidas_sao_recusadas(tmp_path):
    arq = tmp_path / "b.csv"
    arq.write_text("id,titulo,pontos,sprint,criado_em,iniciado_em,concluido_em\nX,x,1,1,2026-11-10,2026-11-15,2026-11-12\n")
    with pytest.raises(ValueError):
        metricas.ler(arq)


def test_cartao_concluido_na_terca_de_virada_conta_so_na_sprint_que_termina():
    cs = [cartao("A", 5, 1, "2026-11-10", "2026-11-11", "2026-11-17")]
    r = metricas.por_sprint(cs)
    assert r[1]["throughput"] == 1 and r[2]["throughput"] == 0
