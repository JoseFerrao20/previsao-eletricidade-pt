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
LIMIAR_PSI = 0.25  # PSI > 0,25 = mudança de distribuição relevante
# Promoção: o candidato pode ser no máximo 2 % pior do que o campeão (ruído).
TOLERANCIA_PROMOCAO = 1.02
VERSOES_A_MANTER = 8

REN_BASE = "https://servicebus.ren.pt/datahubapi/electricity"
REN_PRODUCAO_DIARIA = f"{REN_BASE}/ElectricityProductionBreakdownDaily"
REN_CULTURE = "pt-PT"

OPEN_METEO_PREVIOUS_RUNS = "https://previous-runs-api.open-meteo.com/v1/forecast"

# Início do histórico. A API de corridas anteriores do Open-Meteo só tem
# previsões arquivadas a partir de 2024 para a maioria dos modelos.
INICIO_HISTORICO = "2024-01-01"

ALVOS = ("consumo", "eolica", "solar")

# Padrões (normalizados: minúsculas, sem acentos) que identificam cada série
# alvo no JSON da REN. "Consumo" tem de ser distinto de "consumo + bombagem".
PADROES_SERIES = {
    "consumo": {"incluir": ("consumo", "consumption"), "excluir": ("bombagem", "armazen", "storage", "pump")},
    "eolica": {"incluir": ("eolica", "wind"), "excluir": ()},
    "solar": {"incluir": ("solar", "fotovolt"), "excluir": ()},
}


@dataclass(frozen=True)
class Ponto:
    nome: str
    lat: float
    lon: float
    grupo: str  # "populacao", "vento" ou "sol"


# Pontos representativos (não ponderados pela potência instalada; ver README).
PONTOS = (
    Ponto("lisboa", 38.72, -9.14, "populacao"),
    Ponto("porto", 41.15, -8.61, "populacao"),
    Ponto("coimbra", 40.21, -8.43, "populacao"),
    Ponto("caramulo", 40.57, -8.17, "vento"),
    Ponto("vila_real", 41.30, -7.75, "vento"),
    Ponto("castelo_branco", 39.82, -7.49, "vento"),
    Ponto("evora", 38.57, -7.91, "sol"),
    Ponto("beja", 38.02, -7.86, "sol"),
    Ponto("alcoutim", 37.47, -7.47, "sol"),
)

VARIAVEIS_METEO = ("temperature_2m", "wind_speed_100m", "shortwave_radiation", "cloud_cover")

# Que variáveis (e de que grupo de pontos) alimentam cada alvo.
METEO_POR_ALVO = {
    "consumo": (
        ("populacao", "temperature_2m"),
        ("populacao", "cloud_cover"),
        ("populacao", "shortwave_radiation"),
    ),
    "eolica": (("vento", "wind_speed_100m"),),
    "solar": (("sol", "shortwave_radiation"), ("sol", "cloud_cover"), ("sol", "temperature_2m")),
}

# Horizonte: a previsão emitida à meia-noite local de D cobre D (lead 1) e D+1 (lead 2).
DIAS_HORIZONTE = 2

# No solar, o MAPE só é calculado nas horas com produção acima deste valor (MW).
LIMIAR_MAPE_SOLAR_MW = 100.0
