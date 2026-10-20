"""Testes dos dados gerados: reprodutibilidade, ausência de dados sensíveis e totais que batem."""

from pathlib import Path

import pandas as pd
import pytest

from analise import metricas as m
from scripts.gerar_dados import COLUNAS_FALTAS, COLUNAS_PESSOAS, gerar

RAIZ = Path(__file__).resolve().parents[1]
PREMISSAS = m.carregar_premissas(RAIZ / "config" / "premissas.toml")

# Termos que não podem aparecer em nenhum nome de coluna: dados sensíveis da LGPD (art. 5º, II),
# identificação direta e salário individual.
PROIBIDOS = ["nome", "cpf", "email", "telefone", "salario", "remuneracao", "genero", "sexo", "idade", "nascimento",
             "raca", "cor", "etnia", "religiao", "politic", "sindic", "saude", "doenca", "cid", "atestado",
             "motivo", "genetic", "biometr", "orientacao", "estado_civil", "deficiencia"]


@pytest.fixture(scope="module")
def dados():
    return gerar(PREMISSAS)


def test_mesma_semente_gera_os_mesmos_dados(dados):
    pessoas, faltas = dados
    pessoas2, faltas2 = gerar(PREMISSAS)
    pd.testing.assert_frame_equal(pessoas, pessoas2)
    pd.testing.assert_frame_equal(faltas, faltas2)
    outra, _ = gerar(PREMISSAS, semente=PREMISSAS["geracao"]["semente"] + 1)
    assert not outra.equals(pessoas)


def test_csv_publicado_e_igual_ao_gerado(dados):
    # o CSV incluído no repositório é exatamente o que o gerador produz com a semente do config
    pessoas, faltas = dados
    for df, arquivo in ((pessoas, "pessoas.csv"), (faltas, "faltas_mensais.csv")):
        publicado = (RAIZ / "dados" / arquivo).read_text(encoding="utf-8").replace("\r\n", "\n")
        assert df.to_csv(index=False, lineterminator="\n") == publicado, arquivo


def test_nenhuma_coluna_sensivel_nem_salario_individual(dados):
    pessoas, faltas = dados
    assert list(pessoas.columns) == COLUNAS_PESSOAS
    assert list(faltas.columns) == COLUNAS_FALTAS
    arquivos = [pd.read_csv(RAIZ / "dados" / "pessoas.csv"), pd.read_csv(RAIZ / "dados" / "faltas_mensais.csv")]
    for df in [pessoas, faltas, *arquivos]:
        for coluna in df.columns:
            partes = coluna.lower().split("_")   # compara por palavra: "unidade" não é "idade"
            assert not any(p.startswith(t) for p in partes for t in PROIBIDOS), f"coluna proibida: {coluna}"
    # pessoas só por código; faltas sem motivo, só contagem
    assert pessoas["id"].str.fullmatch(r"P\d{4}").all()
    assert pessoas["lider"].str.fullmatch(r"L\d{2}").all()
    assert pd.api.types.is_integer_dtype(faltas["faltas"])


def test_totais_batem_admissoes_saidas_e_quadro_por_mes(dados):
    pessoas, _ = dados
    pessoas = pessoas.copy()
    pessoas["data_admissao"] = pd.to_datetime(pessoas["data_admissao"])
    pessoas["data_desligamento"] = pd.to_datetime(pessoas["data_desligamento"])
    meses = m.meses_do_periodo(PREMISSAS["periodo"]["inicio"], PREMISSAS["periodo"]["meses"])
    inicio, fim = meses[0].start_time.normalize(), meses[-1].end_time.normalize()
    mensal = m.rotatividade_mensal(pessoas, meses)

    # quadro do fim do mês anterior + admissões menos saídas = quadro do fim do mês, em todos os meses
    conta = mensal["quadro_fim_mes_anterior"] + mensal["admissoes"] - mensal["saidas"]
    assert (conta == mensal["quadro_fim_mes"]).all()
    assert (mensal["quadro_fim_mes"].shift(1).iloc[1:] == mensal["quadro_fim_mes_anterior"].iloc[1:]).all()

    # somas do período iguais às contagens diretas na base
    assert mensal["admissoes"].sum() == pessoas["data_admissao"].between(inicio, fim).sum()
    assert mensal["saidas"].sum() == pessoas["data_desligamento"].between(inicio, fim).sum()
    assert mensal["saidas"].sum() == mensal["saidas_pedido"].sum() + mensal["saidas_empresa"].sum()
    assert mensal["quadro_fim_mes"].iloc[-1] == m.quadro_fim_do_dia(pessoas, fim)

    # por grupo, a soma das áreas é a rede
    por_area = m.rotatividade_mensal(pessoas, meses, ["area"])
    for col in ("admissoes", "saidas", "quadro_fim_mes"):
        assert (por_area.groupby("mes")[col].sum().values == mensal[col].values).all()


def test_faltas_so_nos_meses_ativos_e_nunca_acima_dos_dias_previstos(dados):
    pessoas, faltas = dados
    assert (faltas["faltas"] >= 0).all()
    assert (faltas["faltas"] <= faltas["dias_previstos"]).all()
    assert set(faltas["id"]) <= set(pessoas["id"])
