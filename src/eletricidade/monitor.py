"""Vigilância em produção: erro realizado das previsões emitidas e drift das features.

Sinais (por alvo):
  - degradação: MAE realizado dos últimos N dias / MAE de referência do backtest
    do campeão > LIMIAR_DEGRADACAO;
  - pior do que o naive sazonal no mesmo período (com as mesmas horas);
Qualquer um destes sinais -> alerta (issue no GitHub) e pedido de retreino.

Avisos (não disparam retreino):
  - drift da meteorologia prevista: PSI dos últimos 14 dias face à mesma época
    do ano (mesmo intervalo do calendário ±7 dias) nos dados anteriores > LIMIAR_PSI.

Porquê só meteorologia e só com referência sazonal: comparar uma semana de
novembro com dois anos inteiros dá "drift" todos os dias no calendário, na
temperatura e na radiação (foi o que aconteceu na primeira execução real). Os
lags do próprio alvo também não entram: a sua mudança já é medida pelo erro
realizado. Um drift sem degradação do erro não é acionável; com degradação, o
erro já dispara o alerta.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, metricas
from .registo import perfil_features

JANELA_DRIFT_DIAS = 14
RAIO_SAZONAL_DIAS = 7  # margem à volta da janela, nos anos anteriores


def psi(esperado: list[float], limites: list[float], valores: np.ndarray, eps: float = 1e-4) -> float:
    valores = valores[np.isfinite(valores)]
    if valores.size == 0:
        return float("nan")
    contagens = np.bincount(np.searchsorted(limites, valores, side="right"), minlength=len(esperado))
    obs = np.clip(contagens / valores.size, eps, None)
    esp = np.clip(np.asarray(esperado, dtype=float), eps, None)
    return float(np.sum((obs - esp) * np.log(obs / esp)))


def colunas_drift(exemplos: pd.DataFrame) -> list[str]:
    """Features exógenas contínuas: a meteorologia prevista, só as médias ``grupo__variavel``.

    As séries por ponto ficam de fora: são muitas e ruidosas, e as médias já resumem a
    mudança; o proxy de potência é uma transformação do vento e também fica de fora.
    """
    return [
        c
        for c in exemplos.columns
        if "__" in c and not c.startswith(config.PREFIXO_PONTO) and not c.endswith("potencia_proxy")
    ]


def drift_sazonal(exemplos: pd.DataFrame, hoje: pd.Timestamp) -> dict[str, float]:
    """PSI da janela recente face à mesma época do ano nos dados anteriores a essa janela."""
    colunas = colunas_drift(exemplos)
    if not colunas or exemplos.empty:
        return {}
    inicio = hoje - pd.Timedelta(days=JANELA_DRIFT_DIAS)
    dia = pd.to_datetime(exemplos["dia"])
    recente = exemplos[(exemplos["origem"] > inicio) & (exemplos["origem"] <= hoje)]
    centro = (inicio + pd.Timedelta(days=JANELA_DRIFT_DIAS / 2)).day_of_year
    distancia = np.abs(dia.dt.day_of_year - centro)
    distancia = np.minimum(distancia, 365 - distancia)
    referencia = exemplos[(dia < inicio) & (distancia <= RAIO_SAZONAL_DIAS + JANELA_DRIFT_DIAS / 2)]
    if len(referencia) < 24 * 30 or recente.empty:
        return {}
    resultado = {}
    for coluna, perfil in perfil_features(referencia, colunas).items():
        resultado[coluna] = psi(
            perfil["proporcoes"], perfil["limites"], recente[coluna].to_numpy(dtype=float)
        )
    return resultado


def carregar_previsoes(pasta: Path | None = None) -> pd.DataFrame:
    pasta = pasta or config.DIR_PREVISOES
    ficheiros = sorted(pasta.glob("*.parquet"))
    if not ficheiros:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in ficheiros], ignore_index=True)


def juntar_reais(previsoes: pd.DataFrame, grade: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta o valor real (``y``) a cada previsão emitida; mantém só as já observadas."""
    reais = grade.stack().rename("y").reset_index()
    reais.columns = ["dia", "hora", "alvo", "y"]
    reais["dia"] = pd.to_datetime(reais["dia"])
    out = previsoes.drop(columns=["y"], errors="ignore").merge(reais, on=["dia", "hora", "alvo"], how="inner")
    return out.dropna(subset=["y"])


MODELOS_MONITOR = ("previsao", "naive_sazonal", "media_semana", "persistencia")


def historico_erro(realizadas: pd.DataFrame) -> pd.DataFrame:
    """MAE diário por alvo × lead × modelo (para o painel)."""
    linhas = []
    for (alvo, dia, lead), g in realizadas.groupby(["alvo", "dia", "lead"]):
        g = g.dropna(subset=list(MODELOS_MONITOR))
        if g.empty:
            continue
        for m in MODELOS_MONITOR:
            linhas.append(
                {"alvo": alvo, "dia": dia, "lead": lead, "modelo": m, "MAE": metricas.mae(g["y"], g[m])}
            )
    return pd.DataFrame(linhas)


