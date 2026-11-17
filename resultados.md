Backtest semana a semana: 52 semanas de teste, de 2025-11-17 a 2026-11-15; horizontes D e D+1 agregados. MAPE e sMAPE do solar só nas horas com mais de 100 MW.

| Alvo | Modelo | MAE (MW) | MAPE | sMAPE | Skill vs. naive sazonal |
|------|--------|---------:|-----:|------:|------------------------:|
| consumo | **LightGBM** | 185 | 2.9% | 2.9% | +47.8% |
| consumo | Naive sazonal (7 dias) | 354 | 5.6% | 5.6% | +0.0% |
| consumo | Média da semana anterior | 466 | 7.6% | 7.5% | -31.9% |
| consumo | Persistência (D-1) | 556 | 9.0% | 9.0% | -57.2% |
| eolica | **LightGBM** | 262 | 31.2% | 25.3% | +76.6% |
| eolica | Naive sazonal (7 dias) | 1122 | 213.7% | 80.1% | +0.0% |
| eolica | Média da semana anterior | 848 | 192.5% | 64.1% | +24.4% |
| eolica | Persistência (D-1) | 915 | 181.2% | 68.4% | +18.5% |
| solar | **LightGBM** | 112 | 18.5% | 17.6% | +49.6% |
| solar | Naive sazonal (7 dias) | 222 | 45.7% | 37.2% | +0.0% |
| solar | Média da semana anterior | 177 | 35.8% | 27.8% | +20.3% |
| solar | Persistência (D-1) | 189 | 36.6% | 30.8% | +14.8% |
