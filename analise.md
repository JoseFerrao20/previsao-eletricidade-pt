MAE (MW) por segmento nas mesmas 52 semanas, horizontes D e D+1 agregados. *Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a prevista na emissão, por isso os segmentos são conhecidos de antemão.

**consumo**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 282 | 490 | 490 (naive) | +42% |
| Estação | primavera | 4 400 | 143 | 311 | 311 (naive) | +54% |
| Estação | verão | 4 416 | 157 | 327 | 327 (naive) | +52% |
| Estação | outono | 4 320 | 155 | 288 | 288 (naive) | +46% |
| Tipo de dia | dia útil | 11 896 | 184 | 353 | 353 (naive) | +48% |
| Tipo de dia | fim de semana | 4 796 | 177 | 306 | 306 (naive) | +42% |
| Tipo de dia | feriado | 620 | 219 | 689 | 689 (naive) | +68% |
| Tipo de dia | ponte | 144 | 267 | 554 | 333 (média sem.) | +20% |
| Temperatura prevista | < 10 °C | 1 731 | 228 | 389 | 389 (naive) | +41% |
| Temperatura prevista | 10–20 °C | 10 862 | 183 | 342 | 342 (naive) | +46% |
| Temperatura prevista | 20–28 °C | 4 329 | 161 | 342 | 342 (naive) | +53% |
| Temperatura prevista | ≥ 28 °C | 534 | 235 | 572 | 572 (naive) | +59% |

**eolica**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 344 | 1500 | 1092 (média sem.) | +68% |
| Estação | primavera | 4 400 | 274 | 1135 | 853 (média sem.) | +68% |
| Estação | verão | 4 416 | 198 | 690 | 557 (média sem.) | +64% |
| Estação | outono | 4 320 | 230 | 1139 | 928 (média sem.) | +75% |
| Tipo de dia | dia útil | 11 896 | 254 | 1110 | 862 (média sem.) | +71% |
| Tipo de dia | fim de semana | 4 796 | 285 | 1088 | 835 (média sem.) | +66% |
| Tipo de dia | feriado | 620 | 227 | 1273 | 814 (persist.) | +72% |
| Tipo de dia | ponte | 144 | 240 | 1539 | 1264 (média sem.) | +81% |
| Vento previsto a 100 m | < 4 m/s | 8 539 | 190 | 950 | 718 (persist.) | +74% |
| Vento previsto a 100 m | 4–8 m/s | 6 895 | 316 | 1101 | 782 (média sem.) | +60% |
| Vento previsto a 100 m | 8–12 m/s | 1 553 | 384 | 1865 | 1587 (média sem.) | +76% |
| Vento previsto a 100 m | ≥ 12 m/s | 469 | 356 | 1776 | 1351 (persist.) | +74% |

**solar**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 72 | 205 | 150 (média sem.) | +52% |
| Estação | primavera | 4 400 | 123 | 222 | 177 (média sem.) | +30% |
| Estação | verão | 4 416 | 140 | 219 | 190 (média sem.) | +26% |
| Estação | outono | 4 320 | 111 | 232 | 188 (média sem.) | +41% |
| Tipo de dia | dia útil | 11 896 | 110 | 223 | 177 (média sem.) | +38% |
| Tipo de dia | fim de semana | 4 796 | 117 | 212 | 178 (média sem.) | +34% |
| Tipo de dia | feriado | 620 | 111 | 203 | 142 (média sem.) | +21% |
| Tipo de dia | ponte | 144 | 93 | 272 | 196 (persist.) | +53% |
| Nebulosidade prevista (horas de sol) | < 20 % | 2 317 | 237 | 420 | 352 (persist.) | +33% |
| Nebulosidade prevista (horas de sol) | 20–60 % | 2 319 | 238 | 412 | 341 (média sem.) | +30% |
| Nebulosidade prevista (horas de sol) | ≥ 60 % | 3 238 | 233 | 518 | 397 (média sem.) | +41% |
