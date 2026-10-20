"""Testes das métricas com casos pequenos, montados à mão, em que o resultado certo se confere de cabeça."""

import math

import pandas as pd
import pytest

from analise import metricas as m

PEDIDO, EMPRESA = m.PEDIDO, m.EMPRESA


def pessoas(*linhas):
    cols = ["id", "unidade", "area", "cargo", "lider", "data_admissao", "data_desligamento", "tipo_desligamento"]
    df = pd.DataFrame(linhas, columns=cols)
    df["data_admissao"] = pd.to_datetime(df["data_admissao"])
    df["data_desligamento"] = pd.to_datetime(df["data_desligamento"])
    return df


def p(id_, adm, desl=None, tipo=None, area="Vendas", lider="L01", cargo="Cargo A", unidade="U1"):
    return (id_, unidade, area, cargo, lider, adm, desl, tipo)


SALARIOS = {"Cargo A": 3000.0, "Cargo B": 2000.0}


CUSTO = {
    "encargos_sobre_salario": 0.5,
    "deposito_fgts_mensal": 0.08,
    "multa_fgts": 0.40,
    "aviso_previo_dias_base": 30,
    "aviso_previo_dias_por_ano": 3,
    "aviso_previo_dias_maximo": 90,
    "custo_administrativo_desligamento": 100.0,
    "dias_experiencia": 90,
    "custo_recrutamento": 500.0,
    "custo_admissao": 200.0,
    "custo_treinamento": 300.0,
    "produtividade_mes": [0.5, 0.75],
}


# ---------------------------------------------------------------- quadro e rotatividade

def test_ativos_em_conta_quem_sai_no_proprio_dia():
    df = pessoas(p("A", "2024-01-01"), p("B", "2024-01-01", "2024-03-10", PEDIDO), p("C", "2024-03-11"))
    assert m.ativos_em(df, "2024-03-10").tolist() == [True, True, False]
    assert m.ativos_em(df, "2024-03-11").tolist() == [True, False, True]


def test_rotatividade_mensal_separa_os_tipos():
    # Março: 4 ativos no dia 1; saem 1 por pedido e 1 pela empresa; ninguém entra.
    # Quadro médio = (4 + 2) / 2 = 3. Taxa = 2/3, sendo 1/3 de cada tipo.
    df = pessoas(
        p("A", "2024-01-01"),
        p("B", "2024-01-01"),
        p("C", "2024-01-01", "2024-03-05", PEDIDO),
        p("D", "2024-01-01", "2024-03-31", EMPRESA),
    )
    out = m.rotatividade_mensal(df, m.meses_do_periodo("2024-03-01", 2))
    marco, abril = out.iloc[0], out.iloc[1]
    assert (marco.quadro_inicio, marco.quadro_fim, marco.quadro_medio) == (4, 2, 3.0)
    assert marco.saidas == 2
    assert marco.taxa == pytest.approx(2 / 3)
    assert marco.taxa_pedido == pytest.approx(1 / 3)
    assert marco.taxa_empresa == pytest.approx(1 / 3)
    assert abril.saidas == 0 and abril.taxa == 0


def test_rotatividade_mensal_por_grupo():
    df = pessoas(
        p("A", "2024-01-01", area="Vendas"),
        p("B", "2024-01-01", "2024-03-15", PEDIDO, area="Vendas"),
        p("C", "2024-01-01", area="Caixa"),
    )
    out = m.rotatividade_mensal(df, m.meses_do_periodo("2024-03-01", 1), por=["area"]).set_index("area")
    assert out.loc["Vendas", "taxa"] == pytest.approx(1 / 1.5)
    assert out.loc["Caixa", "taxa"] == 0


def test_rotatividade_anualizada_ajusta_para_12_meses():
    # 6 meses, quadro médio sempre 10, 3 saídas no total -> 3/10 em 6 meses = 60% ao ano
    mensal = pd.DataFrame({
        "mes": pd.period_range("2024-01", periods=6, freq="M"),
        "quadro_medio": [10.0] * 6,
        "saidas": [1, 0, 1, 0, 1, 0],
        "saidas_pedido": [1, 0, 0, 0, 1, 0],
        "saidas_empresa": [0, 0, 1, 0, 0, 0],
    })
    out = m.rotatividade_anualizada(mensal).iloc[0]
    assert out.taxa_anual == pytest.approx(0.6)
    assert out.taxa_anual_pedido == pytest.approx(0.4)
    assert out.taxa_anual_empresa == pytest.approx(0.2)


