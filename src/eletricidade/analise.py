"""Análise do erro do backtest por segmento: onde o modelo ganha (ou não) às referências.

Junta as previsões fora da amostra do backtest às features da mesma linha
(calendário e meteorologia prevista, isto é, a que estava disponível na emissão)
e calcula o MAE por segmento. Os segmentos são definidos só com informação
conhecida na emissão, por isso a tabela também diz quando confiar mais ou menos
na previsão.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import metricas
from .backtest import MODELOS
from .modelos import REFERENCIAS

ESTACOES = {12: "inverno", 1: "inverno", 2: "inverno", 3: "primavera", 4: "primavera", 5: "primavera",
            6: "verão", 7: "verão", 8: "verão", 9: "outono", 10: "outono", 11: "outono"}  # fmt: skip
ORDEM_ESTACOES = ["inverno", "primavera", "verão", "outono"]

# Segmentos meteorológicos por alvo: (coluna, rótulo, limites, nomes dos intervalos).
METEO_SEGMENTOS = {
    "consumo": (
        "populacao__temperature_2m",
        "temperatura prevista",
        [-np.inf, 10, 20, 28, np.inf],
        ["< 10 °C", "10–20 °C", "20–28 °C", "≥ 28 °C"],
    ),
    "eolica": (
        "vento__wind_speed_100m",
        "vento previsto a 100 m",
        [-np.inf, 4, 8, 12, np.inf],
        ["< 4 m/s", "4–8 m/s", "8–12 m/s", "≥ 12 m/s"],
    ),
    "solar": (
        "sol__cloud_cover",
        "nebulosidade prevista (horas de sol)",
        [-np.inf, 20, 60, np.inf],
        ["< 20 %", "20–60 %", "≥ 60 %"],
    ),
}
# No solar, a noite (radiação prevista ~0) não diz nada sobre nuvens e é trivial.
RADIACAO_MIN_SOLAR = 50.0  # W/m²


def tipo_dia(ex: pd.DataFrame) -> pd.Series:
    tipo = np.select(
        [ex["feriado"] == 1, ex["ponte"] == 1, ex["fim_de_semana"] == 1],
        ["feriado", "ponte", "fim de semana"],
        default="dia útil",
    )
    return pd.Series(tipo, index=ex.index)


def juntar(previsoes: pd.DataFrame, exemplos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Previsões do backtest com as colunas de segmentação."""
    partes = []
    for alvo, p in previsoes.groupby("alvo"):
        ex = exemplos[alvo]
        cols = ["origem", "dia", "hora", "lead", "feriado", "ponte", "fim_de_semana"]
        coluna_meteo = METEO_SEGMENTOS[alvo][0]
        extra = [c for c in (coluna_meteo, "sol__shortwave_radiation") if c in ex and c not in cols]
        j = p.merge(ex[cols + extra], on=["origem", "dia", "hora", "lead"], how="left", validate="one_to_one")
        j["estacao"] = pd.to_datetime(j["dia"]).dt.month.map(ESTACOES)
        j["tipo_dia"] = tipo_dia(j)
        if coluna_meteo in j:
            _, _, limites, nomes = METEO_SEGMENTOS[alvo]
            j["meteo"] = pd.cut(j[coluna_meteo], limites, labels=nomes, right=False).astype(object)
            if alvo == "solar" and "sol__shortwave_radiation" in j:
                j.loc[j["sol__shortwave_radiation"] < RADIACAO_MIN_SOLAR, "meteo"] = None
        partes.append(j)
    return pd.concat(partes, ignore_index=True)


def por_segmento(juntas: pd.DataFrame, dimensao: str) -> pd.DataFrame:
    """MAE do LightGBM e das referências por segmento, sempre nas mesmas linhas.

    ``melhor_simples`` é a melhor referência *dentro de cada segmento*, escolhida
    depois de ver o resultado: é uma comparação deliberadamente exigente.
    """
    linhas = []
    for (alvo, segmento), g in juntas.dropna(subset=[dimensao]).groupby(["alvo", dimensao]):
        g = g.dropna(subset=["y", *MODELOS])
        if g.empty:
            continue
        mae = {m: metricas.mae(g["y"], g[m]) for m in MODELOS}
        melhor = min(REFERENCIAS, key=lambda m: mae[m])
        linhas.append(
            {
                "alvo": alvo,
                "dimensao": dimensao,
                "segmento": segmento,
                "previsoes": len(g),
                "MAE_lightgbm": mae["lightgbm"],
                "MAE_naive_sazonal": mae["naive_sazonal"],
                "melhor_simples": melhor,
                "MAE_melhor_simples": mae[melhor],
                "skill_vs_melhor_simples": 1 - mae["lightgbm"] / mae[melhor],
            }
        )
    return pd.DataFrame(linhas)


def tabela_completa(previsoes: pd.DataFrame, exemplos: dict[str, pd.DataFrame]) -> pd.DataFrame:
    juntas = juntar(previsoes, exemplos)
    return pd.concat([por_segmento(juntas, d) for d in ("estacao", "tipo_dia", "meteo")], ignore_index=True)


NOMES_REF = {"naive_sazonal": "naive", "media_semana": "média sem.", "persistencia": "persist."}
TITULOS = {"estacao": "Estação", "tipo_dia": "Tipo de dia"}
ORDEM_TIPO_DIA = ["dia útil", "fim de semana", "feriado", "ponte"]


def _ordenar(t: pd.DataFrame, alvo: str) -> pd.DataFrame:
    ordem = {
        "estacao": ORDEM_ESTACOES,
        "tipo_dia": ORDEM_TIPO_DIA,
        "meteo": METEO_SEGMENTOS[alvo][3],
    }
    chave = t.apply(lambda r: (["estacao", "tipo_dia", "meteo"].index(r["dimensao"]),
                               ordem[r["dimensao"]].index(r["segmento"])), axis=1)  # fmt: skip
    return t.assign(_k=chave).sort_values("_k").drop(columns="_k")


def markdown(tabela: pd.DataFrame) -> str:
    """Uma tabela por alvo; MAE em MW, horizontes D e D+1 agregados."""
    blocos = []
    for alvo, t in tabela.groupby("alvo", sort=False):
        rotulo_meteo = METEO_SEGMENTOS[alvo][1].capitalize()
        linhas = [
            f"**{alvo}**",
            "",
            "| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |",
            "|---|---|---:|---:|---:|---:|---:|",
        ]
        for _, r in _ordenar(t, alvo).iterrows():
            titulo = TITULOS.get(r["dimensao"], rotulo_meteo)
            linhas.append(
                f"| {titulo} | {r['segmento']} | {r['previsoes']:,} | {r['MAE_lightgbm']:.0f} "
                f"| {r['MAE_naive_sazonal']:.0f} | {r['MAE_melhor_simples']:.0f} "
                f"({NOMES_REF[r['melhor_simples']]}) | {r['skill_vs_melhor_simples']:+.0%} |".replace(
                    ",", " "
                )
            )
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)
