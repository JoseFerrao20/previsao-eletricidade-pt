"""Ciclo de produção completo sobre dados SINTÉTICOS (treino, promoção, previsão, monitor, painel)."""

import json

import numpy as np
import pandas as pd
import pytest

from eletricidade import config, features, monitor, painel, producao, registo


@pytest.fixture
def estado(tmp_path, monkeypatch):
    for nome, valor in {
        "ESTADO": tmp_path / "estado",
        "REGISTO": tmp_path / "estado" / "registo",
        "DIR_PREVISOES": tmp_path / "estado" / "previsoes",
        "DIR_MONITOR": tmp_path / "estado" / "monitor",
        "SITE": tmp_path / "site",
    }.items():
        monkeypatch.setattr(config, nome, valor)
    return tmp_path


def test_ciclo_completo(estado, horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    corte = pd.Timestamp("2025-04-01")
    passado = grade[pd.to_datetime(grade.index.get_level_values("dia")) < corte]

    # 1. treino + promoção (sem campeão anterior: basta bater o naive sazonal)
    for alvo in config.ALVOS:
        ex = features.construir_exemplos(passado, None, alvo)
        r = producao.treinar_e_promover(alvo, ex, semanas_gate=2)
        assert r["MAE_backtest"] > 0
    campeoes = registo.campeoes()
    assert set(campeoes) <= set(config.ALVOS) and "consumo" in campeoes
    _, meta = registo.carregar("consumo")
    assert meta["seed"] == config.SEED and meta["treino"]["dia_fim"] < "2025-04-01"
    assert meta["perfil_features"]  # perfil para o drift

    # alvos sem campeão (se o sintético não bater o naive) recebem um para o resto do teste
    for alvo in config.ALVOS:
        if alvo not in campeoes:
            versao = sorted(p.name for p in (config.REGISTO / alvo).iterdir())[-1]
            registo.promover(alvo, versao, "teste")

    # 2. previsões diárias, sem ver o futuro
    for k in range(10):
        origem = corte + pd.Timedelta(days=k)
        prev = producao.prever(origem, grade)
        assert len(prev) == 48 * len(config.ALVOS)
        assert set(prev["dia"]) == {origem, origem + pd.Timedelta(days=1)}
        producao.guardar_previsao(prev)
    # a previsão não muda se o futuro (a partir da origem) for alterado
    alterada = grade.copy()
    alterada[pd.to_datetime(alterada.index.get_level_values("dia")) >= corte] = 0.0
    a = producao.prever(corte, grade)["previsao"].to_numpy()
    b = producao.prever(corte, alterada)["previsao"].to_numpy()
    np.testing.assert_allclose(a, b)

    # 3. monitor
    previsoes = monitor.carregar_previsoes()
    realizadas = monitor.juntar_reais(previsoes, grade)
    assert len(realizadas) == len(previsoes)
    metas = {alvo: registo.carregar(alvo)[1] for alvo in config.ALVOS}
    recentes = {alvo: features.construir_exemplos(grade, None, alvo) for alvo in config.ALVOS}
    rel = monitor.avaliar(realizadas, recentes, metas, pd.Timestamp("2025-04-11"))
    assert set(rel["alvos"]) == set(config.ALVOS)
    assert rel["alvos"]["consumo"]["n_horas"] > 24
    hist = monitor.historico_erro(realizadas)
    monitor.guardar(rel, hist)
    assert (config.DIR_MONITOR / "relatorio.md").exists()

    # 4. painel
    dados = painel.dados_painel(grade, previsoes, hist, rel, None)
    destino = painel.escrever(dados)
    html = destino.read_text(encoding="utf-8")
    assert "/*__DADOS__*/" not in html and '"consumo"' in html
    json.dumps(dados, default=str)


def test_drift_detetado_quando_a_distribuicao_muda():
    rng = np.random.default_rng(0)
    treino = pd.DataFrame({"x": rng.normal(0, 1, 5000)})
    perfil = registo.perfil_features(treino, ["x"])["x"]
    igual = monitor.psi(perfil["proporcoes"], perfil["limites"], rng.normal(0, 1, 500))
    mudou = monitor.psi(perfil["proporcoes"], perfil["limites"], rng.normal(1.5, 1, 500))
    assert igual < 0.1 < config.LIMIAR_PSI < mudou


def test_degradacao_gera_alerta():
    dias = pd.date_range("2025-01-01", periods=7)
    linhas = pd.DataFrame(
        [(d, h, 1, "consumo", 5000.0, 5000.0 + 900, 5000.0 + 300) for d in dias for h in range(24)],
        columns=["dia", "hora", "lead", "alvo", "y", "previsao", "naive_sazonal"],
    )
    meta = {"versao": "v", "metricas": {"MAE_backtest": 400.0}, "perfil_features": {}}
    rel = monitor.avaliar(linhas, {}, {"consumo": meta}, pd.Timestamp("2025-01-08"))
    sinais = rel["alvos"]["consumo"]["sinais"]
    assert rel["alerta"] and rel["retreinar"]
    assert any("degradação" in s for s in sinais) and any("naive" in s for s in sinais)
