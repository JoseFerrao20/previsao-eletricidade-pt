MAE (MW) por segmento nas mesmas 52 semanas, horizontes D e D+1 agregados. *Melhor simples* é a melhor das três referências **dentro de cada segmento**, escolhida depois de ver o resultado (comparação deliberadamente exigente). A meteorologia é a prevista na emissão, por isso os segmentos são conhecidos de antemão.

**consumo**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 355 | 490 | 490 (naive) | +28% |
| Estação | primavera | 4 400 | 179 | 311 | 311 (naive) | +43% |
| Estação | verão | 4 416 | 204 | 327 | 327 (naive) | +38% |
| Estação | outono | 4 320 | 184 | 277 | 277 (naive) | +34% |
| Tipo de dia | dia útil | 11 896 | 226 | 350 | 350 (naive) | +36% |
| Tipo de dia | fim de semana | 4 796 | 240 | 302 | 302 (naive) | +20% |
| Tipo de dia | feriado | 620 | 217 | 689 | 689 (naive) | +69% |
| Tipo de dia | ponte | 144 | 276 | 554 | 333 (média sem.) | +17% |
| Temperatura prevista | < 10 °C | 1 712 | 299 | 400 | 400 (naive) | +25% |
| Temperatura prevista | 10–20 °C | 10 947 | 226 | 337 | 337 (naive) | +33% |
| Temperatura prevista | 20–28 °C | 4 268 | 201 | 339 | 339 (naive) | +41% |
| Temperatura prevista | ≥ 28 °C | 529 | 314 | 569 | 569 (naive) | +45% |

**eolica**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 696 | 1500 | 1092 (média sem.) | +36% |
| Estação | primavera | 4 400 | 563 | 1135 | 853 (média sem.) | +34% |
| Estação | verão | 4 416 | 383 | 690 | 557 (média sem.) | +31% |
| Estação | outono | 4 320 | 530 | 1128 | 921 (média sem.) | +42% |
| Tipo de dia | dia útil | 11 896 | 532 | 1121 | 862 (média sem.) | +38% |
| Tipo de dia | fim de semana | 4 796 | 545 | 1050 | 828 (média sem.) | +34% |
| Tipo de dia | feriado | 620 | 714 | 1273 | 814 (persist.) | +12% |
| Tipo de dia | ponte | 144 | 538 | 1539 | 1264 (média sem.) | +57% |
| Vento previsto a 100 m | < 4 m/s | 10 378 | 481 | 1004 | 756 (média sem.) | +36% |
| Vento previsto a 100 m | 4–8 m/s | 5 800 | 654 | 1158 | 889 (média sem.) | +26% |
| Vento previsto a 100 m | 8–12 m/s | 1 038 | 567 | 1819 | 1422 (persist.) | +60% |
| Vento previsto a 100 m | ≥ 12 m/s | 240 | 366 | 1499 | 1146 (persist.) | +68% |

**solar**

| Segmento | | Previsões | LightGBM | Naive sazonal | Melhor simples | Skill vs. melhor |
|---|---|---:|---:|---:|---:|---:|
| Estação | inverno | 4 320 | 103 | 205 | 150 (média sem.) | +31% |
| Estação | primavera | 4 400 | 144 | 222 | 177 (média sem.) | +19% |
| Estação | verão | 4 416 | 149 | 219 | 190 (média sem.) | +21% |
| Estação | outono | 4 320 | 132 | 229 | 182 (média sem.) | +27% |
| Tipo de dia | dia útil | 11 896 | 130 | 222 | 176 (média sem.) | +26% |
| Tipo de dia | fim de semana | 4 796 | 140 | 210 | 174 (média sem.) | +20% |
| Tipo de dia | feriado | 620 | 114 | 203 | 142 (média sem.) | +19% |
| Tipo de dia | ponte | 144 | 120 | 272 | 196 (persist.) | +39% |
| Nebulosidade prevista (horas de sol) | < 20 % | 2 710 | 259 | 430 | 353 (persist.) | +27% |
| Nebulosidade prevista (horas de sol) | 20–60 % | 1 833 | 282 | 420 | 342 (média sem.) | +18% |
| Nebulosidade prevista (horas de sol) | ≥ 60 % | 3 351 | 290 | 496 | 385 (média sem.) | +25% |
