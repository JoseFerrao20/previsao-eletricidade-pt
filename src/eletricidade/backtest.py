"""Backtest semana a semana (rolling origin) contra as referências simples.

Para cada semana de teste (segunda a domingo de origens):
  1. treina só com exemplos cujo dia alvo é anterior à primeira origem da semana;
  2. prevê todos os exemplos com origem nessa semana (horizontes D e D+1);
  3. compara com as referências, que usam exatamente a mesma informação.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import config, metricas
from .modelos import REFERENCIAS, ModeloLGBM, prever_referencia

log = logging.getLogger(__name__)


def semanas_teste(exemplos: pd.DataFrame, n_semanas: int) -> list[pd.Timestamp]:
    """Segundas-feiras das últimas ``n_semanas`` semanas completas com valores reais."""
    # Última origem com o horizonte completo observado (D e D+1).
    ultima_origem = exemplos.dropna(subset=["y"])["dia"].max() - pd.Timedelta(days=1)
    ultimo_domingo = ultima_origem - pd.Timedelta(days=(ultima_origem.day_of_week - 6) % 7)
    segunda = ultimo_domingo - pd.Timedelta(days=6)
    return [segunda - pd.Timedelta(weeks=i) for i in reversed(range(n_semanas))]


def correr(
    exemplos: pd.DataFrame, alvo: str, n_semanas: int = 26, min_dias_treino: int = 180
) -> pd.DataFrame:
    """Devolve previsões fora da amostra de todos os modelos, por linha de teste."""
    resultados = []
    for segunda in semanas_teste(exemplos, n_semanas):
        domingo = segunda + pd.Timedelta(days=6)
        treino = exemplos[(exemplos["dia"] < segunda) & exemplos["y"].notna()]
        teste = exemplos[
            (exemplos["origem"] >= segunda) & (exemplos["origem"] <= domingo) & exemplos["y"].notna()
        ]
        if teste.empty or treino["dia"].nunique() < min_dias_treino:
            log.info("%s semana %s: ignorada (treino insuficiente ou sem teste)", alvo, segunda.date())
            continue
        modelo = ModeloLGBM(alvo).treinar(treino)
        bloco = teste[["origem", "dia", "hora", "lead", "y"]].copy()
        bloco["semana"] = segunda
        bloco["lightgbm"] = modelo.prever(teste)
        for nome in REFERENCIAS:
            bloco[nome] = prever_referencia(teste, nome)
        resultados.append(bloco)
        log.info("%s semana %s: treino=%d teste=%d", alvo, segunda.date(), len(treino), len(teste))
    if not resultados:
        raise ValueError(f"{alvo}: nenhuma semana de teste avaliável")
    saida = pd.concat(resultados, ignore_index=True)
    saida.insert(0, "alvo", alvo)
    return saida


MODELOS = ("lightgbm", *REFERENCIAS)


def _limiar(alvo: str) -> float:
    return config.LIMIAR_MAPE_SOLAR_MW if alvo == "solar" else 0.0


def resumir(previsoes: pd.DataFrame, por: tuple[str, ...] = ()) -> pd.DataFrame:
    """Métricas por alvo × modelo (× grupos opcionais). Skill face ao naive sazonal."""
    linhas = []
    chaves = ["alvo", *por]
    for chave, grupo in previsoes.groupby(chaves):
        chave = chave if isinstance(chave, tuple) else (chave,)
        alvo = chave[0]
        # Avalia todos os modelos exatamente nas mesmas linhas.
        comum = grupo.dropna(subset=["y", *MODELOS])
        for modelo in MODELOS:
            m = metricas.todas(comum["y"], comum[modelo], _limiar(alvo))
            linhas.append({**dict(zip(chaves, chave, strict=True)), "modelo": modelo, "n": len(comum), **m})
    tabela = pd.DataFrame(linhas)
    ref = tabela[tabela["modelo"] == "naive_sazonal"].set_index(chaves)["MAE"]
    tabela["skill_vs_naive_sazonal"] = 1 - tabela["MAE"] / tabela.set_index(chaves).index.map(ref).to_numpy()
    return tabela


def erro_semanal(previsoes: pd.DataFrame) -> pd.DataFrame:
    """MAE por semana e modelo (para o painel e para a referência do monitor)."""
    linhas = []
    for (alvo, semana), g in previsoes.groupby(["alvo", "semana"]):
        g = g.dropna(subset=["y", *MODELOS])
        for modelo in MODELOS:
            linhas.append(
                {
                    "alvo": alvo,
                    "semana": semana,
                    "modelo": modelo,
                    "MAE": metricas.mae(g["y"], g[modelo]),
                    "sMAPE": metricas.smape(g["y"], g[modelo]),
                }
            )
    return pd.DataFrame(linhas)


def tabela_markdown(resumo: pd.DataFrame) -> str:
    """Tabela para o README (horizonte agregado)."""
    nomes = {
        "lightgbm": "**LightGBM**",
        "naive_sazonal": "Naive sazonal (7 dias)",
        "media_semana": "Média da semana anterior",
        "persistencia": "Persistência (D-1)",
    }
    linhas = [
        "| Alvo | Modelo | MAE (MW) | MAPE | sMAPE | Skill vs. naive sazonal |",
        "|------|--------|---------:|-----:|------:|------------------------:|",
    ]
    for _, r in resumo.iterrows():
        mape_txt = "—" if np.isnan(r["MAPE"]) else f"{r['MAPE']:.1f}%"
        linhas.append(
            f"| {r['alvo']} | {nomes.get(r['modelo'], r['modelo'])} | {r['MAE']:.0f} | {mape_txt} "
            f"| {r['sMAPE']:.1f}% | {r['skill_vs_naive_sazonal']:+.1%} |"
        )
    return "\n".join(linhas)