# ---------------------------------------------------------------- 90 dias

def test_saida_90_dias_limite_e_elegibilidade():
    df = pessoas(
        p("A", "2024-01-01", "2024-03-30", EMPRESA),   # 89 dias de casa: conta
        p("B", "2024-01-01", "2024-03-31", PEDIDO),    # 90 dias de casa: não conta
        p("C", "2024-01-01"),                          # ficou
        p("D", "2024-02-01", "2024-02-10", PEDIDO),    # 9 dias: conta
        p("E", "2023-06-01", "2024-01-15", PEDIDO),    # admitido antes do período: fora
        p("F", "2024-05-01"),                          # ainda não completaria 90 dias: fora
    )
    out = m.saida_90_dias(df, "2024-01-01", "2024-06-30").iloc[0]
    assert out.admitidos == 4
    assert out.sairam_90_dias == 2
    assert out.taxa_90_dias == pytest.approx(0.5)


def test_saida_90_dias_por_lider():
    df = pessoas(
        p("A", "2024-01-01", "2024-01-20", PEDIDO, lider="L01"),
        p("B", "2024-01-01", lider="L01"),
        p("C", "2024-01-01", lider="L02"),
    )
    out = m.saida_90_dias(df, "2024-01-01", "2024-12-31", por=["lider"]).set_index("lider")
    assert out.loc["L01", "taxa_90_dias"] == pytest.approx(0.5)
    assert out.loc["L02", "taxa_90_dias"] == 0


# ---------------------------------------------------------------- absenteísmo

def test_absenteismo_total_e_por_grupo_e_meses():
    df = pessoas(p("A", "2024-01-01", area="Vendas"), p("B", "2024-01-01", area="Caixa"))
    faltas = pd.DataFrame({
        "id": ["A", "A", "B", "B"],
        "mes": ["2024-01", "2024-02", "2024-01", "2024-02"],
        "dias_previstos": [20, 20, 20, 20],
        "faltas": [2, 0, 1, 1],
    })
    assert m.absenteismo(faltas).iloc[0].absenteismo == pytest.approx(4 / 80)
    por_area = m.absenteismo(faltas, df, ["area"]).set_index("area")
    assert por_area.loc["Vendas", "absenteismo"] == pytest.approx(2 / 40)
    assert por_area.loc["Caixa", "absenteismo"] == pytest.approx(2 / 40)
    so_fev = m.absenteismo(faltas, meses=["2024-02"]).iloc[0]
    assert so_fev.absenteismo == pytest.approx(1 / 40)


def test_faltas_antes_da_saida_compara_com_quem_ficou():
    meses = m.meses_do_periodo("2024-01-01", 6)  # jan a jun
    df = pessoas(
        p("S", "2023-01-01", "2024-05-10", PEDIDO),   # sai em maio: janela fev, mar, abr
        p("X", "2024-03-01", "2024-05-20", PEDIDO),   # admitido dentro da janela: fora
        p("F", "2023-01-01"),                          # ficou: janela final abr, mai, jun
    )
    linhas = []
    for mes, falta in zip(["2024-01", "2024-02", "2024-03", "2024-04", "2024-05"], [0, 2, 2, 2, 5]):
        linhas.append(("S", mes, 20, falta))
    for mes in ["2024-03", "2024-04", "2024-05"]:
        linhas.append(("X", mes, 20, 10))
    for mes, falta in zip(["2024-01", "2024-02", "2024-03", "2024-04", "2024-05", "2024-06"], [9, 9, 9, 1, 0, 2]):
        linhas.append(("F", mes, 20, falta))
    faltas = pd.DataFrame(linhas, columns=["id", "mes", "dias_previstos", "faltas"])

    out = m.faltas_antes_da_saida(df, faltas, meses)
    assert out["saiu"] == pytest.approx(6 / 60)      # fev, mar, abr de S; maio (mês da saída) não entra
    assert out["ficou"] == pytest.approx(19 / 60)    # F nos mesmos meses: fev 9, mar 9, abr 1 em 20 dias cada
    assert out["pessoas_saiu"] == 1 and out["pessoas_ficou"] == 1
    assert out["saiu_detalhe"]["faltas"] == 6 and out["saiu_detalhe"]["dias"] == 60
    assert out["por_tipo"][PEDIDO]["saiu"]["taxa"] == pytest.approx(0.1)
    assert out["por_tipo"][PEDIDO]["ficou"]["taxa"] == pytest.approx(19 / 60)
    assert math.isnan(out["por_tipo"][EMPRESA]["saiu"]["taxa"])
    curva = out["curva"].set_index("meses_antes")
    assert curva.loc[4, "absenteismo"] == 0          # janeiro, 4 meses antes de maio