def avaliar(
    realizadas: pd.DataFrame,
    exemplos: dict[str, pd.DataFrame],
    metas: dict[str, dict],
    hoje: pd.Timestamp,
) -> dict:
    """Relatório com sinais por alvo e a decisão de retreino."""
    inicio = hoje - pd.Timedelta(days=config.JANELA_MONITOR_DIAS)
    relatorio = {"gerado_em": datetime.now(UTC).isoformat(timespec="seconds"), "alvos": {}}
    for alvo, meta in metas.items():
        sinais: list[str] = []
        r = realizadas[(realizadas["alvo"] == alvo) & (realizadas["dia"] >= inicio)]
        r = r.dropna(subset=["previsao", "naive_sazonal"])
        info: dict = {"versao": meta.get("versao"), "n_horas": len(r)}
        referencia = meta.get("metricas", {}).get("MAE_backtest")
        if len(r) >= 24:
            mae_m = metricas.mae(r["y"], r["previsao"])
            mae_n = metricas.mae(r["y"], r["naive_sazonal"])
            info.update({"MAE_realizado": mae_m, "MAE_naive_sazonal": mae_n, "MAE_referencia": referencia})
            if {"p10", "p90"} <= set(r.columns) and r["p10"].notna().any():
                ri = r.dropna(subset=["p10", "p90"])
                info["cobertura_80"] = float(100 * ((ri["y"] >= ri["p10"]) & (ri["y"] <= ri["p90"])).mean())
            if referencia and mae_m / referencia > config.LIMIAR_DEGRADACAO:
                sinais.append(
                    f"degradação: MAE {mae_m:.0f} MW = {mae_m / referencia:.2f}× "
                    f"a referência ({referencia:.0f})"
                )
            if mae_m > mae_n:
                sinais.append(f"pior do que o naive sazonal ({mae_m:.0f} vs {mae_n:.0f} MW)")
        else:
            info["nota"] = "menos de 24 horas com valores reais na janela"

        ex = exemplos.get(alvo)
        drift = drift_sazonal(ex, hoje) if ex is not None else {}
        info["psi"] = {k: round(v, 3) for k, v in drift.items() if np.isfinite(v)}
        info["avisos"] = [
            f"meteorologia invulgar para a época: '{c}' (PSI {v:.2f})"
            for c, v in info["psi"].items()
            if v > config.LIMIAR_PSI
        ]
        info["sinais"] = sinais
        relatorio["alvos"][alvo] = info
    relatorio["alerta"] = any(a["sinais"] for a in relatorio["alvos"].values())
    relatorio["retreinar"] = relatorio["alerta"]
    return relatorio


def atrasos_emissao(previsoes: pd.DataFrame, dias: int = 7) -> dict:
    """Atraso (h) entre a meia-noite de Lisboa e a emissão real, nas últimas origens."""
    if previsoes.empty or "emitida_em" not in previsoes:
        return {}
    por_origem = previsoes.dropna(subset=["emitida_em"]).groupby("origem")["emitida_em"].first()
    if por_origem.empty:
        return {}
    meia_noite = pd.DatetimeIndex(por_origem.index).tz_localize(config.FUSO)
    horas = (
        pd.DatetimeIndex(pd.to_datetime(por_origem.to_numpy(), utc=True)) - meia_noite
    ).total_seconds() / 3600
    horas = pd.Series(horas, index=por_origem.index).sort_index().tail(dias)
    return {
        "ultima_origem": f"{horas.index[-1]:%Y-%m-%d}",
        "atraso_ultima_h": round(float(horas.iloc[-1]), 1),
        "atraso_mediano_h": round(float(horas.median()), 1),
        "atraso_maximo_h": round(float(horas.max()), 1),
        "origens": len(horas),
    }


def markdown(relatorio: dict) -> str:
    linhas = [f"Relatório do monitor ({relatorio['gerado_em']})", ""]
    if e := relatorio.get("emissao"):
        linhas += [
            f"Emissão: a previsão de {e['ultima_origem']} saiu {e['atraso_ultima_h']} h depois da "
            f"meia-noite; nas últimas {e['origens']} origens, mediana {e['atraso_mediano_h']} h e "
            f"máximo {e['atraso_maximo_h']} h.",
            "",
        ]
    for alvo, info in relatorio["alvos"].items():
        estado = "⚠️" if info["sinais"] else "✅"
        linhas.append(f"### {estado} {alvo} (modelo {info.get('versao')})")
        if "MAE_realizado" in info:
            linhas.append(
                f"- MAE realizado ({config.JANELA_MONITOR_DIAS} dias): {info['MAE_realizado']:.0f} MW · "
                f"naive sazonal: {info['MAE_naive_sazonal']:.0f} MW · "
                f"referência do backtest: {info['MAE_referencia'] or float('nan'):.0f} MW"
            )
        if "cobertura_80" in info:
            linhas.append(f"- cobertura realizada do intervalo a 80 %: {info['cobertura_80']:.0f} %")
        linhas += [f"- {s}" for s in info["sinais"]] or ["- sem sinais de degradação"]
        linhas += [f"- aviso: {a}" for a in info.get("avisos", [])]
        linhas.append("")
    if relatorio["retreinar"]:
        linhas.append("O retreino foi pedido automaticamente.")
    return "\n".join(linhas)


def guardar(relatorio: dict, hist: pd.DataFrame, pasta: Path | None = None) -> None:
    pasta = pasta or config.DIR_MONITOR
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "relatorio.json").write_text(
        json.dumps(relatorio, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (pasta / "relatorio.md").write_text(markdown(relatorio), encoding="utf-8")
    if not hist.empty:
        hist.to_csv(pasta / "historico_erro.csv", index=False)
