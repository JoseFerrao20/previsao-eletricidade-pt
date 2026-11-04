"""Modelos: referências simples e LightGBM (um modelo por alvo, horizonte como feature)."""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from . import config, features

# Referências: a previsão é uma coluna já calculada, sem fuga (ver features.py).
REFERENCIAS = {
    "naive_sazonal": "naive_sazonal",  # mesma hora, 7 dias antes
    "media_semana": "media_semana",  # média da mesma hora em D-7..D-1
    "persistencia": "persistencia",  # mesma hora em D-1
}

PARAMETROS_LGBM = {
    "objective": "l1",  # alinhado com o MAE
    "n_estimators": 800,
    "learning_rate": 0.03,
    "num_leaves": 31,
    "min_child_samples": 40,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "reg_lambda": 1.0,
    "random_state": config.SEED,
    "deterministic": True,
    "force_row_wise": True,
    "n_jobs": 2,
    "verbose": -1,
}


def prever_referencia(exemplos: pd.DataFrame, nome: str) -> np.ndarray:
    return exemplos[REFERENCIAS[nome]].to_numpy(dtype=float)


@dataclass
class ModeloLGBM:
    alvo: str
    parametros: dict = field(default_factory=lambda: dict(PARAMETROS_LGBM))
    colunas: list[str] = field(default_factory=list)
    modelo: lgb.LGBMRegressor | None = None

    def treinar(self, exemplos: pd.DataFrame) -> ModeloLGBM:
        treino = exemplos.dropna(subset=["y"])
        if treino.empty:
            raise ValueError(f"{self.alvo}: sem dados de treino")
        self.colunas = features.colunas_features(treino)
        self.modelo = lgb.LGBMRegressor(**self.parametros)
        self.modelo.fit(features.matriz_x(treino, self.colunas), treino["y"].to_numpy())
        return self

    def prever(self, exemplos: pd.DataFrame) -> np.ndarray:
        if self.modelo is None:
            raise RuntimeError("Modelo não treinado")
        p = self.modelo.predict(features.matriz_x(exemplos, self.colunas))
        if self.alvo in ("eolica", "solar"):
            p = np.clip(p, 0, None)  # produção não pode ser negativa
        if self.alvo == "solar":
            # Sem radiação prevista e sem produção conhecida a essa hora => noite.
            noite = exemplos["max_30d"].to_numpy(dtype=float) <= 1.0
            p = np.where(noite, 0.0, p)
        return p
