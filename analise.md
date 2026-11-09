MAE (MW) por segmento nas mesmas 52 semanas, horizontes D e D+1 agregados. *Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a prevista na emissão, por isso os segmentos são conhecidos de antemão.

**consumo**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 309 | 490 | 490 (naive) | +37% |
| Estação | primavera | 4 400 | 154 | 311 | 311 (naive) | +50% |
| Estação | verão | 4 416 | 162 | 327 | 327 (naive) | +51% |
| Estação | outono | 4 320 | 156 | 277 | 277 (naive) | +44% |
| Tipo de dia | dia útil | 11 896 | 197 | 350 | 350 (naive) | +44% |
| Tipo de dia | fim de semana | 4 796 | 182 | 302 | 302 (naive) | +40% |
| Tipo de dia | feriado | 620 | 232 | 689 | 689 (naive) | +66% |
| Tipo de dia | ponte | 144 | 279 | 554 | 333 (média sem.) | +16% |
| Temperatura prevista | < 10 °C | 1 712 | 262 | 393 | 393 (naive) | +33% |
| Temperatura prevista | 10–20 °C | 10 921 | 192 | 338 | 338 (naive) | +43% |
| Temperatura prevista | 20–28 °C | 4 289 | 170 | 339 | 339 (naive) | +50% |
| Temperatura prevista | ≥ 28 °C | 534 | 233 | 572 | 572 (naive) | +59% |

**eolica**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 345 | 1500 | 1092 (média sem.) | +68% |
| Estação | primavera | 4 400 | 274 | 1135 | 853 (média sem.) | +68% |
| Estação | verão | 4 416 | 199 | 690 | 557 (média sem.) | +64% |
| Estação | outono | 4 320 | 234 | 1128 | 921 (média sem.) | +75% |
| Tipo de dia | dia útil | 11 896 | 258 | 1121 | 862 (média sem.) | +70% |
| Tipo de dia | fim de semana | 4 796 | 278 | 1050 | 828 (média sem.) | +66% |
| Tipo de dia | feriado | 620 | 228 | 1273 | 814 (persist.) | +72% |
| Tipo de dia | ponte | 144 | 240 | 1539 | 1264 (média sem.) | +81% |
| Vento previsto a 100 m | < 4 m/s | 8 532 | 192 | 953 | 722 (persist.) | +73% |
| Vento previsto a 100 m | 4–8 m/s | 6 893 | 316 | 1096 | 772 (média sem.) | +59% |
| Vento previsto a 100 m | 8–12 m/s | 1 563 | 379 | 1836 | 1555 (média sem.) | +76% |
| Vento previsto a 100 m | ≥ 12 m/s | 468 | 366 | 1785 | 1286 (persist.) | +72% |

**solar**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 73 | 205 | 150 (média sem.) | +51% |
| Estação | primavera | 4 400 | 123 | 222 | 177 (média sem.) | +30% |
| Estação | verão | 4 416 | 141 | 219 | 190 (média sem.) | +26% |
| Estação | outono | 4 320 | 108 | 229 | 182 (média sem.) | +41% |
| Tipo de dia | dia útil | 11 896 | 109 | 222 | 176 (média sem.) | +38% |
| Tipo de dia | fim de semana | 4 796 | 116 | 210 | 174 (média sem.) | +33% |
| Tipo de dia | feriado | 620 | 114 | 203 | 142 (média sem.) | +19% |
| Tipo de dia | ponte | 144 | 92 | 272 | 196 (persist.) | +53% |
| Nebulosidade prevista (horas de sol) | < 20 % | 2 282 | 241 | 423 | 353 (persist.) | +32% |
| Nebulosidade prevista (horas de sol) | 20–60 % | 2 317 | 237 | 415 | 345 (média sem.) | +31% |
| Nebulosidade prevista (horas de sol) | ≥ 60 % | 3 275 | 228 | 509 | 386 (média sem.) | +41% |
