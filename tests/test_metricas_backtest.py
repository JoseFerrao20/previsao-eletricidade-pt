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


def test_pinball_e_minimo_no_quantil_certo():
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 20000)
    q_verdadeiro = np.quantile(y, 0.9)
    perdas = {
        q: metricas.pinball(y, np.full_like(y, q), 0.9)
        for q in (q_verdadeiro - 0.5, q_verdadeiro, q_verdadeiro + 0.5)
    }
    assert min(perdas, key=perdas.get) == q_verdadeiro


def test_cobertura_do_intervalo():
    y = np.arange(10.0)
    m = metricas.intervalo(y, np.full(10, 1.0), np.full(10, 8.0), (0.1, 0.9))
    assert m["cobertura"] == 80.0 and m["abaixo"] == 10.0 and m["acima"] == 10.0 and m["largura"] == 7.0


def test_backtest_produz_intervalos_ordenados(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "solar")
    prev = backtest.correr(ex, "solar", n_semanas=6, min_dias_treino=100)
    assert (prev["lightgbm_p10"] <= prev["lightgbm"] + 1e-9).all()
    assert (prev["lightgbm"] <= prev["lightgbm_p90"] + 1e-9).all()
    assert (prev["lightgbm_p10"] >= 0).all()  # produção não negativa
    t = backtest.resumir_intervalos(prev)
    assert set(t["modelo"]) == {"lightgbm", "naive_empirico"}
    assert t["cobertura"].between(0, 100).all()
    assert "Cobertura" in backtest.tabela_intervalos_markdown(t)


def test_intervalo_nao_altera_a_previsao_central(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "consumo")
    com = backtest.correr(ex, "consumo", n_semanas=2, min_dias_treino=100)
    from eletricidade.modelos import ModeloLGBM

    treino = ex[ex["dia"] < com["semana"].min()]
    sem = ModeloLGBM("consumo").treinar(treino, intervalos=False)
    primeira = ex[
        (ex["origem"] >= com["semana"].min()) & (ex["origem"] < com["semana"].min() + pd.Timedelta(days=7))
    ]
    primeira = primeira.dropna(subset=["y"])
    np.testing.assert_allclose(
        sem.prever(primeira), com[com["semana"] == com["semana"].min()]["lightgbm"].to_numpy()
    )


def test_alvo_normalizado_pela_capacidade(horario_sintetico, monkeypatch):
    from eletricidade import config
    from eletricidade.modelos import ModeloLGBM

    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "eolica")
    assert "capacidade" in ex and "capacidade" not in features.construir_exemplos(grade, None, "consumo")
    # a capacidade só usa dias até D-1: mudar o próprio dia não a altera
    dia = ex["dia"].iloc[len(ex) // 2]
    alterada = grade.copy()
    alterada.loc[alterada.index.get_level_values("dia") == dia.date(), "eolica"] = 1e9
    ex2 = features.construir_exemplos(alterada, None, "eolica")
    sel = (ex["dia"] == dia) & (ex["lead"] == 1)
    np.testing.assert_allclose(
        ex.loc[sel, "capacidade"], ex2.loc[(ex2["dia"] == dia) & (ex2["lead"] == 1), "capacidade"]
    )

    treino = ex[ex["dia"] < dia]
    m = ModeloLGBM("eolica").treinar(treino)
    assert m.normalizado
    teste = ex[(ex["dia"] >= dia) & ex["y"].notna()].head(200)
    p = m.prever(teste)
    assert np.isfinite(p).all() and (p >= 0).all()
    # um modelo guardado antes desta mudança (sem o atributo) não é reescalado
    antigo = ModeloLGBM("eolica")
    monkeypatch.setattr(config, "ALVOS_NORMALIZADOS", ())
    antigo.treinar(treino.drop(columns="capacidade"))
    del antigo.__dict__["normalizado"]
    assert not antigo.normalizado and np.isfinite(antigo.prever(teste.drop(columns="capacidade"))).all()
