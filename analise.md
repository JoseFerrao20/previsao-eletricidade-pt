MAE (MW) por segmento nas mesmas 52 semanas, horizontes D e D+1 agregados. *Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a prevista na emissão, por isso os segmentos são conhecidos de antemão.

**consumo**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 324 | 490 | 490 (naive) | +34% |
| Estação | primavera | 4 400 | 161 | 311 | 311 (naive) | +48% |
| Estação | verão | 4 416 | 176 | 327 | 327 (naive) | +46% |
| Estação | outono | 4 320 | 168 | 277 | 277 (naive) | +39% |
| Tipo de dia | dia útil | 11 896 | 207 | 350 | 350 (naive) | +41% |
| Tipo de dia | fim de semana | 4 796 | 202 | 302 | 302 (naive) | +33% |
| Tipo de dia | feriado | 620 | 226 | 689 | 689 (naive) | +67% |
| Tipo de dia | ponte | 144 | 284 | 554 | 333 (média sem.) | +15% |
| Temperatura prevista | < 10 °C | 1 712 | 274 | 400 | 400 (naive) | +31% |
| Temperatura prevista | 10–20 °C | 10 947 | 201 | 337 | 337 (naive) | +40% |
| Temperatura prevista | 20–28 °C | 4 268 | 186 | 339 | 339 (naive) | +45% |
| Temperatura prevista | ≥ 28 °C | 529 | 276 | 569 | 569 (naive) | +51% |

**eolica**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 470 | 1500 | 1092 (média sem.) | +57% |
| Estação | primavera | 4 400 | 374 | 1135 | 853 (média sem.) | +56% |
| Estação | verão | 4 416 | 262 | 690 | 557 (média sem.) | +53% |
| Estação | outono | 4 320 | 317 | 1128 | 921 (média sem.) | +66% |
| Tipo de dia | dia útil | 11 896 | 345 | 1121 | 862 (média sem.) | +60% |
| Tipo de dia | fim de semana | 4 796 | 379 | 1050 | 828 (média sem.) | +54% |
| Tipo de dia | feriado | 620 | 367 | 1273 | 814 (persist.) | +55% |
| Tipo de dia | ponte | 144 | 386 | 1539 | 1264 (média sem.) | +69% |
| Vento previsto a 100 m | < 4 m/s | 8 538 | 265 | 954 | 718 (persist.) | +63% |
| Vento previsto a 100 m | 4–8 m/s | 6 984 | 438 | 1111 | 791 (média sem.) | +45% |
| Vento previsto a 100 m | 8–12 m/s | 1 458 | 492 | 1845 | 1562 (média sem.) | +69% |
| Vento previsto a 100 m | ≥ 12 m/s | 476 | 355 | 1670 | 1316 (persist.) | +73% |

**solar**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 83 | 205 | 150 (média sem.) | +44% |
| Estação | primavera | 4 400 | 136 | 222 | 177 (média sem.) | +23% |
| Estação | verão | 4 416 | 144 | 219 | 190 (média sem.) | +24% |
| Estação | outono | 4 320 | 116 | 229 | 182 (média sem.) | +36% |
| Tipo de dia | dia útil | 11 896 | 120 | 222 | 176 (média sem.) | +32% |
| Tipo de dia | fim de semana | 4 796 | 121 | 210 | 174 (média sem.) | +30% |
| Tipo de dia | feriado | 620 | 109 | 203 | 142 (média sem.) | +23% |
| Tipo de dia | ponte | 144 | 108 | 272 | 196 (persist.) | +45% |
| Nebulosidade prevista (horas de sol) | < 20 % | 2 240 | 244 | 422 | 354 (persist.) | +31% |
| Nebulosidade prevista (horas de sol) | 20–60 % | 2 329 | 258 | 417 | 348 (média sem.) | +26% |
| Nebulosidade prevista (horas de sol) | ≥ 60 % | 3 310 | 254 | 508 | 387 (média sem.) | +34% |
