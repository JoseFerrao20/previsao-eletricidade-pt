from datetime import date

import numpy as np
import pandas as pd
import pytest

from eletricidade import ren
from tests.conftest import payload_ren


def test_normalizar_remove_acentos_e_maiusculas():
    assert ren.normalizar("  Eólica  ") == "eolica"
    assert ren.normalizar("Hídrica") == "hidrica"


def test_identificar_series_distingue_consumo_de_bombagem():
    nomes = ["Consumo", "Consumo + Bombagem", "Eólica", "Solar"]
    assert ren.identificar_series(nomes) == {"consumo": "Consumo", "eolica": "Eólica", "solar": "Solar"}


def test_identificar_series_falha_se_ambiguo_ou_ausente():
    with pytest.raises(ren.ErroREN):
        ren.identificar_series(["Consumo", "Eólica", "Solar", "Solar Térmica"])
    with pytest.raises(ren.ErroREN):
        ren.identificar_series(["Consumo", "Eólica"])


def test_intervalos_dias_normais_e_mudancas_de_hora():
    assert len(ren.intervalos_utc(date(2025, 6, 1))) == 96
    assert len(ren.intervalos_utc(date(2025, 3, 30))) == 92  # hora avança
    assert len(ren.intervalos_utc(date(2025, 10, 26))) == 100  # hora recua
    # meia-noite de Lisboa no verão é 23:00 UTC do dia anterior
    assert ren.intervalos_utc(date(2025, 6, 1))[0] == pd.Timestamp("2025-05-31 23:00", tz="UTC")


@pytest.mark.parametrize("dia", [date(2025, 6, 1), date(2025, 3, 30), date(2025, 10, 26)])
def test_interpretar_dia(dia):
    tabela = ren.interpretar_dia(payload_ren(dia), dia)
    assert list(tabela.columns) == ["consumo", "eolica", "solar"]
    assert len(tabela) == len(ren.intervalos_utc(dia))
    assert tabela.index.is_monotonic_increasing and tabela.index.is_unique


def test_interpretar_dia_rejeita_numero_de_intervalos_errado():
    with pytest.raises(ren.ErroREN, match="intervalos"):
        ren.interpretar_dia(payload_ren(date(2025, 3, 30), n=96), date(2025, 3, 30))


def test_interpretar_aceita_xaxis_em_lista_e_pontos_em_dicionario():
    dia = date(2025, 6, 1)
    p = payload_ren(dia)
    p["xAxis"] = [p["xAxis"]]
    p["series"][1]["data"] = [{"y": 5.0}] * 96
    p["series"][2]["data"][-1] = None  # dia corrente incompleto
    tabela = ren.interpretar_dia(p, dia)
    assert (tabela["eolica"] == 5.0).all()
    assert np.isnan(tabela["solar"].iloc[-1])


def test_para_horario_so_fecha_horas_completas():
    dia = date(2025, 6, 1)
    p = payload_ren(dia)
    p["series"][5]["data"][-1] = None
    horario = ren.para_horario(ren.interpretar_dia(p, dia))
    assert len(horario) == 24
    assert np.isnan(horario["consumo"].iloc[-1])
    assert horario["consumo"].iloc[0] == pytest.approx(1001.5)  # média de 1000..1003


def test_dias_a_descarregar_e_incremental(tmp_path):
    for d in (date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)):
        caminho = ren.caminho_bruto(d, tmp_path)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text("{}")
    dias = ren.dias_a_descarregar(date(2025, 1, 1), date(2025, 1, 5), tmp_path, rever=2)
    # 1..3 já existem; 4 e 5 em falta (e também são os revistos)
    assert dias == [date(2025, 1, 4), date(2025, 1, 5)]
    dias = ren.dias_a_descarregar(date(2025, 1, 1), date(2025, 1, 3), tmp_path, rever=2)
    assert dias == [date(2025, 1, 2), date(2025, 1, 3)]  # últimos dois são sempre revistos


def test_atualizar_regista_falhas_sem_parar(tmp_path, monkeypatch):
    def falso(dia, sessao=None):
        return payload_ren(dia, n=96)  # errado no dia de mudança de hora

    monkeypatch.setattr(ren, "descarregar_dia", falso)
    feitos, falhas = ren.atualizar(date(2025, 3, 29), date(2025, 3, 31), tmp_path, pausa=0)
    assert feitos == [date(2025, 3, 29), date(2025, 3, 31)]
    assert list(falhas) == [date(2025, 3, 30)]
    horario = ren.construir_horario(tmp_path)
    assert horario.index.tz is not None


def test_atualizar_para_quando_a_fonte_nao_responde(tmp_path):
    """Vários dias seguidos sem resposta: pára logo, não esgota o tempo do workflow."""
    pedidos = []

    def sem_resposta(dia, sessao):
        pedidos.append(dia)
        raise ren.ErroREN(f"REN {dia}: timeout")

    with pytest.raises(ren.FonteIndisponivel):
        ren.atualizar(date(2025, 1, 1), date(2025, 3, 1), raiz=tmp_path, pausa=0, descarregar=sem_resposta)
    assert len(pedidos) == 3


def test_atualizar_tolera_falhas_isoladas(tmp_path):
    def intermitente(dia, sessao):
        if dia.day % 2 == 0:
            raise ren.ErroREN(f"REN {dia}: erro isolado")
        return payload_ren(dia)

    feitos, falhas = ren.atualizar(
        date(2025, 1, 1), date(2025, 1, 6), raiz=tmp_path, pausa=0, descarregar=intermitente
    )
    assert len(falhas) == 3 and len(feitos) == 3
