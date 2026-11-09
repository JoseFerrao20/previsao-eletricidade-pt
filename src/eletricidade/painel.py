"""Painel estático (GitHub Pages): previsões, valores reais e histórico do erro."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import config
from .producao import atraso_emissao_horas

NOMES = {"consumo": "Consumo", "eolica": "Eólica", "solar": "Solar"}


def _ts_local(dia: pd.Series, hora: pd.Series) -> list[str]:
    return [f"{d:%Y-%m-%d}T{int(h):02d}:00" for d, h in zip(pd.to_datetime(dia), hora, strict=True)]


def dados_painel(
    grade: pd.DataFrame,
    previsoes: pd.DataFrame,
    hist_erro: pd.DataFrame,
    relatorio: dict | None,
    resumo_backtest: pd.DataFrame | None,
    dias: int = 14,
) -> dict:
    """Estrutura JSON consumida pela página. Só agregados horários e métricas."""
    saida: dict = {"gerado_em": f"{datetime.now(UTC):%Y-%m-%d %H:%M} UTC", "alvos": {}}
    ultima_origem = previsoes["origem"].max() if not previsoes.empty else None
    inicio = (ultima_origem or pd.Timestamp.now()) - pd.Timedelta(days=dias)
    reais = grade.reset_index()
    reais["dia"] = pd.to_datetime(reais["dia"])
    reais = reais[reais["dia"] >= inicio]
    for alvo in config.ALVOS:
        bloco: dict = {"nome": NOMES[alvo]}
        r = reais.dropna(subset=[alvo])
        bloco["real"] = {"x": _ts_local(r["dia"], r["hora"]), "y": r[alvo].round(1).tolist()}
        if not previsoes.empty:
            p = previsoes[(previsoes["alvo"] == alvo) & (previsoes["dia"] >= inicio)]
            # Histórico: previsão a D (lead 1) de cada origem; mais a última emissão completa (48 h).
            hist = p[p["lead"] == 1]
            ultima = p[p["origem"] == ultima_origem]
            serie = pd.concat([hist[hist["origem"] < ultima_origem], ultima]).sort_values(["dia", "hora"])
            serie = serie.drop_duplicates(["dia", "hora"], keep="last")
            bloco["previsao"] = {
                "x": _ts_local(serie["dia"], serie["hora"]),
                "y": serie["previsao"].round(1).tolist(),
            }
            if {"p10", "p90"} <= set(serie.columns):
                banda = serie[serie["origem"] == ultima_origem].dropna(subset=["p10", "p90"])
                if not banda.empty:
                    bloco["intervalo"] = {
                        "x": _ts_local(banda["dia"], banda["hora"]),
                        "baixo": banda["p10"].round(1).tolist(),
                        "alto": banda["p90"].round(1).tolist(),
                    }
            bloco["naive"] = {
                "x": _ts_local(serie["dia"], serie["hora"]),
                "y": serie["naive_sazonal"].round(1).tolist(),
            }
            bloco["ultima_origem"] = f"{ultima_origem:%Y-%m-%d}"
            if "emitida_em" in ultima and ultima["emitida_em"].notna().any():
                emitida = pd.Timestamp(ultima["emitida_em"].dropna().iloc[0]).tz_convert(config.FUSO)
                bloco["emitida_em"] = f"{emitida:%d/%m %H:%M}"
                bloco["atraso_horas"] = round(atraso_emissao_horas(ultima), 1)
            bloco["versao"] = str(ultima["versao"].iloc[0]) if not ultima.empty else None
        if not hist_erro.empty:
            h = hist_erro[(hist_erro["alvo"] == alvo) & (hist_erro["lead"] == 1)]
            bloco["erro"] = {
                m: {"x": [f"{d:%Y-%m-%d}" for d in pd.to_datetime(g["dia"])], "y": g["MAE"].round(1).tolist()}
                for m, g in h.groupby("modelo")
                if m in ("previsao", "naive_sazonal")
            }
        if relatorio and alvo in relatorio.get("alvos", {}):
            bloco["monitor"] = relatorio["alvos"][alvo]
        saida["alvos"][alvo] = bloco
    if resumo_backtest is not None and not resumo_backtest.empty:
        saida["backtest"] = resumo_backtest.round(3).to_dict(orient="records")
    return saida


def escrever(dados: dict, destino: Path | None = None) -> Path:
    destino = destino or config.SITE / "index.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    modelo = (Path(__file__).parent / "painel_modelo.html").read_text(encoding="utf-8")
    json_txt = json.dumps(dados, ensure_ascii=False, default=str).replace("</", "<\\/")
    destino.write_text(modelo.replace("/*__DADOS__*/null", json_txt), encoding="utf-8")
    return destino
