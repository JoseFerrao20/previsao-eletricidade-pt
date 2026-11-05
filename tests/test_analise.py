"""Análise por segmento sobre dados SINTÉTICOS."""

import numpy as np
import pandas as pd

from eletricidade import analise, backtest, features


def test_analise_por_segmento(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "consumo")
    # meteorologia sintética para exercitar o segmento meteorológico
    ex["populacao__temperature_2m"] = np.random.default_rng(0).uniform(0, 35, len(ex))
    prev = backtest.correr(ex, "consumo", n_semanas=4, min_dias_treino=100)
    tabela = analise.tabela_completa(prev, {"consumo": ex})

    assert set(tabela["dimensao"]) == {"estacao", "tipo_dia", "meteo"}
    # cada dimensão parte as mesmas horas (sem perder nem duplicar linhas)
    total = len(prev.dropna(subset=["y", *backtest.MODELOS]))
    for _, t in tabela.groupby("dimensao"):
        assert t["previsoes"].sum() == total
    # "melhor simples" é mesmo o mínimo das referências em cada segmento
    assert (tabela["MAE_melhor_simples"] <= tabela["MAE_naive_sazonal"] + 1e-9).all()

    md = analise.markdown(tabela)
    assert "**consumo**" in md and "Temperatura prevista" in md and "dia útil" in md


def test_tipo_dia_prioriza_feriado():
    ex = pd.DataFrame({"feriado": [1, 0, 0, 0], "ponte": [0, 1, 0, 0], "fim_de_semana": [1, 0, 1, 0]})
    assert analise.tipo_dia(ex).tolist() == ["feriado", "ponte", "fim de semana", "dia útil"]
