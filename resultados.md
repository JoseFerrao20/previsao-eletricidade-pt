Backtest semana a semana: 52 semanas de teste, de 2025-11-10 a 2026-11-08; horizontes D e D+1 agregados. MAPE e sMAPE do solar só nas horas com mais de 100 MW.

| Alvo | Modelo | MAE (MW) | MAPE | sMAPE | Skill vs. naive sazonal |
|------|--------|---------:|-----:|------:|------------------------:|
| consumo | **LightGBM** | 184 | 2.9% | 2.9% | +47.8% |
| consumo | Naive sazonal (7 dias) | 353 | 5.6% | 5.6% | +0.0% |
| consumo | Média da semana anterior | 467 | 7.7% | 7.5% | -32.2% |
| consumo | Persistência (D-1) | 555 | 9.0% | 9.0% | -57.2% |
| eolica | **LightGBM** | 262 | 31.3% | 25.3% | +76.5% |
| eolica | Naive sazonal (7 dias) | 1114 | 213.5% | 79.7% | +0.0% |
| eolica | Média da semana anterior | 856 | 193.1% | 64.4% | +23.1% |
| eolica | Persistência (D-1) | 922 | 181.7% | 68.9% | +17.2% |
| solar | **LightGBM** | 112 | 18.7% | 17.7% | +49.0% |
| solar | Naive sazonal (7 dias) | 220 | 44.3% | 37.1% | +0.0% |
| solar | Média da semana anterior | 176 | 35.3% | 27.8% | +19.8% |
| solar | Persistência (D-1) | 188 | 36.4% | 30.8% | +14.2% |
