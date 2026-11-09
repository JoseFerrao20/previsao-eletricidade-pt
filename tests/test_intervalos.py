"""Calibração conformal dos intervalos (dados sintéticos)."""

import numpy as np
import pandas as pd

from eletricidade import backtest, intervalos


def _previsoes(n_semanas=20, desvio=100.0, largura=50.0, seed=0):
    """Previsões com intervalos estreitos de mais: o erro real tem desvio >> largura."""
    rng = np.random.default_rng(seed)
    linhas = []
    for k in range(n_semanas):
        semana = pd.Timestamp("2025-01-06") + pd.Timedelta(weeks=k)
        for d in range(7):
            for h in range(24):
                y = 5000 + rng.normal(0, desvio)
                linhas.append((semana, semana + pd.Timedelta(days=d), h, 1, "consumo", y, 5000.0))
    df = pd.DataFrame(linhas, columns=["semana", "dia", "hora", "lead", "alvo", "y", "lightgbm"])
    df["lightgbm_p10"] = df["lightgbm"] - largura
    df["lightgbm_p90"] = df["lightgbm"] + largura
    df["naive_sazonal"] = df["lightgbm"]
    return df


def test_calibracao_corrige_cobertura_sem_olhar_para_a_semana():
    df = intervalos.calibrar_backtest(_previsoes())
    # as primeiras semanas não têm passado suficiente
    primeiras = df["semana"] < df["semana"].min() + pd.Timedelta(weeks=intervalos.MIN_SEMANAS)
    assert df.loc[primeiras, "lightgbm_p10c"].isna().all()
    resto = df[~primeiras]
    crua = ((resto["y"] >= resto["lightgbm_p10"]) & (resto["y"] <= resto["lightgbm_p90"])).mean()
    cal = ((resto["y"] >= resto["lightgbm_p10c"]) & (resto["y"] <= resto["lightgbm_p90c"])).mean()
    assert crua < 0.5 and abs(cal - 0.8) < 0.05


def test_calibracao_nao_usa_a_propria_semana():
    df = _previsoes()
    ultima = df["semana"] == df["semana"].max()
    alterado = df.copy()
    alterado.loc[ultima, "y"] += 10_000  # semana avaliada absurda
    a = intervalos.calibrar_backtest(df).loc[ultima, "lightgbm_p90c"]
    b = intervalos.calibrar_backtest(alterado).loc[ultima, "lightgbm_p90c"]
    np.testing.assert_allclose(a, b)


def test_resumo_compara_nas_mesmas_linhas():
    t = backtest.resumir_intervalos(intervalos.calibrar_backtest(_previsoes()))
    assert {"lightgbm", "lightgbm_calibrado", "naive_empirico"} <= set(t["modelo"])
    assert t["n"].nunique() == 1


def test_producao_aplica_a_calibracao_do_ultimo_backtest(tmp_path):
    from eletricidade import producao

    bt = intervalos.calibrar_backtest(_previsoes())
    intervalos.ajustes_producao(bt).to_csv(tmp_path / producao.FICH_CALIBRACAO, index=False)
    prev = pd.DataFrame(
        {"alvo": "consumo", "lead": 1, "hora": range(24), "previsao": 5000.0, "p10": 4950.0, "p90": 5050.0}
    )
    cal = producao.calibrar_intervalos(prev, pasta=tmp_path)
    assert cal["intervalo_calibrado"].all()
    assert (cal["p10"] < 4950).all() and (cal["p90"] > 5050).all()
    assert not producao.calibrar_intervalos(prev, pasta=tmp_path / "nada")["intervalo_calibrado"].any()


def _previsoes_com_mudanca(n_semanas=30, seed=1):
    """O erro real duplica a meio: a calibração estática fica para trás, a adaptativa acompanha."""
    df = _previsoes(n_semanas=n_semanas, seed=seed)
    rng = np.random.default_rng(seed + 1)
    meio = df["semana"] >= df["semana"].min() + pd.Timedelta(weeks=n_semanas // 2)
    df.loc[meio, "y"] = 5000 + rng.normal(0, 250, meio.sum())
    return df


def test_aci_recupera_cobertura_depois_de_uma_mudanca():
    df = _previsoes_com_mudanca()
    est = intervalos.calibrar_backtest(df, adaptativo=False)
    aci = intervalos.calibrar_backtest(df, adaptativo=True)
    fim = df["semana"] >= df["semana"].max() - pd.Timedelta(weeks=9)  # semanas depois da mudança

    def cobertura(t):
        t = t[fim]
        return ((t["y"] >= t["lightgbm_p10c"]) & (t["y"] <= t["lightgbm_p90c"])).mean()

    assert abs(cobertura(aci) - 0.8) < abs(cobertura(est) - 0.8)
    assert aci.attrs["niveis"] and all(0.5 <= v["alto"] <= 0.995 for v in aci.attrs["niveis"].values())


def test_aci_nao_usa_a_propria_semana():
    df = _previsoes_com_mudanca()
    ultima = df["semana"] == df["semana"].max()
    alterado = df.copy()
    alterado.loc[ultima, "y"] += 10_000
    a = intervalos.calibrar_backtest(df).loc[ultima, "lightgbm_p90c"]
    b = intervalos.calibrar_backtest(alterado).loc[ultima, "lightgbm_p90c"]
    np.testing.assert_allclose(a, b)


def test_producao_recebe_os_niveis_finais():
    aci = intervalos.calibrar_backtest(_previsoes_com_mudanca())
    tabela = intervalos.ajustes_producao(aci)
    assert {"nivel_baixo", "nivel_alto"} <= set(tabela.columns)
