"""Métricas de erro: MAE, MAPE e sMAPE (em %); cobertura e pinball loss para intervalos."""

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


def smape(y, p, limiar: float | None = None) -> float:
    """sMAPE em [0, 200]. Pares com y = p = 0 contam como erro zero.

    Com ``limiar``, só entram observações com |y| > limiar (no solar, as horas
    noturnas ou de alvorada valeriam 200 % por cada MW previsto em vão).
    """
    y, p = _validos(y, p)
    if limiar is not None:
        ok = np.abs(y) > limiar
        y, p = y[ok], p[ok]
    if not y.size:
        return float("nan")
    den = np.abs(y) + np.abs(p)
    termos = np.where(den == 0, 0.0, 2 * np.abs(y - p) / np.where(den == 0, 1, den))
    return float(100 * np.mean(termos))


def todas(y, p, limiar_mape: float = 0.0) -> dict[str, float]:
    limiar_smape = limiar_mape if limiar_mape > 0 else None
    return {"MAE": mae(y, p), "MAPE": mape(y, p, limiar_mape), "sMAPE": smape(y, p, limiar_smape)}


def pinball(y, q, alfa: float) -> float:
    """Perda quantílica média (MW). Minimizada pelo verdadeiro quantil alfa."""
    y, q = _validos(y, q)
    if not y.size:
        return float("nan")
    d = y - q
    return float(np.mean(np.maximum(alfa * d, (alfa - 1) * d)))


def intervalo(y, baixo, alto, alfas: tuple[float, float]) -> dict[str, float]:
    """Cobertura (%), largura média (MW) e pinball dos dois limites."""
    y, baixo, alto = (np.asarray(v, dtype=float) for v in (y, baixo, alto))
    ok = np.isfinite(y) & np.isfinite(baixo) & np.isfinite(alto)
    y, baixo, alto = y[ok], baixo[ok], alto[ok]
    if not y.size:
        return {"cobertura": float("nan"), "largura": float("nan"), "pinball_baixo": float("nan"),
                "pinball_alto": float("nan"), "abaixo": float("nan"), "acima": float("nan")}  # fmt: skip
    return {
        "cobertura": float(100 * np.mean((y >= baixo) & (y <= alto))),
        "abaixo": float(100 * np.mean(y < baixo)),
        "acima": float(100 * np.mean(y > alto)),
        "largura": float(np.mean(alto - baixo)),
        "pinball_baixo": pinball(y, baixo, alfas[0]),
        "pinball_alto": pinball(y, alto, alfas[1]),
    }
