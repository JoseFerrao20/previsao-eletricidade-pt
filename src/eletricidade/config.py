"""Configuração central: caminhos, alvos, pontos meteorológicos e constantes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

FUSO = "Europe/Lisbon"
SEED = 42

RAIZ = Path(os.environ.get("ELETRICIDADE_RAIZ", Path.cwd()))
DADOS = RAIZ / "dados"
DIR_REN_BRUTO = DADOS / "ren" / "bruto"
DIR_METEO_BRUTO = DADOS / "meteo" / "bruto"
FICH_REN_HORARIO = DADOS / "ren_horario.parquet"
FICH_METEO_HORARIO = DADOS / "meteo_horario.parquet"
ARTEFACTOS = RAIZ / "artefactos"  # saídas do backtest (CSV, tabela markdown)
SITE = RAIZ / "site"  # painel estático

# Estado de produção, versionado no branch "estado" (montado em ./estado no CI).
ESTADO = Path(os.environ.get("ELETRICIDADE_ESTADO", RAIZ / "estado"))
REGISTO = ESTADO / "registo"
DIR_PREVISOES = ESTADO / "previsoes"
DIR_MONITOR = ESTADO / "monitor"

# Monitor: limiares de alerta.
JANELA_MONITOR_DIAS = 7
LIMIAR_DEGRADACAO = 1.30  # MAE realizado / MAE de referência do backtest
LIMIAR_PSI = 0.25  # PSI > 0,25 = mudança relevante (aviso de drift, face à mesma época do ano)
# Promoção: o candidato pode ser no máximo 2 % pior do que o campeão (ruído).
TOLERANCIA_PROMOCAO = 1.02
VERSOES_A_MANTER = 8

REN_BASE = "https://servicebus.ren.pt/datahubapi/electricity"
REN_PRODUCAO_DIARIA = f"{REN_BASE}/ElectricityProductionBreakdownDaily"
REN_CULTURE = "pt-PT"  # a API aceita só pt-PT e en-US
USER_AGENT = "previsao-eletricidade-pt (+https://github.com/JoseFerrao20/previsao-eletricidade-pt)"

OPEN_METEO_PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"

# Início do histórico. A API de corridas anteriores do Open-Meteo só tem
# previsões arquivadas a partir de 2024 para a maioria dos modelos.
INICIO_HISTORICO = "2024-01-01"

ALVOS = ("consumo", "eolica", "solar")

# Padrões (normalizados: minúsculas, sem acentos) que identificam cada série
# alvo no JSON da REN. "Consumo" tem de ser distinto de "consumo + bombagem".
# Nomes das séries em culture=pt-PT, observados na API (2026-11): "Consumo",
# "Consumo + Armazenamento" (= Consumo + Bombagem + Consumo Baterias), "Bombagem",
# "Consumo Baterias", "Injeção de Baterias", "Eólica", "Solar", "Hídrica", ...
# Comparação exata após normalização (sem acentos, minúsculas): "Consumo" é o
# consumo líquido, sem bombagem nem carga de baterias.
SERIES_REN = {"consumo": "consumo", "eolica": "eolica", "solar": "solar"}


@dataclass(frozen=True)
class Ponto:
    nome: str
    lat: float
    lon: float
    grupos: tuple[str, ...]  # "populacao", "vento" e/ou "sol"


# Pontos meteorológicos. Os de vento ficam nas serras onde se concentram os parques
# eólicos; os de sol nas zonas das grandes centrais fotovoltaicas, mais Lisboa e
# Porto pela produção descentralizada (telhados). A escolha é geográfica; o peso de
# cada ponto não é imposto: o LightGBM recebe as séries por ponto e aprende-o com
# os dados de treino de cada dobra do backtest.
POP, VENTO, SOL = "populacao", "vento", "sol"
PONTOS = (
    Ponto("lisboa", 38.72, -9.14, (POP, SOL)),
    Ponto("porto", 41.15, -8.61, (POP, SOL)),
    Ponto("coimbra", 40.21, -8.43, (POP,)),
    # vento
    Ponto("caramulo", 40.57, -8.17, (VENTO,)),
    Ponto("freita", 40.87, -8.27, (VENTO,)),
    Ponto("montemuro", 41.00, -7.98, (VENTO,)),
    Ponto("alvao", 41.38, -7.80, (VENTO,)),
    Ponto("barroso", 41.80, -7.85, (VENTO,)),
    Ponto("arga", 41.80, -8.68, (VENTO,)),
    Ponto("guarda", 40.50, -7.25, (VENTO,)),
    Ponto("gardunha", 40.10, -7.50, (VENTO,)),
    Ponto("lousa", 40.08, -8.20, (VENTO,)),
    Ponto("candeeiros", 39.45, -8.90, (VENTO,)),
    Ponto("oeste", 39.20, -9.30, (VENTO,)),
    Ponto("monchique", 37.30, -8.58, (VENTO,)),
    # sol
    Ponto("evora", 38.57, -7.91, (SOL,)),
    Ponto("beja", 38.02, -7.86, (SOL,)),
    Ponto("alcoutim", 37.47, -7.47, (SOL,)),
    Ponto("ourique", 37.65, -8.22, (SOL,)),
    Ponto("amareleja", 38.20, -7.23, (SOL,)),
    Ponto("alcacer", 38.37, -8.51, (SOL,)),
    Ponto("ribatejo", 39.25, -8.55, (SOL,)),
    Ponto("abrantes", 39.45, -8.12, (SOL,)),
    Ponto("castelo_branco", 39.82, -7.49, (SOL,)),
)

# Variáveis por ponto que entram como features (além das médias de grupo).
# Consumo: só médias (a população dilui o efeito de cada ponto).
METEO_POR_PONTO = {
    "eolica": (VENTO, ("wind_speed_100m",)),
    "solar": (SOL, ("shortwave_radiation", "cloud_cover")),
}
PREFIXO_PONTO = "ponto_"
# Proxy de potência eólica: média por ponto de min(v, V_NOMINAL)^3 (m/s).
V_NOMINAL_EOLICA = 13.0

VARIAVEIS_METEO = ("temperature_2m", "wind_speed_100m", "shortwave_radiation", "cloud_cover")

# Que variáveis (e de que grupo de pontos) alimentam cada alvo.
METEO_POR_ALVO = {
    "consumo": (
        ("populacao", "temperature_2m"),
        ("populacao", "cloud_cover"),
        ("populacao", "shortwave_radiation"),
    ),
    "eolica": (("vento", "wind_speed_100m"), ("vento", "potencia_proxy")),
    "solar": (("sol", "shortwave_radiation"), ("sol", "cloud_cover"), ("sol", "temperature_2m")),
}

# Que corrida meteorológica usar para cada hora (ver meteo.py): "fresca" ou "conservadora".
REGRA_METEO = os.environ.get("ELETRICIDADE_REGRA_METEO", "fresca")
# Margem (h) entre o início de uma corrida e a sua publicação no Open-Meteo. Os modelos
# globais publicam 3–6 h depois do início; 8 h deixa folga para o processamento.
ATRASO_PUBLICACAO_METEO_H = 8

# Alvos previstos como fração de um proxy da potência instalada (máximo dos últimos
# JANELA_CAPACIDADE_DIAS dias): a potência cresce e o passado subestimaria o futuro.
_normalizados = os.environ.get("ELETRICIDADE_ALVOS_NORMALIZADOS", "eolica,solar")
ALVOS_NORMALIZADOS = tuple(a for a in _normalizados.split(",") if a)
JANELA_CAPACIDADE_DIAS = 90

# Horizonte: a previsão emitida à meia-noite local de D cobre D (lead 1) e D+1 (lead 2).
DIAS_HORIZONTE = 2

# No solar, o MAPE só é calculado nas horas com produção acima deste valor (MW).
LIMIAR_MAPE_SOLAR_MW = 100.0
