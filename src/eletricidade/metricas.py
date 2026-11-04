"""Métricas de erro: MAE, MAPE e sMAPE (em %)."""

from __future__ import annotations

import numpy as np


def _validos(y, p):
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    ok = np.isfinite(y) & np.isfinite(p)
    return y[ok], p[ok]


def mae(y, p) -> float:
    y, p = _validos(y, p)
    return float(np.mean(np.abs(y - p))) if y.size else float("nan")


def mape(y, p, limiar: float = 0.0) -> float:
    """MAPE só nas observações com |y| > limiar (evita a explosão perto de zero)."""
    y, p = _validos(y, p)
    ok = np.abs(y) > limiar
    if not ok.any():
        return float("nan")
    return float(100 * np.mean(np.abs(y[ok] - p[ok]) / np.abs(y[ok])))


def smape(y, p) -> float:
    """sMAPE em [0, 200]. Pares com y = p = 0 contam como erro zero."""
    y, p = _validos(y, p)
    if not y.size:
        return float("nan")
    den = np.abs(y) + np.abs(p)
    termos = np.where(den == 0, 0.0, 2 * np.abs(y - p) / np.where(den == 0, 1, den))
    return float(100 * np.mean(termos))


def todas(y, p, limiar_mape: float = 0.0) -> dict[str, float]:
    return {"MAE": mae(y, p), "MAPE": mape(y, p, limiar_mape), "sMAPE": smape(y, p)}
