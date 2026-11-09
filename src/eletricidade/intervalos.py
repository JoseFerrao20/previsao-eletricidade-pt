"""Calibração conformal dos intervalos de previsão (CQR assimétrico).

Os quantis do LightGBM, sozinhos, ficaram estreitos de mais no backtest real
(cobertura de 63–70 % para 80 % nominal; no solar ~53 %, com o P90 baixo de mais
porque a potência instalada cresce). A correção desloca cada limite pelo quantil
90 % dos erros fora da amostra das semanas anteriores:

    c_baixo = Q_0.9(P10 - y)      novo P10 = P10 - c_baixo
    c_alto  = Q_0.9(y - P90)      novo P90 = P90 + c_alto

por alvo, horizonte e hora do dia (o erro do solar ao meio-dia não é o da noite),
com as últimas JANELA_SEMANAS semanas: a calibração acompanha mudanças lentas.
No backtest, cada semana é calibrada só com semanas anteriores; em produção,
com as semanas mais recentes do último backtest.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .modelos import QUANTIS

JANELA_SEMANAS = 12
MIN_SEMANAS = 4
NIVEL = 1 - QUANTIS[0]  # 0,9: cada lado deixa 10 % de fora


def ajustes(previsoes: pd.DataFrame) -> pd.DataFrame:
    """Deslocamentos por (alvo, lead, hora) a partir de previsões fora da amostra com y."""
    d = previsoes.dropna(subset=["y", "lightgbm_p10", "lightgbm_p90"])
    d = d.assign(e_baixo=d["lightgbm_p10"] - d["y"], e_alto=d["y"] - d["lightgbm_p90"])
    return (
        d.groupby(["alvo", "lead", "hora"])
        .agg(
            c_baixo=("e_baixo", lambda e: np.quantile(e, NIVEL)),
            c_alto=("e_alto", lambda e: np.quantile(e, NIVEL)),
        )
        .reset_index()
    )


def aplicar(
    bloco: pd.DataFrame, tabela: pd.DataFrame, centro: str, baixo: str, alto: str
) -> tuple[np.ndarray, np.ndarray]:
    """Limites calibrados para as linhas de ``bloco`` (colunas alvo, lead, hora)."""
    m = bloco[["alvo", "lead", "hora"]].merge(tabela, on=["alvo", "lead", "hora"], how="left")
    novo_b = bloco[baixo].to_numpy() - m["c_baixo"].to_numpy()
    novo_a = bloco[alto].to_numpy() + m["c_alto"].to_numpy()
    c = bloco[centro].to_numpy()
    novo_b, novo_a = np.minimum(novo_b, c), np.maximum(novo_a, c)
    producao = bloco["alvo"].isin(["eolica", "solar"]).to_numpy()
    novo_b = np.where(producao, np.clip(novo_b, 0, None), novo_b)
    # sem tabela para a combinação: mantém o intervalo original
    sem = m["c_baixo"].isna().to_numpy()
    return np.where(sem, bloco[baixo], novo_b), np.where(sem, bloco[alto], novo_a)


def calibrar_backtest(previsoes: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta lightgbm_p10c/p90c: cada semana calibrada só com as anteriores."""
    saida = previsoes.copy()
    saida["lightgbm_p10c"] = np.nan
    saida["lightgbm_p90c"] = np.nan
    semanas = np.sort(saida["semana"].unique())
    for i, s in enumerate(semanas):
        if i < MIN_SEMANAS:
            continue
        passado = saida[saida["semana"].isin(semanas[max(0, i - JANELA_SEMANAS) : i])]
        aqui = saida["semana"] == s
        b, a = aplicar(saida[aqui], ajustes(passado), "lightgbm", "lightgbm_p10", "lightgbm_p90")
        saida.loc[aqui, "lightgbm_p10c"] = b
        saida.loc[aqui, "lightgbm_p90c"] = a
    return saida


def ajustes_producao(previsoes: pd.DataFrame) -> pd.DataFrame:
    """Tabela para produção: as últimas JANELA_SEMANAS semanas do backtest."""
    semanas = np.sort(previsoes["semana"].unique())[-JANELA_SEMANAS:]
    return ajustes(previsoes[previsoes["semana"].isin(semanas)])
