"""Procura de hiperparâmetros sem tocar no período de teste.

Os parâmetros são escolhidos só com semanas de validação ANTERIORES à primeira
semana do backtest de avaliação (``ate``). Em cada semana de validação, o modelo
é treinado só com o passado dessa semana, exatamente como no backtest. A
configuração atual é sempre a candidata 0, por isso "não mudar" é uma resposta
possível. Depois, a escolha é avaliada nas semanas de teste com o workflow
`avaliar`, como qualquer outra alteração.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config, metricas
from .modelos import ModeloLGBM, parametros_para

log = logging.getLogger(__name__)

ESPACO = {
    "num_leaves": [15, 31, 63, 127],
    "learning_rate": [0.02, 0.03, 0.05],
    "n_estimators": [400, 800, 1500],
    "min_child_samples": [20, 40, 100, 200],
    "colsample_bytree": [0.5, 0.8, 1.0],
    "reg_lambda": [0.0, 1.0, 10.0],
}


def candidatos(n: int, seed: int = config.SEED) -> list[dict]:
    """Candidata 0 = sem alterações; as restantes, amostradas do ESPACO (sem repetições)."""
    rng = np.random.default_rng(seed)
    vistos, saida = set(), [{}]
    while len(saida) < n:
        c = {k: v[rng.integers(len(v))] for k, v in ESPACO.items()}
        chave = tuple(sorted(c.items()))
        if chave not in vistos:
            vistos.add(chave)
            saida.append({k: (v.item() if hasattr(v, "item") else v) for k, v in c.items()})
    return saida


def semanas_validacao(ate: pd.Timestamp, n: int, passo: int = 3) -> list[pd.Timestamp]:
    """``n`` segundas-feiras antes de ``ate``, espaçadas de ``passo`` semanas (cobrem mais estações)."""
    ate = pd.Timestamp(ate)
    if ate.day_of_week != 0:
        raise ValueError("ate tem de ser uma segunda-feira (a primeira semana de teste)")
    return [ate - pd.Timedelta(weeks=passo * k) for k in range(n, 0, -1)]


def avaliar_candidata(exemplos: pd.DataFrame, alvo: str, semanas: list[pd.Timestamp], ajuste: dict) -> float:
    parametros = {**parametros_para(alvo), **ajuste}
    erros = []
    for segunda in semanas:
        domingo = segunda + pd.Timedelta(days=6)
        treino = exemplos[(exemplos["dia"] < segunda) & exemplos["y"].notna()]
        teste = exemplos[
            (exemplos["origem"] >= segunda) & (exemplos["origem"] <= domingo) & exemplos["y"].notna()
        ]
        modelo = ModeloLGBM(alvo, parametros=parametros).treinar(treino, intervalos=False)
        erros.append(metricas.mae(teste["y"], modelo.prever(teste)))
    return float(np.mean(erros))


def procurar(
    exemplos: pd.DataFrame, alvo: str, ate: pd.Timestamp, n_semanas: int = 8, n_candidatas: int = 16
) -> pd.DataFrame:
    semanas = semanas_validacao(ate, n_semanas)
    linhas = []
    for i, ajuste in enumerate(candidatos(n_candidatas)):
        mae = avaliar_candidata(exemplos, alvo, semanas, ajuste)
        log.info("%s candidata %d: MAE %.1f %s", alvo, i, mae, ajuste)
        linhas.append({"alvo": alvo, "candidata": i, "MAE_validacao": mae, "ajuste": ajuste})
    tabela = pd.DataFrame(linhas).sort_values("MAE_validacao").reset_index(drop=True)
    tabela.attrs["semanas"] = [f"{s:%Y-%m-%d}" for s in semanas]
    return tabela
