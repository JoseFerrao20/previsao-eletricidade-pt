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

from . import (
    afinar,
    analise,
    backtest,
    config,
    features,
    intervalos,
    meteo,
    monitor,
    painel,
    producao,
    registo,
    ren,
)

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
    try:
        _, falhas = ren.atualizar(desde, hoje)
    except ren.FonteIndisponivel as erro:
        log.error("%s", erro)
        _resumo_github(f"## Ingestão interrompida\n\n{erro}\n")
        return 2
    horario = ren.construir_horario()
    config.FICH_REN_HORARIO.parent.mkdir(parents=True, exist_ok=True)
    horario.to_parquet(config.FICH_REN_HORARIO)
    # Meteorologia até D+1 (necessária para emitir a previsão de hoje).
    meteo.atualizar(desde, hoje + timedelta(days=config.DIAS_HORIZONTE - 1))
    longo = meteo.construir_horario()
    longo.to_parquet(config.FICH_METEO_HORARIO, index=False)
    resumo = meteo.resumo_por_ponto(longo)
    texto_meteo = (
        "## Meteorologia prevista por ponto (D, todo o histórico)\n\n"
        "Média e percentis 10/50/90. Vento a 100 m em m/s, radiação em W/m², nebulosidade em %.\n\n"
        + _markdown_simples(resumo.reset_index())
        + "\n"
    )
    config.ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    (config.ARTEFACTOS / "meteo_por_ponto.md").write_text(texto_meteo, encoding="utf-8")
    _resumo_github(texto_meteo)
    # Graves: buracos no histórico. O dia anterior (D-1) pode ainda não estar publicado:
    # isso não pára o workflow; é o `prever` que decide se emite ou adia.
    ontem = hoje - timedelta(days=1)
    graves = {d: e for d, e in falhas.items() if not ren.e_dia_mudanca_hora(d) and d < ontem}
    log.info("REN: %d horas, de %s a %s", len(horario), horario.index.min(), horario.index.max())
    for d, e in falhas.items():
        log.warning("Falha %s: %s", d, e)
    return 1 if graves else 0


def _todos_exemplos():
    grade, grupos = producao.carregar_grade(), producao.carregar_meteo()
    return grade, grupos, {a: features.construir_exemplos(grade, grupos, a) for a in config.ALVOS}


def cmd_backtest(args) -> int:
    _, _, ex = _todos_exemplos()
    previsoes = pd.concat(
        [
            backtest.correr(ex[a], a, n_semanas=args.semanas, ultima_semana=args.ultima_semana)
            for a in config.ALVOS
        ]
    )
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
    estatico = intervalos.calibrar_backtest(previsoes, adaptativo=False)
    previsoes = intervalos.calibrar_backtest(previsoes)  # adaptativo (ACI): o usado em produção
    previsoes["lightgbm_p10e"] = estatico["lightgbm_p10c"].to_numpy()
    previsoes["lightgbm_p90e"] = estatico["lightgbm_p90c"].to_numpy()
    previsoes.to_parquet(config.ARTEFACTOS / "backtest_previsoes.parquet", index=False)
    intervalos.ajustes_producao(previsoes).to_csv(
        config.ARTEFACTOS / "backtest_calibracao_intervalos.csv", index=False
    )
    resumo_int = backtest.resumir_intervalos(previsoes)
    resumo_int.to_csv(config.ARTEFACTOS / "backtest_intervalos.csv", index=False)
    texto_intervalos = (
        f"Intervalo de previsão a 80 % (quantis 10 % e 90 %) nas mesmas {semanas.nunique()} semanas, "
        f"menos as {intervalos.MIN_SEMANAS} primeiras (precisam de erros passados para calibrar). "
        "Um intervalo bem calibrado contém o valor real em ~80 % das horas, com ~10 % de cada lado; "
        "entre intervalos calibrados, o mais estreito é melhor (menor pinball). *Estática*: "
        f"cada limite deslocado pelo quantil 90 % dos erros das {intervalos.JANELA_SEMANAS} semanas "
        "anteriores, por alvo, horizonte e hora (calibração conformal). *Adaptativa* (a usada em "
        "produção): o nível desse quantil é corrigido semana a semana pela taxa de falhas de cada "
        f"lado na semana anterior (ACI, passo {intervalos.GAMA}).\n\n"
        + backtest.tabela_intervalos_markdown(resumo_int)
    )
    (config.ARTEFACTOS / "intervalos.md").write_text(texto_intervalos + "\n", encoding="utf-8")
    _resumo_github("## Intervalos de previsão\n\n" + texto_intervalos)
    segmentos = analise.tabela_completa(previsoes, ex)
    segmentos.to_csv(config.ARTEFACTOS / "backtest_segmentos.csv", index=False)
    texto_analise = (
        f"MAE (MW) por segmento nas mesmas {semanas.nunique()} semanas, horizontes D e D+1 agregados. "
        "*Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida "
        "depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a "
        "prevista na emissão, por isso os segmentos são conhecidos de antemão.\n\n"
        + analise.markdown(segmentos)
    )
    (config.ARTEFACTOS / "analise.md").write_text(texto_analise + "\n", encoding="utf-8")
    _resumo_github("## Análise por segmento\n\n" + texto_analise)
    if args.atualizar_readme:
        readme = config.RAIZ / "README.md"
        texto = readme.read_text(encoding="utf-8")
        texto = _substituir_bloco(texto, "RESULTADOS", tabela)
        texto = _substituir_bloco(texto, "ANALISE", texto_analise)
        texto = _substituir_bloco(texto, "INTERVALOS", texto_intervalos)
        readme.write_text(texto, encoding="utf-8")
    return 0


