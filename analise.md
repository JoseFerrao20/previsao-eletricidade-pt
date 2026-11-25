MAE (MW) por segmento nas mesmas 52 semanas, horizontes D e D+1 agregados. *Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a prevista na emissão, por isso os segmentos são conhecidos de antemão.

**consumo**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 284 | 490 | 490 (naive) | +42% |
| Estação | primavera | 4 400 | 143 | 311 | 311 (naive) | +54% |
| Estação | verão | 4 416 | 156 | 327 | 327 (naive) | +52% |
| Estação | outono | 4 320 | 157 | 276 | 276 (naive) | +43% |
| Tipo de dia | dia útil | 11 896 | 185 | 352 | 352 (naive) | +48% |
| Tipo de dia | fim de semana | 4 796 | 178 | 297 | 297 (naive) | +40% |
| Tipo de dia | feriado | 620 | 220 | 689 | 689 (naive) | +68% |
| Tipo de dia | ponte | 144 | 267 | 554 | 333 (média sem.) | +20% |
| Temperatura prevista | < 10 °C | 1 638 | 237 | 387 | 387 (naive) | +39% |
| Temperatura prevista | 10–20 °C | 10 955 | 184 | 338 | 338 (naive) | +46% |
| Temperatura prevista | 20–28 °C | 4 329 | 161 | 342 | 342 (naive) | +53% |
| Temperatura prevista | ≥ 28 °C | 534 | 234 | 572 | 572 (naive) | +59% |

**eolica**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 345 | 1500 | 1092 (média sem.) | +68% |
| Estação | primavera | 4 400 | 274 | 1135 | 853 (média sem.) | +68% |
| Estação | verão | 4 416 | 199 | 690 | 557 (média sem.) | +64% |
| Estação | outono | 4 320 | 242 | 1109 | 876 (média sem.) | +72% |
| Tipo de dia | dia útil | 11 896 | 257 | 1111 | 840 (média sem.) | +69% |
| Tipo de dia | fim de semana | 4 796 | 288 | 1059 | 840 (média sem.) | +66% |
| Tipo de dia | feriado | 620 | 228 | 1273 | 814 (persist.) | +72% |
| Tipo de dia | ponte | 144 | 240 | 1539 | 1264 (média sem.) | +81% |
| Vento previsto a 100 m | < 4 m/s | 8 402 | 192 | 931 | 723 (persist.) | +73% |
| Vento previsto a 100 m | 4–8 m/s | 6 937 | 318 | 1100 | 778 (média sem.) | +59% |
| Vento previsto a 100 m | 8–12 m/s | 1 656 | 382 | 1797 | 1467 (média sem.) | +74% |
| Vento previsto a 100 m | ≥ 12 m/s | 461 | 358 | 1902 | 1270 (persist.) | +72% |

**solar**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 73 | 205 | 150 (média sem.) | +51% |
| Estação | primavera | 4 400 | 123 | 222 | 177 (média sem.) | +30% |
| Estação | verão | 4 416 | 141 | 219 | 190 (média sem.) | +26% |
| Estação | outono | 4 320 | 110 | 226 | 178 (média sem.) | +38% |
| Tipo de dia | dia útil | 11 896 | 110 | 223 | 173 (média sem.) | +37% |
| Tipo de dia | fim de semana | 4 796 | 118 | 207 | 177 (média sem.) | +33% |
| Tipo de dia | feriado | 620 | 114 | 203 | 142 (média sem.) | +19% |
| Tipo de dia | ponte | 144 | 92 | 272 | 196 (persist.) | +53% |
| Nebulosidade prevista (horas de sol) | < 20 % | 2 270 | 242 | 402 | 346 (média sem.) | +30% |
| Nebulosidade prevista (horas de sol) | 20–60 % | 2 323 | 241 | 405 | 338 (média sem.) | +29% |
| Nebulosidade prevista (horas de sol) | ≥ 60 % | 3 268 | 230 | 523 | 393 (média sem.) | +42% |
