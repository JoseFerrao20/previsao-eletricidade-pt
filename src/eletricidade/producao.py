"""Operações de produção: carregar dados, treinar com regra de promoção, emitir previsões."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import backtest, config, features, meteo, metricas, monitor, registo
from .modelos import REFERENCIAS, ModeloLGBM

log = logging.getLogger(__name__)


def carregar_grade() -> pd.DataFrame:
    return features.para_grade_local(pd.read_parquet(config.FICH_REN_HORARIO))


def carregar_meteo() -> pd.DataFrame | None:
    if not config.FICH_METEO_HORARIO.exists():
        log.warning("Sem meteorologia: os modelos treinam só com histórico e calendário")
        return None
    return meteo.agregar_por_grupo(pd.read_parquet(config.FICH_METEO_HORARIO))


def exemplos(alvo: str, grade=None, grupos=None, ate: pd.Timestamp | None = None) -> pd.DataFrame:
    grade = carregar_grade() if grade is None else grade
    return features.construir_exemplos(grade, grupos, alvo, ate=ate)


def treinar_e_promover(alvo: str, ex: pd.DataFrame, semanas_gate: int = 4, raiz: Path | None = None) -> dict:
    """Treina um candidato e promove-o só se passar a regra.

    Regra (sem olhar para dados que nenhum dos dois viu):
      1. backtest semana a semana do candidato nas últimas ``semanas_gate`` semanas;
      2. tem de bater o naive sazonal nessas semanas;
      3. se já houver campeão com previsões realizadas nessas semanas, o MAE do
         candidato não pode exceder TOLERANCIA_PROMOCAO × o MAE realizado do campeão,
         nas mesmas horas.
    Se passar, o candidato é retreinado com todos os dados e passa a campeão.
    """
    bt = backtest.correr(ex, alvo, n_semanas=semanas_gate)
    bt = bt.dropna(subset=["y", "lightgbm", "naive_sazonal"])
    mae_cand = metricas.mae(bt["y"], bt["lightgbm"])
    mae_naive = metricas.mae(bt["y"], bt["naive_sazonal"])
    mae_por_lead = {int(k): metricas.mae(g["y"], g["lightgbm"]) for k, g in bt.groupby("lead")}

    motivo_rejeicao = None
    mae_campeao = None
    if mae_cand >= mae_naive:
        motivo_rejeicao = f"não bate o naive sazonal ({mae_cand:.0f} vs {mae_naive:.0f} MW)"
    else:
        hist = monitor.carregar_previsoes()
        if not hist.empty:
            hist = hist[hist["alvo"] == alvo].merge(
                bt[["dia", "hora", "lead", "lightgbm", "y"]], on=["dia", "hora", "lead"], how="inner"
            )
            if len(hist) >= 24 * 7:
                mae_campeao = metricas.mae(hist["y"], hist["previsao"])
                mae_cand_comum = metricas.mae(hist["y"], hist["lightgbm"])
                if mae_cand_comum > config.TOLERANCIA_PROMOCAO * mae_campeao:
                    motivo_rejeicao = (
                        "pior do que o campeão nas mesmas horas "
                        f"({mae_cand_comum:.0f} vs {mae_campeao:.0f} MW)"
                    )

    treino = ex.dropna(subset=["y"])
    modelo = ModeloLGBM(alvo).treinar(treino)
    resumo = {
        "MAE_backtest": mae_cand,
        "MAE_backtest_por_lead": mae_por_lead,
        "MAE_naive_sazonal_backtest": mae_naive,
        "MAE_campeao_realizado": mae_campeao,
        "semanas_gate": semanas_gate,
    }
    versao = registo.guardar(modelo, treino, resumo, raiz)
    if motivo_rejeicao:
        registo.registar_decisao(alvo, versao, "rejeitado", motivo_rejeicao, raiz)
        log.warning("%s: candidato %s rejeitado: %s", alvo, versao, motivo_rejeicao)
    else:
        motivo = f"MAE backtest {mae_cand:.0f} MW vs naive sazonal {mae_naive:.0f} MW"
        registo.promover(alvo, versao, motivo, raiz)
        log.info("%s: %s promovido (%s)", alvo, versao, motivo)
    registo.limpar(alvo, raiz=raiz)
    return {
        "alvo": alvo,
        "versao": versao,
        "promovido": motivo_rejeicao is None,
        "motivo": motivo_rejeicao or "ok",
        **resumo,
    }


def prever(origem: pd.Timestamp, grade=None, grupos=None, raiz: Path | None = None) -> pd.DataFrame:
    """Previsão horária para D e D+1 emitida à meia-noite local de ``origem`` (= D)."""
    origem = pd.Timestamp(origem).normalize()
    grade = carregar_grade() if grade is None else grade
    ultimo_real = pd.Timestamp(max(grade.dropna(how="all").index.get_level_values("dia")))
    if ultimo_real < origem - pd.Timedelta(days=1):
        log.warning(
            "Dados reais só até %s; a previsão de %s terá lags em falta", ultimo_real.date(), origem.date()
        )
    partes = []
    for alvo in config.ALVOS:
        modelo, meta = registo.carregar(alvo, raiz=raiz)
        # Só valores conhecidos antes da emissão entram (corta tudo a partir de D).
        grade_passado = grade[pd.to_datetime(grade.index.get_level_values("dia")) < origem]
        ex = features.construir_exemplos(
            grade_passado, grupos, alvo, ate=origem + pd.Timedelta(days=config.DIAS_HORIZONTE - 1)
        )
        ex = ex[ex["origem"] == origem]
        if len(ex) != 24 * config.DIAS_HORIZONTE:
            raise RuntimeError(f"{alvo}: esperava {24 * config.DIAS_HORIZONTE} linhas, tenho {len(ex)}")
        bloco = ex[["origem", "dia", "hora", "lead"]].copy()
        bloco["alvo"] = alvo
        bloco["versao"] = meta["versao"]
        bloco["previsao"] = modelo.prever(ex)
        for nome in REFERENCIAS:
            bloco[nome] = ex[REFERENCIAS[nome]].to_numpy()
        partes.append(bloco)
    return pd.concat(partes, ignore_index=True)


def guardar_previsao(previsao: pd.DataFrame, pasta: Path | None = None) -> Path:
    pasta = pasta or config.DIR_PREVISOES
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{previsao['origem'].iloc[0]:%Y-%m-%d}.parquet"
    previsao.to_parquet(destino, index=False)
    return destino