def _markdown_simples(tabela: pd.DataFrame) -> str:
    cab = "| " + " | ".join(map(str, tabela.columns)) + " |"
    sep = "|" + "---|" * len(tabela.columns)
    linhas = ["| " + " | ".join(map(str, r)) + " |" for r in tabela.itertuples(index=False)]
    return "\n".join([cab, sep, *linhas])


def _substituir_bloco(texto: str, nome: str, conteudo: str) -> str:
    padrao = rf"(<!-- {nome}:INICIO -->\n).*?(\n<!-- {nome}:FIM -->)"
    if not re.search(padrao, texto, flags=re.S):
        raise ValueError(f"README sem os marcadores {nome}:INICIO/FIM")
    return re.sub(padrao, lambda m: m.group(1) + conteudo + m.group(2), texto, flags=re.S)


def cmd_afinar(args) -> int:
    _, _, ex = _todos_exemplos()
    alvos = [args.alvo] if args.alvo else list(config.ALVOS)
    escolhidos, partes, linhas_md = {}, [], []
    for alvo in alvos:
        t = afinar.procurar(ex[alvo], alvo, pd.Timestamp(args.ate), args.semanas, args.candidatas)
        partes.append(t)
        base = float(t.loc[t["candidata"] == 0, "MAE_validacao"].iloc[0])
        melhor = t.iloc[0]
        escolhidos[alvo] = melhor["ajuste"]
        linhas_md.append(
            f"| {alvo} | {base:.0f} | {melhor['MAE_validacao']:.0f} "
            f"| {100 * (melhor['MAE_validacao'] / base - 1):+.1f}% | `{json.dumps(melhor['ajuste'])}` |"
        )
    config.ARTEFACTOS.mkdir(parents=True, exist_ok=True)
    tabela = pd.concat(partes, ignore_index=True)
    tabela.assign(ajuste=tabela["ajuste"].map(json.dumps)).to_csv(
        config.ARTEFACTOS / "afinacao.csv", index=False
    )
    texto = (
        f"Semanas de validação (todas antes de {args.ate}): {', '.join(partes[0].attrs['semanas'])}.\n\n"
        "| Alvo | MAE atual | MAE da melhor | Variação | Ajuste |\n|---|---:|---:|---:|---|\n"
        + "\n".join(linhas_md)
    )
    (config.ARTEFACTOS / "afinacao.md").write_text(texto + "\n", encoding="utf-8")
    (config.ARTEFACTOS / "hiperparametros_escolhidos.json").write_text(
        json.dumps(escolhidos, indent=2) + "\n", encoding="utf-8"
    )
    print(texto)
    _resumo_github("## Afinação de hiperparâmetros\n\n" + texto)
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
    existente = producao.caminho_previsao(origem)
    if existente.exists() and not args.forcar:
        # A primeira emissão é a que conta: uma reemissão mais tarde poderia usar um
        # modelo retreinado com valores do próprio dia D (fuga na avaliação realizada).
        log.info("Já existe a previsão de %s (%s); nada a fazer", origem.date(), existente)
        _resumo_github(f"Previsão de {origem.date()} já emitida; mantida a primeira emissão.\n")
        return 0
    grade = producao.carregar_grade()
    ontem = origem - pd.Timedelta(days=1)
    if not producao.dia_completo(grade, ontem):
        if not args.aceitar_incompleto:
            # Como a primeira emissão fica, emitir agora com lags em falta seria definitivo.
            log.warning("Dados de %s incompletos: previsão adiada para a próxima tentativa", ontem.date())
            _resumo_github(f"Dados de {ontem.date()} incompletos na REN: previsão adiada.\n")
            return 0
        log.warning("Dados de %s incompletos: emitida mesmo assim (última tentativa)", ontem.date())
        _resumo_github(f"⚠️ Dados de {ontem.date()} incompletos: previsão emitida com lags em falta.\n")
    previsao = producao.prever(origem, grade, producao.carregar_meteo())
    destino = producao.guardar_previsao(previsao)
    atraso = producao.atraso_emissao_horas(previsao)
    log.info("Previsão guardada em %s (emitida %.1f h depois da meia-noite de Lisboa)", destino, atraso)
    _resumo_github(f"Previsão de {origem.date()} emitida {atraso:.1f} h depois da meia-noite de Lisboa.\n")
    return 0


