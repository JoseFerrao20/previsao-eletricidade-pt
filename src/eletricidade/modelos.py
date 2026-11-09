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


# Intervalo de previsão a 80 %: quantis 10 % e 90 %, um LightGBM por quantil.
QUANTIS = (0.1, 0.9)
COBERTURA_NOMINAL = QUANTIS[1] - QUANTIS[0]


def _parametros_quantil(alfa: float) -> dict:
    p = dict(PARAMETROS_LGBM)
    p.update({"objective": "quantile", "alpha": alfa, "n_estimators": 400})
    return p


def prever_referencia(exemplos: pd.DataFrame, nome: str) -> np.ndarray:
    return exemplos[REFERENCIAS[nome]].to_numpy(dtype=float)


@dataclass
class ModeloLGBM:
    alvo: str
    parametros: dict = field(default_factory=lambda: dict(PARAMETROS_LGBM))
    colunas: list[str] = field(default_factory=list)
    modelo: lgb.LGBMRegressor | None = None
    quantis: dict[float, lgb.LGBMRegressor] = field(default_factory=dict)

    def treinar(self, exemplos: pd.DataFrame, intervalos: bool = True) -> ModeloLGBM:
        treino = exemplos.dropna(subset=["y"])
        if treino.empty:
            raise ValueError(f"{self.alvo}: sem dados de treino")
        self.colunas = features.colunas_features(treino)
        x, y = features.matriz_x(treino, self.colunas), treino["y"].to_numpy()
        self.modelo = lgb.LGBMRegressor(**self.parametros).fit(x, y)
        self.quantis = (
            {a: lgb.LGBMRegressor(**_parametros_quantil(a)).fit(x, y) for a in QUANTIS} if intervalos else {}
        )
        return self

    def prever(self, exemplos: pd.DataFrame) -> np.ndarray:
        if self.modelo is None:
            raise RuntimeError("Modelo não treinado")
        return self._pos_processar(self.modelo.predict(features.matriz_x(exemplos, self.colunas)), exemplos)

    def prever_intervalo(self, exemplos: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Limites inferior e superior (quantis 10 % e 90 %), sem cruzamento com a mediana."""
        if not self.quantis:
            raise RuntimeError("Modelo treinado sem intervalos")
        x = features.matriz_x(exemplos, self.colunas)
        centro = self.prever(exemplos)
        baixo, alto = (self._pos_processar(self.quantis[a].predict(x), exemplos) for a in QUANTIS)
        # Quantis treinados em separado podem cruzar-se com a previsão central. A
        # previsão central nunca muda (é ela que o MAE avalia); só os limites alargam.
        return np.minimum(baixo, centro), np.maximum(alto, centro)

    def _pos_processar(self, p: np.ndarray, exemplos: pd.DataFrame) -> np.ndarray:
        if self.alvo in ("eolica", "solar"):
            p = np.clip(p, 0, None)  # produção não pode ser negativa
        if self.alvo == "solar":
            # Sem radiação prevista e sem produção conhecida a essa hora => noite.
            noite = exemplos["max_30d"].to_numpy(dtype=float) <= 1.0
            p = np.where(noite, 0.0, p)
        return p
