Relatório do monitor (2026-11-10T13:52:09+00:00)

Emissão: a previsão de 2026-11-10 saiu 7.6 h depois da meia-noite; nas últimas 1 origens, mediana 7.6 h e máximo 7.6 h.

### ⚠️ consumo (modelo 20261110T1129-7b8dc9d)
- MAE realizado (7 dias): 191 MW · naive sazonal: 318 MW · referência do backtest: 132 MW
- degradação: MAE 191 MW = 1.44× a referência (132)
- aviso: meteorologia invulgar para a época: 'populacao__temperature_2m' (PSI 0.27)
- aviso: meteorologia invulgar para a época: 'populacao__cloud_cover' (PSI 0.42)

### ⚠️ eolica (modelo 20261110T1130-7b8dc9d)
- MAE realizado (7 dias): 685 MW · naive sazonal: 1484 MW · referência do backtest: 228 MW
- degradação: MAE 685 MW = 3.01× a referência (228)
- aviso: meteorologia invulgar para a época: 'vento__wind_speed_100m' (PSI 0.70)

### ✅ solar (modelo 20261110T1130-7b8dc9d)
- MAE realizado (7 dias): 136 MW · naive sazonal: 230 MW · referência do backtest: 122 MW
- sem sinais de degradação
- aviso: meteorologia invulgar para a época: 'sol__cloud_cover' (PSI 0.48)
- aviso: meteorologia invulgar para a época: 'sol__temperature_2m' (PSI 0.27)

O retreino foi pedido automaticamente.