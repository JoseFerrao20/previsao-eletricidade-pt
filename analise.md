MAE (MW) por segmento nas mesmas 52 semanas, horizontes D e D+1 agregados. *Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a prevista na emissão, por isso os segmentos são conhecidos de antemão.

**consumo**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 284 | 490 | 490 (naive) | +42% |
| Estação | primavera | 4 400 | 143 | 311 | 311 (naive) | +54% |
| Estação | verão | 4 416 | 156 | 327 | 327 (naive) | +52% |
| Estação | outono | 4 320 | 156 | 288 | 288 (naive) | +46% |
| Tipo de dia | dia útil | 11 896 | 185 | 355 | 355 (naive) | +48% |
| Tipo de dia | fim de semana | 4 796 | 177 | 301 | 301 (naive) | +41% |
| Tipo de dia | feriado | 620 | 220 | 689 | 689 (naive) | +68% |
| Tipo de dia | ponte | 144 | 267 | 554 | 333 (média sem.) | +20% |
| Temperatura prevista | < 10 °C | 1 731 | 229 | 389 | 389 (naive) | +41% |
| Temperatura prevista | 10–20 °C | 10 862 | 184 | 342 | 342 (naive) | +46% |
| Temperatura prevista | 20–28 °C | 4 329 | 161 | 342 | 342 (naive) | +53% |
| Temperatura prevista | ≥ 28 °C | 534 | 234 | 572 | 572 (naive) | +59% |

**eolica**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 345 | 1500 | 1092 (média sem.) | +68% |
| Estação | primavera | 4 400 | 274 | 1135 | 853 (média sem.) | +68% |
| Estação | verão | 4 416 | 199 | 690 | 557 (média sem.) | +64% |
| Estação | outono | 4 320 | 233 | 1175 | 897 (média sem.) | +74% |
| Tipo de dia | dia útil | 11 896 | 256 | 1132 | 849 (média sem.) | +70% |
| Tipo de dia | fim de semana | 4 796 | 283 | 1067 | 838 (média sem.) | +66% |
| Tipo de dia | feriado | 620 | 228 | 1273 | 814 (persist.) | +72% |
| Tipo de dia | ponte | 144 | 240 | 1539 | 1264 (média sem.) | +81% |
| Vento previsto a 100 m | < 4 m/s | 8 512 | 190 | 953 | 716 (persist.) | +73% |
| Vento previsto a 100 m | 4–8 m/s | 6 984 | 317 | 1111 | 782 (média sem.) | +60% |
| Vento previsto a 100 m | 8–12 m/s | 1 519 | 389 | 1902 | 1553 (média sem.) | +75% |
| Vento previsto a 100 m | ≥ 12 m/s | 441 | 354 | 1892 | 1295 (persist.) | +73% |

**solar**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 73 | 205 | 150 (média sem.) | +51% |
| Estação | primavera | 4 400 | 123 | 222 | 177 (média sem.) | +30% |
| Estação | verão | 4 416 | 141 | 219 | 190 (média sem.) | +26% |
| Estação | outono | 4 320 | 110 | 242 | 191 (média sem.) | +42% |
| Tipo de dia | dia útil | 11 896 | 110 | 228 | 178 (média sem.) | +38% |
| Tipo de dia | fim de semana | 4 796 | 117 | 208 | 178 (média sem.) | +34% |
| Tipo de dia | feriado | 620 | 114 | 203 | 142 (média sem.) | +19% |
| Tipo de dia | ponte | 144 | 92 | 272 | 196 (persist.) | +53% |
| Nebulosidade prevista (horas de sol) | < 20 % | 2 317 | 240 | 420 | 352 (persist.) | +32% |
| Nebulosidade prevista (horas de sol) | 20–60 % | 2 319 | 239 | 412 | 342 (média sem.) | +30% |
| Nebulosidade prevista (horas de sol) | ≥ 60 % | 3 233 | 231 | 527 | 398 (média sem.) | +42% |
