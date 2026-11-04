# Plano e stack

## Investigação do acesso aos dados (2026-11-04)

Testado a partir do ambiente de desenvolvimento (contentor na nuvem com proxy de
saída):

| Host | Resultado |
|------|-----------|
| `servicebus.ren.pt`, `datahub.ren.pt`, `www.ren.pt` | **bloqueado** pela política de rede do ambiente (403 no proxy) |
| `api.open-meteo.com`, `archive-api.open-meteo.com` | **bloqueado** |
| `date.nager.at`, `transparency.entsoe.eu` | **bloqueado** |
| `github.com`, `api.github.com`, `pypi.org` | acessível |

Consequência: o código de ingestão é escrito e testado aqui com *fixtures*
sintéticas que imitam o formato documentado, e a **primeira execução real**
acontece num runner do GitHub Actions (que tem acesso à Internet) ou num
ambiente com estes domínios autorizados. Nenhum resultado é publicado sem vir
de dados reais.

### O que está confirmado sobre a API da REN

Por leitura de código público de vários projetos independentes (clientes em
Python, TypeScript e MATLAB):

- Base: `https://servicebus.ren.pt/datahubapi/`
- `electricity/ElectricityProductionBreakdownDaily?date=AAAA-MM-DD&culture=pt-PT`
  - JSON tipo Highcharts: `xAxis.categories` (rótulos `HH:MM`, 96 por dia) e
    `series: [{name, data: [...]}]`, valores em MW (média de 15 min).
  - Séries incluem consumo, eólica, solar, hídrica, gás natural, biomassa,
    ondas, importação, exportação e bombagem. Os nomes dependem de `culture`.
  - Em pelo menos um cliente, `xAxis` aparece como lista (`xAxis[0]`); o
    parser aceita as duas formas.
  - Um projeto refere que o gateway é sensível à ordem dos parâmetros
    (`date` antes de `culture`); o cliente envia-os nessa ordem.
- `electricity/ElectricityConsumptionSupplyDaily?date=...` — totais diários
  (`type`, `daily_Accumulation`). Útil para validar a soma dos 15 min.
- Não há documentação formal de limites de pedidos: o cliente faz pedidos
  sequenciais, com pausa e *retry* com *backoff*.

### Decisões que dependem do primeiro download real

1. Nomes exatos das séries em `pt-PT` → o mapeamento usa normalização (sem
   acentos, minúsculas) e falha se uma série-alvo for ambígua ou inexistente.
2. Comportamento nos dias de mudança de hora (92/100 intervalos ou rótulos
   repetidos) → testado e convertido para UTC.
3. Profundidade do histórico disponível → o download começa em 2024-01-01
   (cobertura do arquivo *Previous Runs* do Open-Meteo).

### Meteorologia: porquê a API *Previous Runs*

O arquivo `historical-forecast-api` junta sobretudo as primeiras horas de cada
corrida (previsões a muito curto prazo), o que tornaria o backtest otimista
para horizontes de 24 a 48 h. A API `previous-runs-api.open-meteo.com` expõe
`<variável>_previous_dayN`, a previsão feita N dias antes (uso confirmado em
código público). Regra: D usa `previous_day2` e D+1 usa `previous_day3`.

## Stack proposta

| Camada | Escolha | Porquê |
|--------|---------|--------|
| Linguagem / ambiente | Python 3.13, `uv` + `uv.lock` | Ambiente reprodutível e rápido de instalar no CI. |
| Dados | `requests`, `pandas`, `pyarrow` (Parquet) | Simples; o volume (≈ 35 mil horas) não justifica mais. |
| Feriados | `holidays` (`PT`) | Regras oficiais sem dependência de rede. |
| Modelos | `lightgbm` (um modelo por alvo, horizonte como variável), `scikit-learn` | Forte em dados tabulares, rápido, determinístico. |
| Registo de modelos | Registo próprio em ficheiros (`registry/`, JSON + `joblib`) | Sem servidor; auditável no git. MLflow seria excessivo aqui. |
| Orquestração | GitHub Actions (`schedule` + `workflow_dispatch`) | Treino agendado e retreino disparado pelo monitor. |
| Armazenamento dos dados | *cache* do Actions + reconstrução a partir dos JSON brutos | A REN não publica licença de reutilização, por isso não se versionam dados brutos no git. |
| Alertas | *Issues* do GitHub abertas pelo workflow | Notificação nativa, histórico rastreável. |
| Painel | HTML estático com Plotly, publicado no GitHub Pages | Sem servidor; atualizado diariamente. |
| Qualidade | `pytest`, `ruff` | CI em cada *push*. |

## Fases

1. **Esqueleto** — README, plano, `pyproject`, lock, CI com testes.
2. **Ingestão** — cliente REN (bruto em JSON, normalizado em Parquet horário,
   UTC), Open-Meteo (pontos representativos de consumo, vento e sol), feriados.
   Incremental: só descarrega dias em falta; o dia corrente e o anterior são
   sempre revistos porque podem estar incompletos.
3. **Features e modelos simples** — calendário, lags compatíveis com a hora de
   emissão, meteorologia prevista; naive sazonal, média da semana anterior,
   persistência.
4. **Backtest** — origens diárias agrupadas por semana, treino só com o
   passado, métricas MAE/MAPE/sMAPE por alvo e horizonte, tabela para o README.
5. **Modelo** — LightGBM por alvo; comparação com as referências.
6. **MLOps** — registo, previsão diária, monitor (erro realizado vs. referência,
   PSI), alertas, retreino com regra de promoção campeão/candidato.
7. **Painel** — previsões, valores reais e histórico do erro.
8. **README final** — resultados reais e limitações observadas.

## Pedidos para quem gere o ambiente

Para correr a ingestão neste ambiente de desenvolvimento, autorizar em
*Network access* os domínios:
`servicebus.ren.pt` e `previous-runs-api.open-meteo.com`.
