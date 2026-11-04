"""Linha de comandos: ``eletricidade <comando>``."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import date, timedelta

import pandas as pd

from . import backtest, config, features, meteo, monitor, painel, producao, registo, ren

log = logging.getLogger("eletricidade")


def _hoje_local() -> date:
    return pd.Timestamp.now(tz=config.FUSO).date()


def _resumo_github(texto: str) -> None:
    if destino := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


def _saida_github(**valores) -> None:
    if destino := os.environ.get("GITHUB_OUTPUT"):
        with open(destino, "a", encoding="utf-8") as f:
            for k, v in valores.items():
                f.write(f"{k}={str(v).lower() if isinstance(v, bool) else v}\n")


def cmd_ingest(args) -> int:
    desde = date.fromisoformat(args.desde)
    hoje = _hoje_local()
    _, falhas = ren.atualizar(desde, hoje)
    horario = ren.construir_horario()
    config.FICH_REN_HORARIO.parent.mkdir(parents=True, exist_ok=True)
    horario.to_parquet(config.FICH_REN_HORARIO)
    # Meteorologia até D+1 (necessária para emitir a previsão de hoje).
    meteo.atualizar(desde, hoje + timedelta(days=config.DIAS_HORIZONTE - 1))
    meteo.construir_horario().to_parquet(config.FICH_METEO_HORARIO, index=False)
    graves = {d: e for d, e in falhas.items() if not ren.e_dia_mudanca_hora(d) and d < hoje}
    log.info("REN: %d horas, de %s a %s", len(horario), horario.index.min(), horario.index.max())
    for d, e in falhas.items():
        log.warning("Falha %s: %s", d, e)
    return 1 if graves else 0


def _todos_exemplos():
    grade, grupos = producao.carregar_grade(), producao.carregar_meteo()
    return grade, grupos, {a: features.construir_exemplos(grade, grupos, a) for a in config.ALVOS}


def cmd_backtest(args) -> int:
    _, _, ex = _todos_exemplos()
    previsoes = pd.concat([backtest.correr(ex[a], a, n_semanas=args.semanas) for a in config.ALVOS])
    config.ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    previsoes.to_parquet(config.ARTEFACTOS / "backtest_previsoes.parquet", index=False)
    resumo = backtest.resumir(previsoes)
    por_lead = backtest.resumir(previsoes, por=("lead",))
    resumo.to_csv(config.ARTEFACTOS / "backtest_resumo.csv", index=False)
    por_lead.to_csv(config.ARTEFACTOS / "backtest_por_lead.csv", index=False)
    backtest.erro_semanal(previsoes).to_csv(config.ARTEFACTOS / "backtest_erro_semanal.csv", index=False)
    semanas = previsoes["semana"]
    cabecalho = (
        f"Backtest semana a semana: {semanas.nunique()} semanas de teste, de "
        f"{semanas.min():%Y-%m-%d} a {(semanas.max() + pd.Timedelta(days=6)):%Y-%m-%d}; "
        f"horizontes D e D+1 agregados. MAPE e sMAPE do solar só nas horas com mais de "
        f"{config.LIMIAR_MAPE_SOLAR_MW:.0f} MW."
    )
    tabela = f"{cabecalho}\n\n{backtest.tabela_markdown(resumo)}"
    (config.ARTEFACTOS / "resultados.md").write_text(tabela + "\n", encoding="utf-8")
    print(tabela)
    _resumo_github(tabela)
    if args.atualizar_readme:
        readme = config.RAIZ / "README.md"
        texto = readme.read_text(encoding="utf-8")
        novo = re.sub(
            r"(<!-- RESULTADOS:INICIO -->\n).*?(\n<!-- RESULTADOS:FIM -->)",
            lambda m: m.group(1) + tabela + m.group(2),
            texto,
            flags=re.S,
        )
        readme.write_text(novo, encoding="utf-8")
    return 0


def cmd_treinar(args) -> int:
    _, _, ex = _todos_exemplos()
    alvos = [args.alvo] if args.alvo else list(config.ALVOS)
    resultados = [producao.treinar_e_promover(a, ex[a], semanas_gate=args.semanas) for a in alvos]
    linhas = [
        "| Alvo | Versão | Promovido | MAE backtest | MAE naive sazonal | Motivo |",
        "|---|---|---|---:|---:|---|",
    ]
    for r in resultados:
        linhas.append(
            f"| {r['alvo']} | {r['versao']} | {'sim' if r['promovido'] else 'não'} | "
            f"{r['MAE_backtest']:.0f} | {r['MAE_naive_sazonal_backtest']:.0f} | {r['motivo']} |"
        )
    print("\n".join(linhas))
    _resumo_github("## Treino\n\n" + "\n".join(linhas))
    if not registo.campeoes():
        log.error("Nenhum modelo campeão no registo")
        return 1
    return 0


def cmd_prever(args) -> int:
    origem = pd.Timestamp(args.origem or _hoje_local())
    previsao = producao.prever(origem, producao.carregar_grade(), producao.carregar_meteo())
    destino = producao.guardar_previsao(previsao)
    log.info("Previsão guardada em %s", destino)
    return 0


def cmd_monitorizar(args) -> int:
    grade, grupos = producao.carregar_grade(), producao.carregar_meteo()
    hoje = pd.Timestamp(_hoje_local())
    previsoes = monitor.carregar_previsoes()
    realizadas = monitor.juntar_reais(previsoes, grade) if not previsoes.empty else pd.DataFrame()
    metas, recentes = {}, {}
    for alvo in config.ALVOS:
        try:
            _, metas[alvo] = registo.carregar(alvo)
        except FileNotFoundError:
            continue
        ex = features.construir_exemplos(grade, grupos, alvo, ate=hoje + pd.Timedelta(days=1))
        recentes[alvo] = ex[ex["origem"] > hoje - pd.Timedelta(days=14)]
    if realizadas.empty:
        realizadas = pd.DataFrame(columns=["alvo", "dia", "hora", "lead", "y", *monitor.MODELOS_MONITOR])
    relatorio = monitor.avaliar(realizadas, recentes, metas, hoje)
    hist = monitor.historico_erro(realizadas) if len(realizadas) else pd.DataFrame()
    monitor.guardar(relatorio, hist)
    md = monitor.markdown(relatorio)
    print(md)
    _resumo_github(md)
    _saida_github(alerta=relatorio["alerta"], retreinar=relatorio["retreinar"])
    return 0


def cmd_painel(args) -> int:
    grade = producao.carregar_grade()
    previsoes = monitor.carregar_previsoes()
    hist_f = config.DIR_MONITOR / "historico_erro.csv"
    hist = pd.read_csv(hist_f, parse_dates=["dia"]) if hist_f.exists() else pd.DataFrame()
    rel_f = config.DIR_MONITOR / "relatorio.json"
    rel = json.loads(rel_f.read_text(encoding="utf-8")) if rel_f.exists() else None
    resumo = None
    for f in (config.ESTADO / "backtest_por_lead.csv", config.ARTEFACTOS / "backtest_por_lead.csv"):
        if f.exists():
            resumo = pd.read_csv(f)
            break
    destino = painel.escrever(painel.dados_painel(grade, previsoes, hist, rel, resumo))
    log.info("Painel escrito em %s", destino)
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    p = argparse.ArgumentParser(prog="eletricidade", description=__doc__)
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("ingest", help="download incremental REN + Open-Meteo")
    s.add_argument("--desde", default=config.INICIO_HISTORICO)
    s.set_defaults(func=cmd_ingest)

    s = sub.add_parser("backtest", help="backtest semana a semana contra as referências")
    s.add_argument("--semanas", type=int, default=26)
    s.add_argument("--atualizar-readme", action="store_true")
    s.set_defaults(func=cmd_backtest)

    s = sub.add_parser("treinar", help="treina candidatos e promove-os se passarem a regra")
    s.add_argument("--alvo", choices=config.ALVOS)
    s.add_argument("--semanas", type=int, default=4)
    s.set_defaults(func=cmd_treinar)

    s = sub.add_parser("prever", help="emite a previsão de 48 h")
    s.add_argument("--origem", help="AAAA-MM-DD (por omissão, hoje em Lisboa)")
    s.set_defaults(func=cmd_prever)

    sub.add_parser("monitorizar", help="erro realizado, drift e alertas").set_defaults(func=cmd_monitorizar)
    sub.add_parser("painel", help="gera o painel estático").set_defaults(func=cmd_painel)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
