"""Registo de modelos em ficheiros: versões imutáveis + ponteiro para o campeão.

registo/
  campeoes.json                 {"consumo": "20261104T0300-ab12cd3", ...}
  historico.jsonl               uma linha por decisão (promovido / rejeitado)
  <alvo>/<versao>/modelo.joblib
  <alvo>/<versao>/meta.json     dados de treino, parâmetros, métricas, commit, seed,
                                perfil das features (para o drift)
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import joblib
import lightgbm
import numpy as np
import pandas as pd

from . import config
from .modelos import ModeloLGBM


def _commit() -> str:
    if sha := os.environ.get("GITHUB_SHA"):
        return sha[:7]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido"


def nova_versao(agora: datetime | None = None) -> str:
    agora = agora or datetime.now(UTC)
    return f"{agora:%Y%m%dT%H%M}-{_commit()}"


def perfil_features(exemplos: pd.DataFrame, colunas: list[str], n_bins: int = 10) -> dict:
    """Decis do treino por feature contínua: limites interiores e proporções (para o PSI)."""
    perfil = {}
    for c in colunas:
        v = pd.to_numeric(exemplos[c], errors="coerce").dropna().to_numpy()
        if np.unique(v).size <= n_bins:  # categóricas / calendário: não interessa
            continue
        limites = np.unique(np.quantile(v, np.linspace(0, 1, n_bins + 1))[1:-1])
        contagens = np.bincount(np.searchsorted(limites, v, side="right"), minlength=limites.size + 1)
        perfil[c] = {"limites": limites.tolist(), "proporcoes": (contagens / v.size).tolist()}
    return perfil


def guardar(modelo: ModeloLGBM, treino: pd.DataFrame, metricas: dict, raiz: Path | None = None) -> str:
    raiz = raiz or config.REGISTO
    versao = nova_versao()
    pasta = raiz / modelo.alvo / versao
    pasta.mkdir(parents=True, exist_ok=False)
    joblib.dump(modelo, pasta / "modelo.joblib")
    meta = {
        "alvo": modelo.alvo,
        "versao": versao,
        "criado_em": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": _commit(),
        "seed": config.SEED,
        "parametros": modelo.parametros,
        "colunas": modelo.colunas,
        "treino": {
            "dia_inicio": str(treino["dia"].min().date()),
            "dia_fim": str(treino["dia"].max().date()),
            "linhas": len(treino),
        },
        "metricas": metricas,
        "perfil_features": perfil_features(treino, modelo.colunas),
        "ambiente": {
            "python": platform.python_version(),
            "lightgbm": lightgbm.__version__,
            "pandas": pd.__version__,
        },
    }
    (pasta / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return versao


def campeoes(raiz: Path | None = None) -> dict[str, str]:
    f = (raiz or config.REGISTO) / "campeoes.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def promover(alvo: str, versao: str, motivo: str, raiz: Path | None = None) -> None:
    raiz = raiz or config.REGISTO
    atuais = campeoes(raiz)
    atuais[alvo] = versao
    (raiz / "campeoes.json").write_text(json.dumps(atuais, indent=2, sort_keys=True), encoding="utf-8")
    registar_decisao(alvo, versao, "promovido", motivo, raiz)


def registar_decisao(alvo: str, versao: str, decisao: str, motivo: str, raiz: Path | None = None) -> None:
    raiz = raiz or config.REGISTO
    raiz.mkdir(parents=True, exist_ok=True)
    linha = {
        "em": datetime.now(UTC).isoformat(timespec="seconds"),
        "alvo": alvo,
        "versao": versao,
        "decisao": decisao,
        "motivo": motivo,
    }
    with (raiz / "historico.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def carregar(alvo: str, versao: str | None = None, raiz: Path | None = None) -> tuple[ModeloLGBM, dict]:
    raiz = raiz or config.REGISTO
    versao = versao or campeoes(raiz).get(alvo)
    if not versao:
        raise FileNotFoundError(f"Sem modelo campeão para '{alvo}'")
    pasta = raiz / alvo / versao
    meta = json.loads((pasta / "meta.json").read_text(encoding="utf-8"))
    return joblib.load(pasta / "modelo.joblib"), meta


def limpar(alvo: str, manter: int = config.VERSOES_A_MANTER, raiz: Path | None = None) -> list[str]:
    """Apaga versões antigas (nunca o campeão). Os metadados ficam no historico.jsonl."""
    raiz = raiz or config.REGISTO
    pasta = raiz / alvo
    if not pasta.exists():
        return []
    campeao = campeoes(raiz).get(alvo)
    versoes = sorted(p.name for p in pasta.iterdir() if p.is_dir())
    apagar = [v for v in versoes[:-manter] if v != campeao]
    for v in apagar:
        shutil.rmtree(pasta / v)
    return apagar