# ---------------------------------------------------------------- custo

def test_custo_pedido_de_demissao_nao_tem_aviso_nem_multa():
    pessoa = pessoas(p("A", "2022-01-01", "2024-01-01", PEDIDO)).iloc[0]
    c = m.custo_por_saida(pessoa, CUSTO, SALARIOS)
    assert c["salario"] == 3000.0                    # salário do cargo, não da pessoa
    assert c["rescisao"] == 100.0
    assert c["reposicao"] == 1000.0
    # rampa: 3000 x 1,5 x ((1-0,5) + (1-0,75)) = 4500 x 0,75 = 3375
    assert c["rampa"] == pytest.approx(3375.0)
    assert c["total"] == pytest.approx(4475.0)


def test_custo_desligamento_pela_empresa_apos_dois_anos():
    # 730 dias = 2 anos completos -> aviso de 36 dias; FGTS = 8% x 3000 x 730/30
    pessoa = pessoas(p("A", "2022-01-01", "2024-01-01", EMPRESA)).iloc[0]
    c = m.custo_por_saida(pessoa, CUSTO, SALARIOS)
    aviso = 3000 / 30 * 36
    multa = 0.40 * 0.08 * 3000 * (730 / 30)
    assert c["rescisao"] == pytest.approx(100 + aviso + multa)


def test_custo_desligamento_pela_empresa_na_experiencia():
    pessoa = pessoas(p("A", "2024-01-01", "2024-02-15", EMPRESA, cargo="Cargo B")).iloc[0]
    assert m.custo_por_saida(pessoa, CUSTO, SALARIOS)["rescisao"] == 100.0


def test_aviso_previo_tem_teto():
    pessoa = pessoas(p("A", "2000-01-01", "2024-01-01", EMPRESA)).iloc[0]
    c = m.custo_por_saida(pessoa, CUSTO, SALARIOS)
    dias = (pessoa.data_desligamento - pessoa.data_admissao).days
    assert c["rescisao"] == pytest.approx(100 + 3000 / 30 * 90 + 0.40 * 0.08 * 3000 * dias / 30)


def test_custo_rotatividade_so_considera_saidas_do_periodo():
    df = pessoas(
        p("A", "2022-01-01", "2024-01-10", PEDIDO),
        p("B", "2022-01-01", "2023-12-31", PEDIDO),
        p("C", "2022-01-01"),
    )
    out = m.custo_rotatividade(df, CUSTO, SALARIOS, "2024-01-01", "2024-12-31")
    assert out["id"].tolist() == ["A"]
    assert out["total"].iloc[0] == pytest.approx(4475.0)


def test_cenarios_de_custo_baixo_medio_alto():
    custo = {**CUSTO, "cenarios": {"baixo": {"custo_recrutamento": 100.0}, "alto": {"custo_recrutamento": 900.0}}}
    assert m.cenario_custo(custo, "medio")["custo_recrutamento"] == 500.0
    assert "cenarios" not in m.cenario_custo(custo, "medio")
    df = pessoas(p("A", "2022-01-01", "2024-01-10", PEDIDO))
    sens = m.sensibilidade_custo(df, custo, SALARIOS, "2024-01-01", "2024-12-31").set_index("cenario")
    assert sens.loc["medio", "total"] == pytest.approx(4475.0)
    assert sens.loc["baixo", "total"] == pytest.approx(4475.0 - 400)
    assert sens.loc["alto", "total"] == pytest.approx(4475.0 + 400)


# ---------------------------------------------------------------- índice

INDICE = {"peso_rotatividade_12m": 0.4, "peso_saida_90_dias": 0.3, "peso_absenteismo_6m": 0.3,
          "referencia_rotatividade_12m": 1.0, "referencia_saida_90_dias": 0.5, "referencia_absenteismo_6m": 0.08}
BASE = 5


