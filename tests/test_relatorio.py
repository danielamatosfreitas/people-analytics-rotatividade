"""Testes da regra de base pequena no texto do relatório."""

import re
from pathlib import Path

from analise import relatorio as r

RAIZ = Path(__file__).resolve().parents[1]


def test_percentual_sempre_com_numero_absoluto():
    assert r.fracao(2, 8) == "25% (2 de 8)"
    assert r.falta_txt(13, 260, 10) == "5,0% (13 faltas em 260 dias previstos)"


def test_grupo_com_menos_de_5_nao_recebe_percentual():
    assert r.fracao(2, 4) == "base insuficiente"
    assert r.fracao(0, 0) == "base insuficiente"
    assert r.taxa_ano(0.5, 2, 4.0, 4) == "base insuficiente"
    assert r.falta_txt(3, 60, 4) == "base insuficiente"


def test_fim_de_cada_barra_do_indice_e_igual_ao_indice():
    from analise import metricas as m
    premissas = m.carregar_premissas(RAIZ / "config" / "premissas.toml")
    pessoas, faltas = m.carregar_dados(RAIZ / "dados")
    meses = m.meses_do_periodo(premissas["periodo"]["inicio"], premissas["periodo"]["meses"])
    indice = m.indice_risco(m.fatores_por_grupo(pessoas, faltas, meses, ["unidade", "area", "lider"]),
                            premissas["indice"], premissas["relatorio"]["base_minima"])
    assert (indice["componentes_usados"] < 3).any(), "a base precisa ter equipes com 2 componentes para o teste valer"
    rotulos = list(indice["lider"])
    fig = r.fig_indice(indice, rotulos)
    barras = [t for t in fig.data if t.type == "bar"]
    texto = [t for t in fig.data if t.type == "scatter"][0]
    # ordem fixa das cores: rotatividade, saída em 90 dias, absenteísmo
    assert [b.name for b in barras] == ["Rotatividade 12 meses", "Saída em 90 dias", "Absenteísmo 6 meses"]
    for i, grupo in enumerate(texto.y):
        partes = [b.x[list(b.y).index(grupo)] for b in barras]
        assert all(p == p for p in partes), "nenhuma parte vazia: componente fora da conta é desenhado como 0"
        assert abs(sum(partes) - texto.x[i]) < 1e-9, grupo


def test_relatorio_publicado_usa_plotly_por_cdn_e_nao_embute_a_biblioteca():
    pagina = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<script[^>]+src="https://cdn\.plot\.ly/plotly-[\d.]+\.min\.js"', pagina)
    assert len(pagina) < 1_000_000  # com a biblioteca embutida, o arquivo passava de 4 MB
    assert pagina.count("cdn.plot.ly") == 1
