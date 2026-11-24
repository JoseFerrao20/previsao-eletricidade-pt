Backtest semana a semana: 52 semanas de teste, de 2025-11-24 a 2026-11-22; horizontes D e D+1 agregados. MAPE e sMAPE do solar só nas horas com mais de 100 MW.

| Alvo | Modelo | MAE (MW) | MAPE | sMAPE | Skill vs. naive sazonal |
|------|--------|---------:|-----:|------:|------------------------:|
| consumo | **LightGBM** | 185 | 2.9% | 2.9% | +47.3% |
| consumo | Naive sazonal (7 dias) | 351 | 5.6% | 5.5% | +0.0% |
| consumo | Média da semana anterior | 468 | 7.7% | 7.5% | -33.5% |
| consumo | Persistência (D-1) | 557 | 9.1% | 9.0% | -58.9% |
| eolica | **LightGBM** | 264 | 31.2% | 25.2% | +76.1% |
| eolica | Naive sazonal (7 dias) | 1106 | 210.0% | 79.3% | +0.0% |
| eolica | Média da semana anterior | 843 | 191.4% | 63.4% | +23.8% |
| eolica | Persistência (D-1) | 914 | 181.5% | 67.6% | +17.4% |
| solar | **LightGBM** | 112 | 18.7% | 17.7% | +48.6% |
| solar | Naive sazonal (7 dias) | 218 | 45.8% | 36.7% | +0.0% |
| solar | Média da semana anterior | 174 | 35.8% | 27.6% | +20.3% |
| solar | Persistência (D-1) | 189 | 37.0% | 31.3% | +13.4% |
