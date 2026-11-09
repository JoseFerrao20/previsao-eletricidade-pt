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
# ACI (Gibbs & Candès, 2021), em lote semanal: passo fixado antes de ver os resultados.
GAMA = 0.5
LIMITES_NIVEL = (0.5, 0.995)


def ajustes(previsoes: pd.DataFrame, niveis: dict | None = None) -> pd.DataFrame:
    """Deslocamentos por (alvo, lead, hora) a partir de previsões fora da amostra com y.

    ``niveis`` dá, por (alvo, lead), o nível do quantil de cada lado
    ({"baixo": q, "alto": q}); por omissão 0,9 dos dois lados (calibração estática).
    """
    d = previsoes.dropna(subset=["y", "lightgbm_p10", "lightgbm_p90"])
    d = d.assign(e_baixo=d["lightgbm_p10"] - d["y"], e_alto=d["y"] - d["lightgbm_p90"])
    linhas = []
    for (alvo, lead, hora), g in d.groupby(["alvo", "lead", "hora"]):
        n = (niveis or {}).get((alvo, lead), {"baixo": NIVEL, "alto": NIVEL})
        linhas.append(
            {
                "alvo": alvo,
                "lead": lead,
                "hora": hora,
                "c_baixo": float(np.quantile(g["e_baixo"], n["baixo"])),
                "c_alto": float(np.quantile(g["e_alto"], n["alto"])),
            }
        )
    return pd.DataFrame(linhas, columns=["alvo", "lead", "hora", "c_baixo", "c_alto"])


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


def calibrar_backtest(previsoes: pd.DataFrame, adaptativo: bool = True) -> pd.DataFrame:
    """Acrescenta lightgbm_p10c/p90c: cada semana calibrada só com as anteriores.

    Com ``adaptativo`` (ACI), o nível do quantil de cada lado é corrigido semana a
    semana pela taxa de falhas da semana anterior, já observada:
        nível ← nível + GAMA × (falhas_do_lado − 0,10)
    Mais falhas do que 10 % de um lado → nível mais alto → limite mais afastado.
    O nível final de cada (alvo, lead) fica em ``saida.attrs["niveis"]`` para a produção.
    """
    saida = previsoes.copy()
    saida["lightgbm_p10c"] = np.nan
    saida["lightgbm_p90c"] = np.nan
    semanas = np.sort(saida["semana"].unique())
    niveis: dict = {}
    for i, s in enumerate(semanas):
        if i < MIN_SEMANAS:
            continue
        passado = saida[saida["semana"].isin(semanas[max(0, i - JANELA_SEMANAS) : i])]
        aqui = saida["semana"] == s
        tabela = ajustes(passado, niveis if adaptativo else None)
        b, a = aplicar(saida[aqui], tabela, "lightgbm", "lightgbm_p10", "lightgbm_p90")
        saida.loc[aqui, "lightgbm_p10c"] = b
        saida.loc[aqui, "lightgbm_p90c"] = a
        if adaptativo:
            semana = saida[aqui].dropna(subset=["y", "lightgbm_p10c", "lightgbm_p90c"])
            for (alvo, lead), g in semana.groupby(["alvo", "lead"]):
                n = niveis.setdefault((alvo, lead), {"baixo": NIVEL, "alto": NIVEL})
                falhas_baixo = float((g["y"] < g["lightgbm_p10c"]).mean())
                falhas_alto = float((g["y"] > g["lightgbm_p90c"]).mean())
                alvo_falhas = 1 - NIVEL
                n["baixo"] = float(np.clip(n["baixo"] + GAMA * (falhas_baixo - alvo_falhas), *LIMITES_NIVEL))
                n["alto"] = float(np.clip(n["alto"] + GAMA * (falhas_alto - alvo_falhas), *LIMITES_NIVEL))
    saida.attrs["niveis"] = {f"{a}|{lead}": v for (a, lead), v in niveis.items()}
    return saida


def ajustes_producao(previsoes: pd.DataFrame) -> pd.DataFrame:
    """Tabela para produção: as últimas JANELA_SEMANAS semanas do backtest, com os níveis
    finais do ACI (se ``previsoes`` vier de calibrar_backtest adaptativo)."""
    semanas = np.sort(previsoes["semana"].unique())[-JANELA_SEMANAS:]
    niveis = {
        (k.split("|")[0], int(k.split("|")[1])): v for k, v in previsoes.attrs.get("niveis", {}).items()
    }
    tabela = ajustes(previsoes[previsoes["semana"].isin(semanas)], niveis or None)
    if niveis:
        tabela["nivel_baixo"] = [
            niveis.get((a, int(lead)), {}).get("baixo", NIVEL)
            for a, lead in zip(tabela["alvo"], tabela["lead"], strict=True)
        ]
        tabela["nivel_alto"] = [
            niveis.get((a, int(lead)), {}).get("alto", NIVEL)
            for a, lead in zip(tabela["alvo"], tabela["lead"], strict=True)
        ]
    return tabela
