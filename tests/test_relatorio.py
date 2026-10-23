"""Testes da regra de base pequena no texto do relatório."""

import re
from pathlib import Path

from analise import relatorio as r

RAIZ = Path(__file__).resolve().parents[1]


def test_percentual_sempre_com_numero_absoluto():
    assert r.fracao(2, 8) == "25% (2 de 8)"
    assert r.falta_txt(13, 260, 10) == "5,0% (13 faltas em 260 dias previstos)"


def test_grupo_com_menos_de_5_nao_recebe_percentual():
    assert r.fracao(2, 4) == "sem percentual"
    assert r.fracao(0, 0) == "sem percentual"
    assert r.taxa_ano(0.5, 2, 4.0, 4) == "sem percentual"
    assert r.falta_txt(3, 60, 4) == "sem percentual"


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


def test_frase_do_asterisco_cita_exatamente_as_equipes_que_escapam_da_marcacao():
    import re as _re
    from analise import metricas as m
    premissas = m.carregar_premissas(RAIZ / "config" / "premissas.toml")
    pessoas, faltas = m.carregar_dados(RAIZ / "dados")
    meses = m.meses_do_periodo(premissas["periodo"]["inicio"], premissas["periodo"]["meses"])
    base_minima, base_pequena = premissas["relatorio"]["base_minima"], premissas["relatorio"]["base_pequena"]
    indice = m.indice_risco(m.fatores_por_grupo(pessoas, faltas, meses, ["unidade", "area", "lider"]), premissas["indice"], base_minima)
    r.BASE_MINIMA, r.BASE_PEQUENA = base_minima, base_pequena
    frase, fortes = r.frase_asterisco(indice)
    # conta independente: com índice e base de 10 ou mais pessoas e de 10 ou mais admissões
    esperado = sorted(indice[(indice["pessoas_12m"] >= base_pequena) & (indice["admitidos_90_dias"] >= base_pequena)
                             & ~indice["base_insuficiente"]]["lider"])
    assert fortes == esperado
    assert sorted(_re.findall(r"L\d\d", frase)) == esperado
    # e é essa a frase publicada abaixo do gráfico
    assert frase in (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")


def test_relatorio_sem_plural_entre_parenteses():
    # o HTML guarda os textos dos gráficos com acentos escapados (\u00ea); decodifica antes de procurar
    pagina = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
    texto = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), pagina)
    assert "(es)" not in texto
    assert "(s)" not in texto
    assert r.meses_antes_txt(1) == "1 mês antes da saída" and r.meses_antes_txt(12) == "12 meses antes da saída"
    assert r.saidas_txt(1) == "1 saída" and r.saidas_txt(3) == "3 saídas"


def test_etiquetas_de_previa_no_head_com_imagem_em_endereco_absoluto():
    pagina = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
    head = pagina.split("</head>")[0]
    esperado = {
        "og:title": "Rotatividade em uma rede de lojas",
        "og:description": "People Analytics com dados fictícios: onde e quando as pessoas saem, saídas na experiência, "
                          "faltas, custo e índice explicável por área e líder.",
        "og:image": "https://danielamatosfreitas.github.io/people-analytics-rotatividade/capa.png",
        "og:image:width": "1200",
        "og:image:height": "630",
        "og:url": "https://danielamatosfreitas.github.io/people-analytics-rotatividade/",
        "og:type": "website",
        "og:locale": "pt_BR",
    }
    for prop, valor in esperado.items():
        achados = re.findall(rf'<meta property="{re.escape(prop)}" content="([^"]*)">', head)
        assert achados == [valor], prop
    assert '<meta name="twitter:card" content="summary_large_image">' in head
    # a imagem tem de estar no ar no mesmo endereço: docs/ vira a raiz do site, e o tamanho declarado é o real
    imagem = re.search(r'<meta property="og:image" content="([^"]+)">', head).group(1)
    assert imagem.startswith("https://") and imagem.endswith("/capa.png")
    capa = RAIZ / "docs" / "capa.png"
    assert capa.exists()
    cabecalho = capa.read_bytes()[:24]
    assert cabecalho[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(cabecalho[16:20], "big") == 1200 and int.from_bytes(cabecalho[20:24], "big") == 630
