import numpy as np
import pandas as pd
import pytest

from eletricidade import calendario, features, meteo
from tests.conftest import payload_meteo


def test_grade_local_mudancas_de_hora():
    idx = pd.date_range("2025-10-25 00:00", "2025-10-27 23:00", freq="1h", tz="UTC")
    tabela = pd.DataFrame({"consumo": np.arange(idx.size, dtype=float)}, index=idx)
    grade = features.para_grade_local(tabela)
    assert grade.index.get_level_values("hora").max() == 23
    # 26/10: 01:00 local repete-se -> média das duas horas UTC 00:00 e 01:00
    v = grade.loc[(pd.Timestamp("2025-10-26").date(), 1), "consumo"]
    assert v == pytest.approx(
        (tabela.loc["2025-10-26 00:00"].iloc[0] + tabela.loc["2025-10-26 01:00"].iloc[0]) / 2
    )

    idx = pd.date_range("2025-03-29", "2025-03-31 23:00", freq="1h", tz="UTC")
    grade = features.para_grade_local(pd.DataFrame({"consumo": 1.0}, index=idx))
    assert np.isnan(grade.loc[(pd.Timestamp("2025-03-30").date(), 1), "consumo"])  # 01:00 não existe


def _exemplos(horario):
    grade = features.para_grade_local(horario)
    return grade, features.construir_exemplos(grade, None, "consumo")


def test_features_sem_fuga_de_informacao(horario_sintetico):
    grade, ex = _exemplos(horario_sintetico)
    origem = ex["origem"].iloc[len(ex) // 2]
    # Alterar tudo a partir da origem não pode mudar as features dessa origem.
    alterado = horario_sintetico.copy()
    alterado.loc[alterado.index.tz_convert("Europe/Lisbon").normalize().tz_localize(None) >= origem] *= 10
    _, ex2 = _exemplos(alterado)
    cols = [c for c in features.colunas_features(ex) if c != "y"]
    a = ex[ex["origem"] == origem][cols].reset_index(drop=True)
    b = ex2[ex2["origem"] == origem][cols].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_definicao_das_referencias(horario_sintetico):
    grade, ex = _exemplos(horario_sintetico)
    m = grade["consumo"].unstack("hora")
    m.index = pd.DatetimeIndex(m.index)
    linha = ex[(ex["lead"] == 2)].iloc[100]
    dia, hora = linha["dia"], linha["hora"]
    assert linha["persistencia"] == pytest.approx(m.loc[dia - pd.Timedelta(days=2), hora])
    assert linha["naive_sazonal"] == pytest.approx(m.loc[dia - pd.Timedelta(days=7), hora])
    janela = [m.loc[dia - pd.Timedelta(days=k), hora] for k in range(2, 9)]
    assert linha["media_semana"] == pytest.approx(np.mean(janela))
    assert linha["origem"] == dia - pd.Timedelta(days=1)


def test_extensao_para_o_futuro(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ultimo = pd.Timestamp(max(grade.index.get_level_values("dia")))
    # o último dia local sintético está incompleto; em produção D-1 está fechado
    grade = grade[grade.index.get_level_values("dia") < ultimo.date()]
    ultimo -= pd.Timedelta(days=1)
    ex = features.construir_exemplos(grade, None, "consumo", ate=ultimo + pd.Timedelta(days=2))
    hoje = ex[ex["origem"] == ultimo + pd.Timedelta(days=1)]  # emissão à meia-noite seguinte
    assert len(hoje) == 48 and sorted(hoje["lead"].unique()) == [1, 2]
    assert hoje["y"].isna().all()
    cols = ["persistencia", "naive_sazonal", "media_semana", "max_30d"]
    assert hoje[cols].notna().all().all()


def test_meteo_interpretar_e_juntar(horario_sintetico):
    longo = meteo.interpretar(payload_meteo("2024-01-01", "2024-03-01"))
    grupos = meteo.agregar_por_grupo(longo)
    assert {"vento__wind_speed_100m", "sol__shortwave_radiation"} <= set(grupos.columns)
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, grupos, "eolica")
    jan = ex[ex["dia"] < "2024-02-28"]
    # lead 1 usa previous_day2, lead 2 usa previous_day3 (valores sintéticos = índice do ponto + N)
    assert jan.loc[jan["lead"] == 1, "vento__wind_speed_100m"].dropna().unique() == pytest.approx([4 + 2])
    assert jan.loc[jan["lead"] == 2, "vento__wind_speed_100m"].dropna().unique() == pytest.approx([4 + 3])


def test_calendario_feriados_e_pontes():
    dias = pd.Series(pd.to_datetime(["2026-04-25", "2026-06-05", "2026-12-07", "2026-11-04"]))
    cal = calendario.features_calendario(dias, pd.Series([0, 0, 0, 0]))
    assert cal["feriado"].tolist() == [1, 0, 0, 0]
    # 05/06/2026 é sexta depois do Corpo de Deus (quinta); 07/12 é segunda antes de 08/12
    assert cal["ponte"].tolist() == [0, 1, 1, 0]
