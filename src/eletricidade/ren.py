"""Cliente do REN Data Hub: download do diagrama de produção/consumo (15 min).

Endpoint confirmado (ver docs/PLANO.md):
    GET {REN_PRODUCAO_DIARIA}?date=AAAA-MM-DD&culture=pt-PT
Resposta tipo Highcharts: ``xAxis.categories`` (rótulos de 15 min em hora
local) e ``series: [{name, data}]`` com valores em MW.
"""

from __future__ import annotations

import json
import logging
import time
import unicodedata
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)


class ErroREN(RuntimeError):
    """Resposta da REN inesperada ou incoerente: falhar em vez de adivinhar."""


def normalizar(texto: str) -> str:
    sem_acentos = unicodedata.normalize("NFD", str(texto))
    sem_acentos = "".join(c for c in sem_acentos if unicodedata.category(c) != "Mn")
    return " ".join(sem_acentos.lower().split())


def descarregar_dia(dia: date, sessao: requests.Session | None = None, tentativas: int = 4) -> dict:
    """Descarrega o JSON bruto de um dia, com *retry* e *backoff* exponencial."""
    sessao = sessao or requests.Session()
    # A ordem date -> culture é intencional (um cliente público refere que o gateway é sensível).
    params = {"date": dia.isoformat(), "culture": config.REN_CULTURE}
    espera = 2.0
    ultimo_erro: Exception | None = None
    for tentativa in range(1, tentativas + 1):
        try:
            resp = sessao.get(
                config.REN_PRODUCAO_DIARIA,
                params=params,
                timeout=(15, 45),
                # Sem "Accept: application/json": com esse cabeçalho o gateway da REN não
                # responde (timeout); sem ele responde em < 1 s. Ver workflow diagnostico-rede.
                headers={"User-Agent": config.USER_AGENT},
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as erro:
            ultimo_erro = erro
            log.warning("REN %s: tentativa %d falhou (%s)", dia, tentativa, erro)
            if tentativa < tentativas:
                time.sleep(espera)
                espera *= 2
    raise ErroREN(f"REN {dia}: falhou após {tentativas} tentativas: {ultimo_erro}")


def _categorias(payload: dict) -> list[str]:
    eixo = payload.get("xAxis")
    if isinstance(eixo, list):  # alguns clientes observam xAxis como lista
        eixo = eixo[0] if eixo else None
    if not isinstance(eixo, dict) or not isinstance(eixo.get("categories"), list):
        raise ErroREN("Resposta sem xAxis.categories")
    return [str(c) for c in eixo["categories"]]


def intervalos_utc(dia: date) -> pd.DatetimeIndex:
    """Inícios (UTC) dos intervalos de 15 min do dia civil em Lisboa.

    96 num dia normal, 92 no dia em que a hora avança e 100 quando recua.
    """
    inicio = pd.Timestamp(dia).tz_localize(config.FUSO)
    fim = pd.Timestamp(dia + timedelta(days=1)).tz_localize(config.FUSO)
    return pd.date_range(inicio.tz_convert("UTC"), fim.tz_convert("UTC"), freq="15min", inclusive="left")


def identificar_series(nomes: list[str]) -> dict[str, str]:
    """Associa cada alvo ao nome exato da série. Falha se faltar ou for ambíguo."""
    resultado: dict[str, str] = {}
    for alvo, nome_esperado in config.SERIES_REN.items():
        candidatos = [n for n in nomes if normalizar(n) == nome_esperado]
        if len(candidatos) != 1:
            raise ErroREN(f"Série '{alvo}': esperava 1 candidata, encontrei {candidatos} em {nomes}")
        resultado[alvo] = candidatos[0]
    return resultado


def interpretar_dia(payload: dict[str, Any], dia: date) -> pd.DataFrame:
    """Converte o JSON de um dia numa tabela larga a 15 min indexada em UTC.

    Colunas: os alvos (consumo, eolica, solar). Valores em falta (dia corrente
    ainda incompleto) ficam como NaN.
    """
    categorias = _categorias(payload)
    series = [s for s in payload.get("series", []) if isinstance(s, dict) and "name" in s]
    if not series:
        raise ErroREN(f"REN {dia}: resposta sem séries")

    esperados = intervalos_utc(dia)
    if len(categorias) != len(esperados):
        raise ErroREN(
            f"REN {dia}: {len(categorias)} intervalos, esperava {len(esperados)} (mudança de hora?)"
        )

    nomes = identificar_series([str(s["name"]) for s in series])
    por_nome = {str(s["name"]): s for s in series}
    colunas = {}
    for alvo, nome in nomes.items():
        dados = por_nome[nome].get("data")
        if not isinstance(dados, list) or len(dados) != len(categorias):
            raise ErroREN(f"REN {dia}: série '{nome}' com comprimento diferente das categorias")
        valores = [
            (v.get("y") if isinstance(v, dict) else v) for v in dados
        ]  # Highcharts aceita números ou {y: ...}
        colunas[alvo] = pd.to_numeric(pd.Series(valores, dtype="object"), errors="coerce").to_numpy()

    tabela = pd.DataFrame(colunas, index=esperados)
    tabela.index.name = "ts_utc"
    return tabela


def para_horario(quarto_horario: pd.DataFrame) -> pd.DataFrame:
    """Média horária (MW médios = MWh na hora). Só fecha horas com os 4 quartos."""
    contagem = quarto_horario.resample("1h").count()
    media = quarto_horario.resample("1h").mean()
    return media.where(contagem == 4)


# --- armazenamento incremental -------------------------------------------------


def caminho_bruto(dia: date, raiz: Path | None = None) -> Path:
    raiz = raiz or config.DIR_REN_BRUTO
    return raiz / f"{dia.year}" / f"{dia.isoformat()}.json"


def dias_a_descarregar(inicio: date, fim: date, raiz: Path | None = None, rever: int = 2) -> list[date]:
    """Dias sem ficheiro bruto, mais os últimos ``rever`` dias (podem estar incompletos)."""
    dias = [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]
    limite_revisao = fim - timedelta(days=rever - 1)
    return [d for d in dias if d >= limite_revisao or not caminho_bruto(d, raiz).exists()]


def e_dia_mudanca_hora(dia: date) -> bool:
    return len(intervalos_utc(dia)) != 96


class FonteIndisponivel(ErroREN):
    """A API falhou em vários dias seguidos: é a fonte, não um dia em particular."""


def atualizar(
    inicio: date,
    fim: date,
    raiz: Path | None = None,
    pausa: float = 0.5,
    max_falhas_seguidas: int = 3,
    descarregar=None,
) -> tuple[list[date], dict[date, str]]:
    """Download incremental dos JSON brutos.

    Devolve (dias gravados, falhas). Um dia só é gravado se for interpretável;
    falhas isoladas ficam registadas sem parar o resto da ingestão. Se falharem
    ``max_falhas_seguidas`` dias seguidos, a fonte está indisponível e a ingestão
    pára logo (``FonteIndisponivel``) em vez de esgotar o tempo do workflow.
    """
    descarregar = descarregar or descarregar_dia
    sessao = requests.Session()
    feitos: list[date] = []
    falhas: dict[date, str] = {}
    seguidas = 0
    for dia in dias_a_descarregar(inicio, fim, raiz):
        try:
            payload = descarregar(dia, sessao)
            interpretar_dia(payload, dia)  # valida antes de gravar
        except ErroREN as erro:
            falhas[dia] = str(erro)
            log.error("%s", erro)
            seguidas += 1
            if seguidas >= max_falhas_seguidas:
                raise FonteIndisponivel(
                    f"REN: {seguidas} dias seguidos falharam (último: {erro}); "
                    f"{len(feitos)} dias gravados antes de parar"
                ) from erro
            continue
        seguidas = 0
        destino = caminho_bruto(dia, raiz)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        feitos.append(dia)
        time.sleep(pausa)
    log.info("REN: %d dias gravados, %d falhas", len(feitos), len(falhas))
    return feitos, falhas


def construir_horario(raiz: Path | None = None) -> pd.DataFrame:
    """Reconstrói a tabela horária a partir de todos os JSON brutos."""
    raiz = raiz or config.DIR_REN_BRUTO
    partes = []
    for ficheiro in sorted(raiz.glob("*/*.json")):
        dia = date.fromisoformat(ficheiro.stem)
        partes.append(interpretar_dia(json.loads(ficheiro.read_text(encoding="utf-8")), dia))
    if not partes:
        raise ErroREN(f"Sem dados brutos em {raiz}")
    quartos = pd.concat(partes).sort_index()
    quartos = quartos[~quartos.index.duplicated(keep="last")]
    return para_horario(quartos)
