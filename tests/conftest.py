"""Fixtures SINTÉTICAS para testes. Imitam o formato da API; não são dados reais."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from eletricidade import config, ren


def payload_ren(dia: date, n: int | None = None, nomes=None, valor=1000.0) -> dict:
    """JSON tipo Highcharts com ``n`` intervalos (por omissão, os do dia civil)."""
    n = n if n is not None else len(ren.intervalos_utc(dia))
    nomes = nomes or [
        "Hídrica",
        "Eólica",
        "Solar",
        "Gás Natural",
        "Importação",
        "Consumo",
        "Consumo + Bombagem",
    ]
    categorias = [f"{(i // 4) % 24:02d}:{(i % 4) * 15:02d}" for i in range(n)]
    return {
        "xAxis": {"categories": categorias, "title": {"text": "Hora"}},
        "series": [{"name": nome, "data": [valor + i for i in range(n)]} for nome in nomes],
    }


def payload_meteo(inicio: str, fim: str) -> list[dict]:
    from eletricidade.meteo import LEAD_METEO

    horas = pd.date_range(inicio, pd.Timestamp(fim) + pd.Timedelta(hours=23), freq="1h")
    tempos = [t.strftime("%Y-%m-%dT%H:%M") for t in horas]
    locais = []
    for k, _ponto in enumerate(config.PONTOS):
        horario = {"time": tempos}
        for v in config.VARIAVEIS_METEO:
            for n in LEAD_METEO.values():
                horario[f"{v}_previous_day{n}"] = [float(k + n)] * len(tempos)
        locais.append({"hourly": horario})
    return locais


def serie_sintetica(dias: int = 500, seed: int = 0) -> pd.DataFrame:
    """Série horária UTC com padrão diário/semanal + ruído, para os três alvos."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=dias * 24, freq="1h", tz="UTC")
    local = idx.tz_convert(config.FUSO)
    h = local.hour.to_numpy()
    fds = np.asarray(local.day_of_week >= 5)
    consumo = 5000 + 1500 * np.sin((h - 6) / 24 * 2 * np.pi) - 800 * fds + rng.normal(0, 150, idx.size)
    solar = np.clip(2000 * np.sin((h - 6) / 12 * np.pi), 0, None) * (h >= 6) * (h <= 18)
    solar = solar * rng.uniform(0.6, 1.0, idx.size)
    eolica = np.clip(1500 + np.cumsum(rng.normal(0, 60, idx.size)) % 3000, 0, None)
    return pd.DataFrame({"consumo": consumo, "eolica": eolica, "solar": solar}, index=idx).rename_axis(
        "ts_utc"
    )


@pytest.fixture
def horario_sintetico() -> pd.DataFrame:
    return serie_sintetica()
