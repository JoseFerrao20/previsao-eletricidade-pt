Backtest semana a semana: 52 semanas de teste, de 2025-11-03 a 2026-11-01; horizontes D e D+1 agregados. MAPE e sMAPE do solar só nas horas com mais de 100 MW.

| Alvo | Modelo | MAE (MW) | MAPE | sMAPE | Skill vs. naive sazonal |
|------|--------|---------:|-----:|------:|------------------------:|
| consumo | **LightGBM** | 230 | 3.7% | 3.7% | +34.5% |
| consumo | Naive sazonal (7 dias) | 351 | 5.6% | 5.5% | +0.0% |
| consumo | Média da semana anterior | 469 | 7.7% | 7.5% | -33.7% |
| consumo | Persistência (D-1) | 556 | 9.1% | 9.0% | -58.6% |
| eolica | **LightGBM** | 542 | 102.5% | 47.9% | +51.2% |
| eolica | Naive sazonal (7 dias) | 1111 | 212.9% | 79.0% | +0.0% |
| eolica | Média da semana anterior | 854 | 192.6% | 63.9% | +23.1% |
| eolica | Persistência (D-1) | 920 | 176.1% | 68.3% | +17.1% |
| solar | **LightGBM** | 132 | 24.2% | 21.7% | +39.6% |
| solar | Naive sazonal (7 dias) | 219 | 43.9% | 37.1% | +0.0% |
| solar | Média da semana anterior | 175 | 34.8% | 27.7% | +20.1% |
| solar | Persistência (D-1) | 189 | 36.6% | 31.0% | +13.8% |
