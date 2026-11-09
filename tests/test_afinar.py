"""Procura de hiperparâmetros (dados sintéticos)."""

import pandas as pd
import pytest

from eletricidade import afinar, features
from eletricidade.modelos import PARAMETROS_LGBM, ModeloLGBM


def test_candidatas_incluem_a_configuracao_atual_e_sao_unicas():
    c = afinar.candidatos(10)
    assert c[0] == {} and len({tuple(sorted(x.items())) for x in c[1:]}) == 9


def test_validacao_so_usa_semanas_antes_do_teste():
    semanas = afinar.semanas_validacao(pd.Timestamp("2025-11-03"), 8)
    assert max(semanas) + pd.Timedelta(days=6) < pd.Timestamp("2025-11-03")
    assert all(s.day_of_week == 0 for s in semanas)
    with pytest.raises(ValueError):
        afinar.semanas_validacao(pd.Timestamp("2025-11-04"), 8)


def test_procura_devolve_tabela_ordenada(horario_sintetico):
    grade = features.para_grade_local(horario_sintetico)
    ex = features.construir_exemplos(grade, None, "consumo")
    ate = afinar.semanas_validacao(
        pd.Timestamp(ex["dia"].max()).normalize() - pd.Timedelta(days=ex["dia"].max().day_of_week), 1, 1
    )[0]
    t = afinar.procurar(ex, "consumo", ate, n_semanas=2, n_candidatas=3)
    assert list(t["MAE_validacao"]) == sorted(t["MAE_validacao"]) and 0 in set(t["candidata"])


def test_parametros_por_alvo_partem_dos_globais():
    m = ModeloLGBM("consumo")
    assert (
        set(PARAMETROS_LGBM) <= set(m.parametros)
        and m.parametros["random_state"] == PARAMETROS_LGBM["random_state"]
    )
