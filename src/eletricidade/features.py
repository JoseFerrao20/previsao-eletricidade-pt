"""Construção da tabela de exemplos (origem, alvo, horizonte) sem fuga de informação.

Convenções
----------
- Grelha local: índice (dia, hora) em hora de Lisboa, hora 0..23.
- Origem (emissão): meia-noite local do dia D; conhecem-se valores reais até
  ao fim de D-1.
- ``lead`` = 1 para alvos em D, 2 para alvos em D+1. Logo D = dia - lead + 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import calendario, config
from .meteo import colunas_por_ponto


def para_grade_local(horario_utc: pd.DataFrame) -> pd.DataFrame:
    """Converte uma tabela horária em UTC para a grelha (dia, hora) local."""
    local = horario_utc.index.tz_convert(config.FUSO)
    tabela = horario_utc.copy()
    tabela.index = pd.MultiIndex.from_arrays(
        [pd.Index(local.date, name="dia"), pd.Index(local.hour, name="hora")]
    )
    tabela = tabela.groupby(level=["dia", "hora"]).mean()
    dias = pd.Index(sorted(set(tabela.index.get_level_values("dia"))), name="dia")
    todos = pd.MultiIndex.from_product([dias, range(24)], names=["dia", "hora"])
    return tabela.reindex(todos)


def _matriz(grade: pd.DataFrame, coluna: str, ate: pd.Timestamp | None = None) -> pd.DataFrame:
    """Matriz dia × hora com dias contínuos (dias em falta como NaN), até ``ate`` se dado."""
    m = grade[coluna].unstack("hora")
    m.index = pd.DatetimeIndex(m.index)
    fim = max(m.index.max(), pd.Timestamp(ate)) if ate is not None else m.index.max()
    completo = pd.date_range(m.index.min(), fim, freq="D")
    return m.reindex(completo)


def _empilhar(m: pd.DataFrame, nome: str) -> pd.Series:
    s = m.stack(future_stack=True)
    s.index = s.index.set_names(["dia", "hora"])
    return s.rename(nome)


def features_historicas(
    grade: pd.DataFrame, alvo: str, lead: int, ate: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Features construídas só com valores reais até D-1, para cada (dia alvo, hora).

    Para um alvo no dia t com horizonte ``lead``, o último dia conhecido é
    t - lead. Todas as janelas terminam aí.
    """
    m = _matriz(grade, alvo, ate)
    ultimo = m.shift(lead)  # D-1, mesma hora (persistência diária)
    lag7 = m.shift(7)  # mesma hora, 7 dias antes (conhecido porque lead <= 7)
    if lead > 7:
        raise ValueError("lead > 7 tornaria o naive sazonal inválido")
    media7 = sum(m.shift(lead + i) for i in range(7)) / 7  # D-7..D-1
    max30 = pd.concat([m.shift(lead + i) for i in range(30)]).groupby(level=0).max()
    nivel = m.mean(axis=1).shift(lead)  # média diária de D-1
    tabela = pd.concat(
        [
            _empilhar(ultimo, "persistencia"),
            _empilhar(lag7, "naive_sazonal"),
            _empilhar(media7, "media_semana"),
            _empilhar(max30, "max_30d"),
            _empilhar(pd.DataFrame({h: nivel for h in m.columns}), "nivel_ultimo_dia"),
            _empilhar(m, "y"),
        ],
        axis=1,
    )
    tabela["lead"] = lead
    return tabela


def features_meteo(meteo_grupos_utc: pd.DataFrame, alvo: str, lead: int) -> pd.DataFrame:
    """Meteorologia prevista para o alvo, com a corrida correspondente ao lead."""
    colunas = [f"{g}__{v}" for g, v in config.METEO_POR_ALVO[alvo]] + colunas_por_ponto(alvo)
    sub = meteo_grupos_utc.xs(lead, level="lead_dias").reindex(columns=colunas)
    sub.index = pd.DatetimeIndex(sub.index)
    if sub.index.tz is None:
        sub.index = sub.index.tz_localize("UTC")
    grade = para_grade_local(sub)
    grade.index = grade.index.set_levels(pd.DatetimeIndex(grade.index.levels[0]), level="dia")
    return grade


def construir_exemplos(
    grade_ren: pd.DataFrame,
    meteo_grupos_utc: pd.DataFrame | None,
    alvo: str,
    ate: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Tabela de exemplos para um alvo: um registo por (dia alvo, hora, lead).

    ``ate`` estende a grelha para o futuro (dias ainda sem valores reais), para
    se poder emitir previsões.
    """
    partes = []
    for lead in range(1, config.DIAS_HORIZONTE + 1):
        tabela = features_historicas(grade_ren, alvo, lead, ate)
        if meteo_grupos_utc is not None:
            tabela = tabela.join(features_meteo(meteo_grupos_utc, alvo, lead), how="left")
        partes.append(tabela)
    exemplos = pd.concat(partes).reset_index()
    exemplos["dia"] = pd.to_datetime(exemplos["dia"])
    exemplos["origem"] = exemplos["dia"] - pd.to_timedelta(exemplos["lead"] - 1, unit="D")
    exemplos = exemplos.join(calendario.features_calendario(exemplos["dia"], exemplos["hora"]))
    # Descarta só o aquecimento inicial (janelas de 30 dias incompletas). Linhas
    # posteriores com lags em falta ficam: o LightGBM lida com NaN e o backtest
    # avalia todos os modelos apenas nas linhas em que todos têm previsão.
    exemplos = exemplos[exemplos["dia"] >= exemplos["dia"].min() + pd.Timedelta(days=31)]
    return exemplos.sort_values(["origem", "dia", "hora"]).reset_index(drop=True)


COLUNAS_NAO_FEATURES = {"dia", "origem", "y"}


def colunas_features(exemplos: pd.DataFrame) -> list[str]:
    return [c for c in exemplos.columns if c not in COLUNAS_NAO_FEATURES]


def matriz_x(exemplos: pd.DataFrame, colunas: list[str]) -> np.ndarray:
    return exemplos[colunas].to_numpy(dtype=float)
