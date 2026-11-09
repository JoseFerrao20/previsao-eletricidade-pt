import numpy as np
import pandas as pd
import pytest

from eletricidade import backtest, features, metricas


def test_metricas_valores_conhecidos():
    y, p = [100, 200, 0], [110, 180, 0]
    assert metricas.mae(y, p) == pytest.approx(10)
    assert metricas.mape(y, p, limiar=1) == pytest.approx(10)  # ignora o zero
    assert metricas.smape(y, p) == pytest.approx(100 * (20 / 210 + 40 / 380 + 0) / 3)
    assert np.isnan(metricas.mape([0, 0], [1, 1], limiar=1))


def test_backtest_semana_a_semana_e_deterministico(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "consumo")
    a = backtest.correr(ex, "consumo", n_semanas=3, min_dias_treino=100)
    b = backtest.correr(ex, "consumo", n_semanas=3, min_dias_treino=100)
    np.testing.assert_array_equal(a["lightgbm"].to_numpy(), b["lightgbm"].to_numpy())
    assert a["semana"].nunique() == 3
    assert set(a["semana"].dt.day_of_week) == {0}
    # nenhuma linha de treino é posterior ao início da semana de teste: verificado pela origem
    for semana, g in a.groupby("semana"):
        assert (g["origem"] >= semana).all() and (g["origem"] < semana + np.timedelta64(7, "D")).all()

    resumo = backtest.resumir(a)
    assert set(resumo["modelo"]) == set(backtest.MODELOS)
    naive = resumo[resumo["modelo"] == "naive_sazonal"]["skill_vs_naive_sazonal"]
    assert naive.to_numpy() == pytest.approx([0.0])
    assert "| consumo |" in backtest.tabela_markdown(resumo)


def test_ultima_semana_fixa_a_janela(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "consumo")
    livres = backtest.semanas_teste(ex, 3)
    fixas = backtest.semanas_teste(ex, 3, ultima_semana=livres[0])
    assert fixas[-1] == livres[0] and len(fixas) == 3
    with pytest.raises(ValueError):
        backtest.semanas_teste(ex, 3, ultima_semana=livres[0] + pd.Timedelta(days=1))
