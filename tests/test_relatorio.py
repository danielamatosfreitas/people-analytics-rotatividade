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


def test_relatorio_publicado_usa_plotly_por_cdn_e_nao_embute_a_biblioteca():
    pagina = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<script[^>]+src="https://cdn\.plot\.ly/plotly-[\d.]+\.min\.js"', pagina)
    assert len(pagina) < 1_000_000  # com a biblioteca embutida, o arquivo passava de 4 MB
    assert pagina.count("cdn.plot.ly") == 1
