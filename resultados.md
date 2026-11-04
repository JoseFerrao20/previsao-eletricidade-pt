Backtest semana a semana: 26 semanas de teste, de 2026-05-04 a 2026-11-01; horizontes D e D+1 agregados. MAPE e sMAPE do solar só nas horas com mais de 100 MW.

| Alvo | Modelo | MAE (MW) | MAPE | sMAPE | Skill vs. naive sazonal |
|------|--------|---------:|-----:|------:|------------------------:|
| consumo | **LightGBM** | 189 | 3.2% | 3.2% | +35.9% |
| consumo | Naive sazonal (7 dias) | 295 | 4.9% | 5.0% | +0.0% |
| consumo | Média da semana anterior | 422 | 7.3% | 7.1% | -43.2% |
| consumo | Persistência (D-1) | 508 | 8.7% | 8.6% | -72.2% |
| eolica | **LightGBM** | 420 | 83.2% | 48.1% | +48.5% |
| eolica | Naive sazonal (7 dias) | 814 | 153.8% | 75.0% | +0.0% |
| eolica | Média da semana anterior | 636 | 126.3% | 62.0% | +21.9% |
| eolica | Persistência (D-1) | 662 | 107.5% | 64.0% | +18.7% |
| solar | **LightGBM** | 149 | 17.6% | 16.9% | +33.2% |
| solar | Naive sazonal (7 dias) | 223 | 27.2% | 24.7% | +0.0% |
| solar | Média da semana anterior | 185 | 21.9% | 19.2% | +17.1% |
| solar | Persistência (D-1) | 193 | 21.8% | 20.2% | +13.2% |
