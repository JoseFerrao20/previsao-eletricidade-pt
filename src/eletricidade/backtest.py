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
from .modelos import QUANTIS, REFERENCIAS, ModeloLGBM, prever_referencia

log = logging.getLogger(__name__)


def semanas_teste(
    exemplos: pd.DataFrame, n_semanas: int, ultima_semana: pd.Timestamp | None = None
) -> list[pd.Timestamp]:
    """Segundas-feiras das últimas ``n_semanas`` semanas completas com valores reais.

    ``ultima_semana`` (uma segunda-feira) fixa o fim, para comparar variantes do
    modelo exatamente nas mesmas semanas mesmo que entretanto cheguem dados novos.
    """
    # Última origem com o horizonte completo observado (D e D+1).
    ultima_origem = exemplos.dropna(subset=["y"])["dia"].max() - pd.Timedelta(days=1)
    ultimo_domingo = ultima_origem - pd.Timedelta(days=(ultima_origem.day_of_week - 6) % 7)
    segunda = ultimo_domingo - pd.Timedelta(days=6)
    if ultima_semana is not None:
        pedida = pd.Timestamp(ultima_semana)
        if pedida.day_of_week != 0 or pedida > segunda:
            raise ValueError(f"ultima_semana tem de ser uma segunda-feira até {segunda.date()}")
        segunda = pedida
    return [segunda - pd.Timedelta(weeks=i) for i in reversed(range(n_semanas))]


def correr(
    exemplos: pd.DataFrame,
    alvo: str,
    n_semanas: int = 26,
    min_dias_treino: int = 180,
    ultima_semana: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Devolve previsões fora da amostra de todos os modelos, por linha de teste."""
    resultados = []
    for segunda in semanas_teste(exemplos, n_semanas, ultima_semana):
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
        bloco["lightgbm_p10"], bloco["lightgbm_p90"] = modelo.prever_intervalo(teste)
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


def resumir_intervalos(previsoes: pd.DataFrame) -> pd.DataFrame:
    """Cobertura do intervalo 10–90 % por alvo e horizonte (nominal: 80 %).

    Ingénuo de comparação: o intervalo empírico do naive sazonal, isto é, o
    naive ± os quantis 10 % e 90 % dos seus erros nas semanas *anteriores* de
    teste (sem olhar para a semana avaliada).
    """
    linhas = []
    for (alvo, lead), g in previsoes.groupby(["alvo", "lead"]):
        g = g.dropna(subset=["y", "lightgbm_p10", "lightgbm_p90", "naive_sazonal"]).sort_values("semana")
        m = metricas.intervalo(g["y"], g["lightgbm_p10"], g["lightgbm_p90"], QUANTIS)
        linhas.append({"alvo": alvo, "lead": lead, "modelo": "lightgbm", "n": len(g), **m})
        baixo, alto = _intervalo_naive_empirico(g)
        ok = np.isfinite(baixo)
        mn = metricas.intervalo(g["y"][ok], baixo[ok], alto[ok], QUANTIS)
        linhas.append({"alvo": alvo, "lead": lead, "modelo": "naive_empirico", "n": int(ok.sum()), **mn})
    return pd.DataFrame(linhas)


def _intervalo_naive_empirico(g: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    erro = (g["y"] - g["naive_sazonal"]).to_numpy()
    semanas = g["semana"].to_numpy()
    baixo = np.full(len(g), np.nan)
    alto = np.full(len(g), np.nan)
    for s in np.unique(semanas):
        antes = erro[semanas < s]
        if antes.size < 24 * 7 * 4:  # pelo menos 4 semanas de erros passados
            continue
        q_b, q_a = np.quantile(antes, QUANTIS)
        aqui = semanas == s
        baixo[aqui] = g["naive_sazonal"].to_numpy()[aqui] + q_b
        alto[aqui] = g["naive_sazonal"].to_numpy()[aqui] + q_a
    return baixo, alto


def tabela_intervalos_markdown(t: pd.DataFrame) -> str:
    nomes = {"lightgbm": "**LightGBM (quantis)**", "naive_empirico": "Naive ± erros passados"}
    linhas = [
        "| Alvo | Horizonte | Intervalo | Cobertura (nominal 80 %) | Abaixo / acima | Largura média (MW) "
        "| Pinball P10 / P90 (MW) |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for _, r in t.iterrows():
        linhas.append(
            f"| {r['alvo']} | {'D' if r['lead'] == 1 else 'D+1'} | {nomes[r['modelo']]} "
            f"| {r['cobertura']:.1f}% "
            f"| {r['abaixo']:.1f}% / {r['acima']:.1f}% | {r['largura']:.0f} "
            f"| {r['pinball_baixo']:.0f} / {r['pinball_alto']:.0f} |"
        )
    return "\n".join(linhas)


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
                    "sMAPE": metricas.smape(g["y"], g[modelo], _limiar(alvo) or None),
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
