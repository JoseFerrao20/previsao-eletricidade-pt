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

import hashlib
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


def descarregar(inicio: date, fim: date, tentativas: int = 6) -> list[dict]:
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
    espera = 10.0  # 10, 20, 40, 80, 160 s: a API recusa por uns minutos quando está carregada
    for tentativa in range(1, tentativas + 1):
        try:
            resp = requests.get(
                config.OPEN_METEO_PREVIOUS_RUNS,
                params=params,
                timeout=(30, 180),
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


def assinatura() -> str:
    """Identifica a lista de pontos e variáveis: mudá-la obriga a novo download, sem misturar."""
    texto = json.dumps(
        [[(p.nome, p.lat, p.lon) for p in config.PONTOS], config.VARIAVEIS_METEO, LEAD_METEO],
        sort_keys=True,
    )
    return hashlib.sha1(texto.encode()).hexdigest()[:10]


def pasta_bruta() -> Path:
    return config.DIR_METEO_BRUTO / assinatura()


def caminho_bruto(mes: pd.Period, raiz: Path | None = None) -> Path:
    return (raiz or pasta_bruta()) / f"{mes}.json"


def atualizar(inicio: date, fim: date, raiz: Path | None = None) -> list[str]:
    """Descarrega meses em falta; o mês de ``fim`` e o anterior são sempre revistos."""
    meses = _meses(inicio, fim)
    ultimos = set(meses[-2:])
    feitos, falhas = [], {}
    for mes in meses:
        destino = caminho_bruto(mes, raiz)
        if destino.exists() and mes not in ultimos:
            continue
        a = max(mes.start_time.date(), inicio)
        b = min(mes.end_time.date(), fim)
        try:
            locais = descarregar(a, b)
            interpretar(locais)  # valida antes de gravar
        except ErroMeteo as erro:
            # Continua: os meses já obtidos ficam gravados (e na cache), e a próxima
            # execução só pede os que faltam.
            falhas[str(mes)] = str(erro)
            log.error("Open-Meteo %s: %s", mes, erro)
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(locais), encoding="utf-8")
        feitos.append(str(mes))
        time.sleep(1.0)
    if falhas:
        raise ErroMeteo(f"{len(falhas)} meses falharam ({', '.join(falhas)}); {len(feitos)} gravados")
    return feitos


def construir_horario(raiz: Path | None = None) -> pd.DataFrame:
    raiz = raiz or pasta_bruta()
    ficheiros = sorted(raiz.glob("*.json"))
    if not ficheiros:
        raise ErroMeteo(f"Sem dados meteorológicos em {raiz}")
    longo = pd.concat(
        [interpretar(json.loads(f.read_text(encoding="utf-8"))) for f in ficheiros], ignore_index=True
    )
    return longo.drop_duplicates(["ts_utc", "ponto", "variavel", "lead_dias"], keep="last")


def _com_proxy_eolico(longo: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta a variável ``potencia_proxy`` = min(v, V_NOMINAL)^3 por ponto (só vento)."""
    vento = longo[longo["variavel"] == "wind_speed_100m"]
    proxy = vento.assign(
        variavel="potencia_proxy", valor=vento["valor"].clip(0, config.V_NOMINAL_EOLICA) ** 3
    )
    return pd.concat([longo, proxy], ignore_index=True)


def agregar_por_grupo(longo: pd.DataFrame) -> pd.DataFrame:
    """Tabela larga, índice (ts_utc, lead_dias).

    - médias por grupo de pontos: ``<grupo>__<variavel>`` (um ponto pode estar em vários grupos);
    - séries por ponto das variáveis em METEO_POR_PONTO: ``ponto_<nome>__<variavel>``.
    """
    longo = _com_proxy_eolico(longo)
    grupos = pd.DataFrame([(p.nome, g) for p in config.PONTOS for g in p.grupos], columns=["ponto", "grupo"])
    por_grupo = (
        longo.merge(grupos, on="ponto")
        .groupby(["ts_utc", "lead_dias", "grupo", "variavel"])["valor"]
        .mean()
        .unstack(["grupo", "variavel"])
    )
    por_grupo.columns = [f"{g}__{v}" for g, v in por_grupo.columns]

    pedidos = {
        (p.nome, v)
        for grupo, variaveis in config.METEO_POR_PONTO.values()
        for p in config.PONTOS
        if grupo in p.grupos
        for v in variaveis
    }
    chave = pd.MultiIndex.from_frame(longo[["ponto", "variavel"]])
    sel = longo[chave.isin(list(pedidos))]
    por_ponto = sel.pivot_table(
        index=["ts_utc", "lead_dias"], columns=["ponto", "variavel"], values="valor", aggfunc="mean"
    )
    por_ponto.columns = [f"{config.PREFIXO_PONTO}{p}__{v}" for p, v in por_ponto.columns]
    return por_grupo.join(por_ponto, how="left").sort_index()


def colunas_por_ponto(alvo: str) -> list[str]:
    if alvo not in config.METEO_POR_PONTO:
        return []
    grupo, variaveis = config.METEO_POR_PONTO[alvo]
    return [
        f"{config.PREFIXO_PONTO}{p.nome}__{v}" for p in config.PONTOS if grupo in p.grupos for v in variaveis
    ]


def resumo_por_ponto(longo: pd.DataFrame) -> pd.DataFrame:
    """Distribuição (lead 1) de cada variável por ponto: para verificar a escolha dos pontos."""
    d = longo[longo["lead_dias"] == 1]
    return (
        d.groupby(["variavel", "ponto"])["valor"]
        .describe(percentiles=[0.1, 0.5, 0.9])[["mean", "10%", "50%", "90%"]]
        .round(1)
    )
