"""Previsões meteorológicas tal como eram conhecidas no passado (Open-Meteo).

Usa a API "Previous Runs" (``<variavel>_previous_dayN``): o valor previsto para
a hora t pela corrida de N dias antes. Isto evita dar ao modelo, no treino e no
backtest, meteorologia melhor do que a que teria em produção.

Regra (conservadora) usada no treino, no backtest e em produção:
    previsão emitida à meia-noite de D
      alvo em D   -> previous_day2
      alvo em D+1 -> previous_day3
Todas as corridas usadas já estavam publicadas à hora de emissão.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)

# dia do horizonte (1 = D, 2 = D+1) -> N de previous_dayN
LEAD_METEO = {1: 2, 2: 3}


class ErroMeteo(RuntimeError):
    pass


def _variaveis_pedido() -> list[str]:
    return [f"{v}_previous_day{n}" for v in config.VARIAVEIS_METEO for n in sorted(LEAD_METEO.values())]


def descarregar(inicio: date, fim: date, tentativas: int = 4) -> list[dict]:
    """Um pedido para todos os pontos. Devolve uma lista (um elemento por ponto)."""
    params = {
        "latitude": ",".join(f"{p.lat}" for p in config.PONTOS),
        "longitude": ",".join(f"{p.lon}" for p in config.PONTOS),
        "hourly": ",".join(_variaveis_pedido()),
        "start_date": inicio.isoformat(),
        "end_date": fim.isoformat(),
        "timezone": "GMT",
        "wind_speed_unit": "ms",
    }
    espera = 5.0
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(
                config.OPEN_METEO_PREVIOUS_RUNS,
                params=params,
                timeout=(15, 120),
                headers={"User-Agent": config.USER_AGENT},
            )
            resp.raise_for_status()
            dados = resp.json()
            return dados if isinstance(dados, list) else [dados]
        except (requests.RequestException, ValueError) as erro:
            log.warning("Open-Meteo %s..%s: tentativa %d falhou (%s)", inicio, fim, tentativa, erro)
            if tentativa == tentativas:
                raise ErroMeteo(str(erro)) from erro
            time.sleep(espera)
            espera *= 2
    raise AssertionError("inalcançável")


def interpretar(locais: list[dict]) -> pd.DataFrame:
    """Tabela longa: ts_utc, ponto, variavel, lead_dias, valor."""
    if len(locais) != len(config.PONTOS):
        raise ErroMeteo(f"Esperava {len(config.PONTOS)} pontos, recebi {len(locais)}")
    partes = []
    for ponto, local in zip(config.PONTOS, locais, strict=True):
        horario = local.get("hourly")
        if not isinstance(horario, dict) or "time" not in horario:
            raise ErroMeteo(f"Ponto {ponto.nome}: resposta sem 'hourly.time'")
        ts = pd.to_datetime(horario["time"], utc=True)
        for var in config.VARIAVEIS_METEO:
            for lead, n in LEAD_METEO.items():
                chave = f"{var}_previous_day{n}"
                if chave not in horario:
                    raise ErroMeteo(f"Ponto {ponto.nome}: falta a variável {chave}")
                partes.append(
                    pd.DataFrame(
                        {
                            "ts_utc": ts,
                            "ponto": ponto.nome,
                            "variavel": var,
                            "lead_dias": lead,
                            "valor": pd.to_numeric(pd.Series(horario[chave]), errors="coerce"),
                        }
                    )
                )
    return pd.concat(partes, ignore_index=True)


# --- armazenamento incremental (por mês) --------------------------------------


def _meses(inicio: date, fim: date) -> list[pd.Period]:
    return list(pd.period_range(pd.Period(inicio, "M"), pd.Period(fim, "M"), freq="M"))


def caminho_bruto(mes: pd.Period, raiz: Path | None = None) -> Path:
    return (raiz or config.DIR_METEO_BRUTO) / f"{mes}.json"


def atualizar(inicio: date, fim: date, raiz: Path | None = None) -> list[str]:
    """Descarrega meses em falta; o mês de ``fim`` e o anterior são sempre revistos."""
    meses = _meses(inicio, fim)
    ultimos = set(meses[-2:])
    feitos = []
    for mes in meses:
        destino = caminho_bruto(mes, raiz)
        if destino.exists() and mes not in ultimos:
            continue
        a = max(mes.start_time.date(), inicio)
        b = min(mes.end_time.date(), fim)
        locais = descarregar(a, b)
        interpretar(locais)  # valida antes de gravar
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(locais), encoding="utf-8")
        feitos.append(str(mes))
        time.sleep(1.0)
    return feitos


def construir_horario(raiz: Path | None = None) -> pd.DataFrame:
    raiz = raiz or config.DIR_METEO_BRUTO
    ficheiros = sorted(raiz.glob("*.json"))
    if not ficheiros:
        raise ErroMeteo(f"Sem dados meteorológicos em {raiz}")
    longo = pd.concat(
        [interpretar(json.loads(f.read_text(encoding="utf-8"))) for f in ficheiros], ignore_index=True
    )
    return longo.drop_duplicates(["ts_utc", "ponto", "variavel", "lead_dias"], keep="last")


def agregar_por_grupo(longo: pd.DataFrame) -> pd.DataFrame:
    """Média por grupo de pontos -> colunas ``<grupo>__<variavel>``, índice (ts_utc, lead_dias)."""
    grupos = {p.nome: p.grupo for p in config.PONTOS}
    tabela = longo.assign(grupo=longo["ponto"].map(grupos))
    tabela = (
        tabela.groupby(["ts_utc", "lead_dias", "grupo", "variavel"])["valor"]
        .mean()
        .unstack(["grupo", "variavel"])
    )
    tabela.columns = [f"{g}__{v}" for g, v in tabela.columns]
    return tabela.sort_index()
