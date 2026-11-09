"""Features de calendário: hora, dia da semana, sazonalidade, feriados nacionais."""

from __future__ import annotations

from functools import cache

import holidays
import numpy as np
import pandas as pd


@cache
def _feriados(ano: int) -> frozenset:
    # Feriados nacionais de Portugal (o Carnaval e os feriados municipais não entram).
    return frozenset(holidays.country_holidays("PT", years=ano).keys())


def e_feriado(dias: pd.Series) -> pd.Series:
    datas = pd.to_datetime(dias).dt.date
    return pd.Series([d in _feriados(d.year) for d in datas], index=dias.index)


def features_calendario(dias: pd.Series, horas: pd.Series) -> pd.DataFrame:
    dias = pd.to_datetime(dias)
    dia_semana = dias.dt.day_of_week
    dia_ano = dias.dt.day_of_year
    feriado = e_feriado(dias)
    feriado_ontem = e_feriado(dias - pd.Timedelta(days=1))
    feriado_amanha = e_feriado(dias + pd.Timedelta(days=1))
    # "Ponte": dia útil entre um feriado e o fim de semana.
    ponte = ((dia_semana == 0) & feriado_amanha) | ((dia_semana == 4) & feriado_ontem)
    return pd.DataFrame(
        {
            "hora": horas.astype(int),
            "dia_semana": dia_semana.astype(int),
            "fim_de_semana": (dia_semana >= 5).astype(int),
            "feriado": feriado.astype(int),
            "ponte": (ponte & ~feriado).astype(int),
            "mes": dias.dt.month.astype(int),
            "doy_sin": np.sin(2 * np.pi * dia_ano / 365.25),
            "doy_cos": np.cos(2 * np.pi * dia_ano / 365.25),
            "tendencia_anos": (dias - pd.Timestamp("2024-01-01")).dt.days / 365.25,
        },
        index=dias.index,
    ).drop(columns="hora")


LIMITE_DIAS = 7  # distância a feriados: além de uma semana não interessa


@cache
def _feriados_ordenados() -> np.ndarray:
    datas = sorted(d for ano in range(2023, 2032) for d in _feriados(ano))
    return np.array(datas, dtype="datetime64[D]")


def _pascoa(ano: int) -> pd.Timestamp:
    """Domingo de Páscoa (algoritmo anónimo gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = (h + l_ - 7 * m + 114) % 31 + 1
    return pd.Timestamp(ano, mes, dia)


def features_calendario_consumo(dias: pd.Series) -> pd.DataFrame:
    """Calendário alargado para o consumo (só datas determinísticas, nada estimado).

    - dias até ao próximo feriado nacional e desde o último (0 = é feriado; limite 7);
    - período de Natal e Ano Novo (24/12 a 1/1) e vésperas (24/12 e 31/12);
    - grandes feriados municipais: Santo António em Lisboa (13/6) e São João no Porto (24/6);
    - Carnaval (terça-feira, Páscoa − 47 dias): facultativo, mas muito observado.
    As férias escolares ficam de fora: o calendário oficial muda todos os anos.
    """
    datas = pd.to_datetime(dias).dt.normalize()
    d64 = datas.to_numpy(dtype="datetime64[D]")
    fer = _feriados_ordenados()
    pos = np.searchsorted(fer, d64, side="left")
    seguinte = fer[np.clip(pos, 0, len(fer) - 1)]
    anterior = fer[np.clip(np.searchsorted(fer, d64, side="right") - 1, 0, len(fer) - 1)]
    ate = (seguinte - d64).astype(int)
    desde = (d64 - anterior).astype(int)
    mes, dia = datas.dt.month, datas.dt.day
    carnaval = datas.apply(lambda d: d == _pascoa(d.year) - pd.Timedelta(days=47))
    return pd.DataFrame(
        {
            "dias_ate_feriado": np.clip(np.where(ate < 0, LIMITE_DIAS, ate), 0, LIMITE_DIAS),
            "dias_desde_feriado": np.clip(np.where(desde < 0, LIMITE_DIAS, desde), 0, LIMITE_DIAS),
            "periodo_natal": (((mes == 12) & (dia >= 24)) | ((mes == 1) & (dia == 1))).astype(int),
            "vespera_natal_ano_novo": ((mes == 12) & dia.isin([24, 31])).astype(int),
            "feriado_municipal_grande": ((mes == 6) & dia.isin([13, 24])).astype(int),
            "carnaval": carnaval.astype(int),
        },
        index=dias.index,
    )