def fatores(**kw):
    linha = {"lider": "L01", "pessoas_12m": 10, "admitidos_90_dias": 10,
             "rotatividade_12m": 0.5, "saida_90_dias": 0.2, "absenteismo_6m": 0.02}
    linha.update(kw)
    return pd.DataFrame([linha])


def test_indice_componentes_de_0_a_1_e_contribuicoes():
    # 0,5 / 1 = 0,5; 0,2 / 0,5 = 0,4; 0,02 / 0,08 = 0,25
    out = m.indice_risco(fatores(), INDICE, BASE).iloc[0]
    assert out.comp_rotatividade_12m == pytest.approx(0.5)
    assert out.comp_saida_90_dias == pytest.approx(0.4)
    assert out.comp_absenteismo_6m == pytest.approx(0.25)
    assert out.contrib_rotatividade_12m == pytest.approx(0.20)
    assert out.contrib_saida_90_dias == pytest.approx(0.12)
    assert out.contrib_absenteismo_6m == pytest.approx(0.075)
    assert out.indice == pytest.approx(0.395)


def test_componentes_ponderados_somam_o_indice():
    df = pd.concat([fatores(lider="L01"), fatores(lider="L02", rotatividade_12m=2.0, absenteismo_6m=0.3),
                    fatores(lider="L03", saida_90_dias=0.0, absenteismo_6m=0.0)], ignore_index=True)
    out = m.indice_risco(df, INDICE, BASE)
    soma = out[[f"contrib_{c}" for c in m.COMPONENTES]].sum(axis=1)
    assert (soma - out["indice"]).abs().max() < 1e-12
    for c in m.COMPONENTES:
        assert out[f"comp_{c}"].between(0, 1).all()
    assert out.set_index("lider").loc["L02", "indice"] == pytest.approx(0.4 + 0.12 + 0.3)  # dois componentes no teto


def test_grupo_com_menos_de_5_pessoas_nao_recebe_indice():
    df = pd.concat([fatores(lider="L01", pessoas_12m=4), fatores(lider="L02", pessoas_12m=5)], ignore_index=True)
    out = m.indice_risco(df, INDICE, BASE).set_index("lider")
    assert bool(out.loc["L01", "base_insuficiente"])
    assert math.isnan(out.loc["L01", "indice"])
    assert all(math.isnan(out.loc["L01", f"contrib_{c}"]) for c in m.COMPONENTES)
    assert not bool(out.loc["L02", "base_insuficiente"])
    assert out.loc["L02", "indice"] == pytest.approx(0.395)


def test_componente_sem_base_nao_entra_e_os_pesos_restantes_somam_1():
    # 4 admissões: o componente dos 90 dias sai da conta, sem valor imputado
    out = m.indice_risco(fatores(admitidos_90_dias=4, saida_90_dias=1.0), INDICE, BASE).iloc[0]
    assert out.componentes_usados == 2
    assert math.isnan(out.comp_saida_90_dias) and math.isnan(out.contrib_saida_90_dias)
    assert math.isnan(out.peso_saida_90_dias)
    # 0,40 e 0,30 viram 0,40/0,70 e 0,30/0,70 (0,57 e 0,43), que somam 1
    assert out.peso_rotatividade_12m == pytest.approx(0.4 / 0.7)
    assert out.peso_absenteismo_6m == pytest.approx(0.3 / 0.7)
    assert out.peso_rotatividade_12m + out.peso_absenteismo_6m == pytest.approx(1.0)
    # índice = 0,5 x 0,4/0,7 + 0,25 x 0,3/0,7; a taxa de 90 dias (1,0) não pesa em nada
    assert out.indice == pytest.approx(0.5 * 0.4 / 0.7 + 0.25 * 0.3 / 0.7)
    assert out.indice == pytest.approx(out.contrib_rotatividade_12m + out.contrib_absenteismo_6m)


def test_com_base_completa_os_tres_componentes_entram_com_os_pesos_declarados():
    out = m.indice_risco(fatores(), INDICE, BASE).iloc[0]
    assert out.componentes_usados == 3
    assert (out.peso_rotatividade_12m, out.peso_saida_90_dias, out.peso_absenteismo_6m) == pytest.approx((0.4, 0.3, 0.3))


def test_indice_recusa_pesos_que_nao_somam_1():
    with pytest.raises(ValueError):
        m.indice_risco(fatores(), {**INDICE, "peso_absenteismo_6m": 0.5}, BASE)
