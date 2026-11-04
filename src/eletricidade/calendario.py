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