def cmd_monitorizar(args) -> int:
    grade, grupos = producao.carregar_grade(), producao.carregar_meteo()
    hoje = pd.Timestamp(_hoje_local())
    previsoes = monitor.carregar_previsoes()
    realizadas = monitor.juntar_reais(previsoes, grade) if not previsoes.empty else pd.DataFrame()
    metas, exemplos = {}, {}
    for alvo in config.ALVOS:
        try:
            _, metas[alvo] = registo.carregar(alvo)
        except FileNotFoundError:
            continue
        exemplos[alvo] = features.construir_exemplos(grade, grupos, alvo, ate=hoje + pd.Timedelta(days=1))
    if realizadas.empty:
        realizadas = pd.DataFrame(columns=["alvo", "dia", "hora", "lead", "y", *monitor.MODELOS_MONITOR])
    relatorio = monitor.avaliar(realizadas, exemplos, metas, hoje)
    relatorio["emissao"] = monitor.atrasos_emissao(previsoes)
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
    s.add_argument("--semanas", type=int, default=52)
    s.add_argument(
        "--ultima-semana", help="segunda-feira AAAA-MM-DD da última semana de teste (fixa a janela)"
    )
    s.add_argument("--atualizar-readme", action="store_true")
    s.set_defaults(func=cmd_backtest)

    s = sub.add_parser("treinar", help="treina candidatos e promove-os se passarem a regra")
    s.add_argument("--alvo", choices=config.ALVOS)
    s.add_argument("--semanas", type=int, default=4)
    s.set_defaults(func=cmd_treinar)

    s = sub.add_parser("prever", help="emite a previsão de 48 h")
    s.add_argument("--origem", help="AAAA-MM-DD (por omissão, hoje em Lisboa)")
    s.add_argument("--forcar", action="store_true", help="substitui uma previsão já emitida para a origem")
    s.add_argument(
        "--aceitar-incompleto",
        action="store_true",
        help="emite mesmo que o dia anterior esteja incompleto (última tentativa da madrugada)",
    )
    s.set_defaults(func=cmd_prever)

    s = sub.add_parser("afinar", help="procura de hiperparâmetros só com semanas anteriores ao teste")
    s.add_argument("--ate", required=True, help="segunda-feira da primeira semana de teste (exclusiva)")
    s.add_argument("--semanas", type=int, default=8, help="semanas de validação")
    s.add_argument("--candidatas", type=int, default=16)
    s.add_argument("--alvo", choices=config.ALVOS)
    s.set_defaults(func=cmd_afinar)

    sub.add_parser("monitorizar", help="erro realizado, drift e alertas").set_defaults(func=cmd_monitorizar)
    sub.add_parser("painel", help="gera o painel estático").set_defaults(func=cmd_painel)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
