"""Previsões de vários modelos meteorológicos (ECMWF, GFS, ICON) além do de omissão.

Cada modelo só é pedido para a variável que interessa a cada grupo de pontos
(vento a 100 m nos pontos de vento, radiação nos de sol, temperatura nos de
população), para não multiplicar a carga sobre a API. A regra de escolha da
corrida por hora é a mesma do resto da meteorologia (``meteo.offset_para``).

Resultado na tabela longa: variável ``<variavel>__<modelo>``; depois da
agregação por grupo dá colunas ``<grupo>__<variavel>__<modelo>`` e
``<grupo>__<variavel>__dispersao`` (desvio-padrão entre os modelos e o de
omissão: quanto maior, mais incerta a meteorologia).

Formato da resposta confirmado num runner (workflow diagnostico-rede):
``<variavel>_previous_dayN_<modelo>``. Arquivo destes modelos: completo a partir
de março de 2024 (Météo-France fica de fora: não tem previous_day2).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, meteo


def pontos_do_grupo(grupo: str):
    return [p for p in config.PONTOS if grupo in p.grupos]


def assinatura() -> str:
    texto = json.dumps(
        [
            [(p.nome, p.lat, p.lon, p.grupos) for p in config.PONTOS],
            config.MODELOS_METEO_EXTRA,
            config.VARIAVEL_EXTRA_POR_GRUPO,
            meteo.OFFSETS_PEDIDOS,
        ],
        sort_keys=True,
    )
    return hashlib.sha1(texto.encode()).hexdigest()[:10]


def pasta_bruta() -> Path:
    return config.DADOS / "brutos" / "meteo_modelos" / assinatura()


def _variaveis(grupo: str) -> list[str]:
    v = config.VARIAVEL_EXTRA_POR_GRUPO[grupo]
    return [f"{v}_previous_day{n}" for n in meteo.OFFSETS_PEDIDOS]


def descarregar(inicio: date, fim: date, grupo: str) -> list[dict]:
    return meteo.descarregar(
        inicio,
        fim,
        pontos=pontos_do_grupo(grupo),
        variaveis=_variaveis(grupo),
        modelos=config.MODELOS_METEO_EXTRA,
    )


def interpretar(locais: list[dict], grupo: str) -> pd.DataFrame:
    """Tabela longa: ts_utc, ponto, variavel (``<var>__<modelo>``), lead_dias, valor."""
    pontos = pontos_do_grupo(grupo)
    if len(locais) != len(pontos):
        raise meteo.ErroMeteo(f"{grupo}: esperava {len(pontos)} pontos, recebi {len(locais)}")
    var = config.VARIAVEL_EXTRA_POR_GRUPO[grupo]
    partes = []
    for ponto, local in zip(pontos, locais, strict=True):
        horario = local.get("hourly")
        if not isinstance(horario, dict) or "time" not in horario:
            raise meteo.ErroMeteo(f"{grupo}/{ponto.nome}: resposta sem 'hourly.time'")
        ts = pd.DatetimeIndex(pd.to_datetime(horario["time"], utc=True))
        for modelo in config.MODELOS_METEO_EXTRA:
            por_offset = {}
            for n in meteo.OFFSETS_PEDIDOS:
                chave = f"{var}_previous_day{n}_{modelo}"
                if chave not in horario:
                    raise meteo.ErroMeteo(f"{grupo}/{ponto.nome}: falta {chave}")
                por_offset[n] = pd.to_numeric(pd.Series(horario[chave]), errors="coerce").to_numpy()
            for lead in meteo.LEAD_METEO:
                n = meteo.offset_para(ts, lead).to_numpy()
                valor = np.select(
                    [n == k for k in meteo.OFFSETS_PEDIDOS], [por_offset[k] for k in meteo.OFFSETS_PEDIDOS]
                )
                partes.append(
                    pd.DataFrame(
                        {
                            "ts_utc": ts,
                            "ponto": ponto.nome,
                            "variavel": f"{var}__{modelo}",
                            "lead_dias": lead,
                            "valor": valor,
                        }
                    )
                )
    return pd.concat(partes, ignore_index=True)


def atualizar(inicio: date, fim: date, raiz: Path | None = None) -> list[str]:
    raiz = raiz or pasta_bruta()
    feitos, erros = [], []
    for grupo in config.VARIAVEL_EXTRA_POR_GRUPO:
        try:
            feitos += meteo.atualizar_meses(
                inicio,
                fim,
                lambda mes, g=grupo: raiz / g / f"{mes}.json",
                lambda a, b, g=grupo: descarregar(a, b, g),
                lambda locais, g=grupo: interpretar(locais, g),
            )
        except meteo.ErroMeteo as erro:  # continua nos outros grupos; falha no fim
            erros.append(f"{grupo}: {erro}")
    if erros:
        raise meteo.ErroMeteo("; ".join(erros))
    return feitos


def construir_horario(raiz: Path | None = None) -> pd.DataFrame | None:
    raiz = raiz or pasta_bruta()
    partes = [
        interpretar(json.loads(f.read_text(encoding="utf-8")), grupo)
        for grupo in config.VARIAVEL_EXTRA_POR_GRUPO
        for f in sorted((raiz / grupo).glob("*.json"))
    ]
    if not partes:
        return None
    longo = pd.concat(partes, ignore_index=True)
    return longo.drop_duplicates(["ts_utc", "ponto", "variavel", "lead_dias"], keep="last")


def com_dispersao(largo: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta ``<grupo>__<var>__dispersao``: desvio-padrão entre o modelo de omissão e os extra."""
    largo = largo.copy()
    for grupo, var in config.VARIAVEL_EXTRA_POR_GRUPO.items():
        cols = [f"{grupo}__{var}"] + [f"{grupo}__{var}__{m}" for m in config.MODELOS_METEO_EXTRA]
        if all(c in largo for c in cols):
            largo[f"{grupo}__{var}__dispersao"] = largo[cols].std(axis=1, ddof=0)
    return largo


def colunas_para(alvo: str) -> list[str]:
    grupo = config.GRUPO_EXTRA_POR_ALVO.get(alvo)
    if not grupo or not config.MODELOS_METEO_EXTRA:
        return []
    var = config.VARIAVEL_EXTRA_POR_GRUPO[grupo]
    return [f"{grupo}__{var}__{m}" for m in config.MODELOS_METEO_EXTRA] + [f"{grupo}__{var}__dispersao"]
