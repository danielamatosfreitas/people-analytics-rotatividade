"""Monta o relatório em um único HTML estático. O plotly vem por CDN, para a página carregar rápido no celular."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from analise import metricas as m

LINKEDIN = "https://www.linkedin.com/in/danielamatosfreitas"
SITE = "https://capitalhumanointelligence.com"
ENDERECO = "https://danielamatosfreitas.github.io/people-analytics-rotatividade/"

# Prévia do link em redes sociais (Open Graph e Twitter); a capa sai de scripts/gerar_capa.py
PREVIA = {
    "og:title": "Rotatividade em uma rede de lojas",
    "og:description": ("People Analytics com dados fictícios: onde e quando as pessoas saem, saídas na experiência, "
                       "faltas, custo e índice explicável por área e líder."),
    "og:image": ENDERECO + "capa-2026-10.png",
    "og:image:width": "1200",
    "og:image:height": "630",
    "og:url": ENDERECO,
    "og:type": "website",
    "og:locale": "pt_BR",
}


def etiquetas_previa() -> str:
    linhas = [f'<meta property="{k}" content="{html.escape(v)}">' for k, v in PREVIA.items()]
    linhas.append('<meta name="twitter:card" content="summary_large_image">')
    return "\n".join(linhas)

# Limites de base; os valores vêm de config/premissas.toml ([relatorio]) quando o relatório é gerado
BASE_MINIMA = 5     # abaixo disto: sem percentual, sem índice ou componente fora da conta
BASE_PEQUENA = 10   # abaixo disto: o índice aparece com leitura cautelosa (marcado com *)
SEM_PERCENTUAL = "sem percentual"


def eh_base_pequena(r) -> bool:
    """Menos de BASE_PEQUENA pessoas no grupo, ou menos de BASE_PEQUENA admissões no componente dos 90 dias."""
    return bool(r["pessoas_12m"] < BASE_PEQUENA or r["admitidos_90_dias"] < BASE_PEQUENA)


def frase_asterisco(indice: pd.DataFrame) -> tuple[str, list[str]]:
    """Nota do gráfico do índice, calculada dos dados: quais líderes têm base de BASE_PEQUENA ou mais nos dois componentes."""
    com_indice = indice[~indice["base_insuficiente"]]
    fortes = [r["lider"] for _, r in com_indice.sort_values("lider").iterrows() if not eh_base_pequena(r)]
    inicio = f"* Base pequena: menos de {BASE_PEQUENA} pessoas ou de {BASE_PEQUENA} admissões no período."
    if not fortes:
        return f"{inicio} Nenhuma equipe tem base de {BASE_PEQUENA} ou mais nos dois componentes.", fortes
    verbo = "tem" if len(fortes) == 1 else "têm"
    return f"{inicio} Só {lista(fortes)} {verbo} base de {BASE_PEQUENA} ou mais nos dois componentes.", fortes

VERDE = "#2C4A3B"
VERDE_MEDIO = "#5F8A74"
CREME = "#F3EEE3"
DOURADO = "#D3AF63"
VERMELHO = "#B3261E"
CINZA = "#6B6B66"
TINTA = "#1F2A24"

MESES_PT = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
MESES_PT_LONGO = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
                  "setembro", "outubro", "novembro", "dezembro"]
UNIDADE_CURTA = {"Loja Centro": "Centro", "Loja Shopping": "Shopping", "Loja Bairro": "Bairro"}

CONFIG_PLOTLY = {"displayModeBar": False, "responsive": True}

# Em telas estreitas, letras um pouco menores; no gráfico do índice, cada rótulo de equipe quebra em duas linhas
# ("L03 · Estoque" e "Centro *") para as barras ganharem largura
SCRIPT_CELULAR = """<script>
if (window.innerWidth <= 600) {
  document.querySelectorAll('.js-plotly-plot').forEach(function (g) {
    Plotly.relayout(g, {'font.size': 10, 'legend.font.size': 11});
  });
  var gi = document.getElementById('g-indice');
  if (gi && gi.data && gi.data.length) {
    var rotulos = gi.data[0].y;
    var quebrados = rotulos.map(function (r) {
      var i = r.lastIndexOf(' · ');
      return i < 0 ? r : r.slice(0, i) + '<br>' + r.slice(i + 3);
    });
    Plotly.relayout(gi, {'yaxis.tickmode': 'array', 'yaxis.tickvals': rotulos, 'yaxis.ticktext': quebrados});
  }
}
</script>"""


# ---------------------------------------------------------------- formatação

def num(x: float, casas: int = 0) -> str:
    texto = f"{x:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, casas: int = 0) -> str:
    return f"{num(100 * x, casas)}%"


def reais(x: float) -> str:
    return f"R$ {num(x)}"


def reais_mil(x: float) -> str:
    return f"R$ {num(x / 1000, 0)} mil"


def vezes(x: float) -> str:
    return f"{num(x, 1)} {'vez' if round(x, 1) < 2 else 'vezes'}"


def fracao(parte: float, todo: float, casas: int = 0) -> str:
    """Percentual com o número absoluto ao lado, como 25% (2 de 8). Menos de 5 na base: sem percentual."""
    parte, todo = int(parte), int(todo)
    if todo < BASE_MINIMA:
        return SEM_PERCENTUAL
    return f"{pct(parte / todo, casas)} ({parte} de {todo})"


def taxa_ano(taxa: float, saidas: float, quadro: float, pessoas: float) -> str:
    """Rotatividade anual com as saídas e o quadro médio ao lado."""
    if pessoas < BASE_MINIMA:
        return SEM_PERCENTUAL
    s = int(saidas)
    return f"{pct(taxa)} ao ano ({s} {'saída' if s == 1 else 'saídas'}, quadro médio de {num(quadro, 1)})"


def taxa_mes(saidas: int, quadro: float) -> str:
    s = int(saidas)
    return f"{pct(s / quadro, 1) if quadro else '0%'} ({s} {'saída' if s == 1 else 'saídas'}, quadro médio de {num(quadro, 1)})"


def falta_txt(faltas: float, dias: float, pessoas: float) -> str:
    """Absenteísmo com as faltas e os dias previstos ao lado."""
    if pessoas < BASE_MINIMA or not dias:
        return SEM_PERCENTUAL
    return f"{pct(faltas / dias, 1)} ({num(faltas)} faltas em {num(dias)} dias previstos)"


def parte_txt(valor: float, total: float) -> str:
    """Parte de um valor em reais, com o valor ao lado."""
    return f"{pct(valor / total)} ({reais_mil(valor)} de {reais_mil(total)})"


def blocos(fato: str, interpretacao: str, hipotese: str) -> str:
    return (f'<div class="fih" lang="pt-BR"><div class="b fato" lang="pt-BR"><h3>Fato</h3>{fato}</div>'
            f'<div class="b interp" lang="pt-BR"><h3>Interpretação</h3>{interpretacao}</div>'
            f'<div class="b hipo" lang="pt-BR"><h3>Hipótese</h3>{hipotese}</div></div>')


def tabela_bruta(cabecalho: list[str], linhas: list[list[str]], legenda: str, aberta: bool = False) -> str:
    """Tabela cujas células já vêm em HTML montado aqui (com html.escape nos textos de dados)."""
    cab = "".join(f"<th>{html.escape(c)}</th>" for c in cabecalho)
    corpo = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in linha) + "</tr>" for linha in linhas)
    return (f'<details class="tabela"{" open" if aberta else ""}><summary>{html.escape(legenda)}</summary>'
            f'<div class="rolagem"><table><thead><tr>{cab}</tr></thead><tbody>{corpo}</tbody></table></div></details>')


def mes_curto(p: pd.Period) -> str:
    return f"{MESES_PT[p.month - 1]}/{str(p.year)[2:]}"


def mes_longo(p: pd.Period) -> str:
    return f"{MESES_PT_LONGO[p.month - 1]} de {p.year}"


def rotulo_equipe(linha) -> str:
    return f"{linha['lider']} · {linha['area']} · {UNIDADE_CURTA.get(linha['unidade'], linha['unidade'])}"


def lista(itens: list[str]) -> str:
    itens = list(itens)
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def tabela_html(df: pd.DataFrame, legenda: str) -> str:
    cab = "".join(f"<th>{html.escape(str(c))}</th>" for c in df.columns)
    linhas = "".join("<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in row) + "</tr>"
                     for row in df.itertuples(index=False))
    return (f'<details class="tabela"><summary>{html.escape(legenda)}</summary>'
            f'<div class="rolagem"><table><thead><tr>{cab}</tr></thead><tbody>{linhas}</tbody></table></div></details>')


# ---------------------------------------------------------------- gráficos

def estilo(fig: go.Figure, altura: int, titulo_y: str | None = None, titulo_x: str | None = None) -> go.Figure:
    fig.update_layout(
        height=altura,
        margin=dict(l=8, r=16, t=48, b=8),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Segoe UI, Roboto, Helvetica, Arial, sans-serif", size=13, color=TINTA),
        separators=",.",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="",
                    traceorder="normal"),
        hoverlabel=dict(bgcolor="#FFFFFF", font_color=TINTA, bordercolor=CINZA),
        bargap=0.3,
    )
    fig.update_xaxes(showgrid=False, linecolor="#C9C3B6", ticks="", title_text=titulo_x, automargin=True,
                     fixedrange=True)
    fig.update_yaxes(gridcolor="#ECE7DC", zeroline=False, linecolor="#C9C3B6", title_text=titulo_y,
                     automargin=True, fixedrange=True)
    return fig


def grafico_html(fig: go.Figure, div_id: str, carregar_plotly: bool = False) -> str:
    # O primeiro gráfico da página carrega o plotly pelo CDN; os outros usam o mesmo arquivo
    return fig.to_html(full_html=False, include_plotlyjs="cdn" if carregar_plotly else False,
                       config=CONFIG_PLOTLY, div_id=div_id)


def saidas_txt(n) -> str:
    """Singular e plural escritos por extenso: "1 saída", "3 saídas"."""
    n = int(n)
    return f"{n} {'saída' if n == 1 else 'saídas'}"


def meses_antes_txt(k) -> str:
    k = int(k)
    return f"{k} {'mês' if k == 1 else 'meses'} antes da saída"


def fig_mensal(mensal: pd.DataFrame) -> go.Figure:
    x = [mes_curto(p) for p in mensal["mes"]]
    fig = go.Figure()
    for col, nome, cor, qtd in [("taxa_pedido", "Pedido de demissão", VERDE, "saidas_pedido"),
                                ("taxa_empresa", "Desligamento pela empresa", DOURADO, "saidas_empresa")]:
        fig.add_bar(x=x, y=mensal[col], name=nome, marker_color=cor, marker_line_color="#FFFFFF",
                    marker_line_width=1, customdata=[[saidas_txt(s), q] for s, q in zip(mensal[qtd], mensal["quadro_medio"])],
                    hovertemplate="%{x}<br>" + nome + ": %{customdata[0]}<br>"
                                  "%{y:.1%} do quadro médio (%{customdata[1]:.1f} pessoas)<extra></extra>")
    media = mensal["taxa"].mean()
    fig.add_hline(y=media, line_dash="dot", line_color=CINZA, line_width=1.5,
                  annotation_text=f"média: {num(mensal['saidas'].mean(), 1)} saídas por mês ({pct(media, 1)} do quadro)", annotation_position="top left",
                  annotation_font_color=CINZA, annotation_font_size=12)
    fig.update_layout(barmode="stack")
    estilo(fig, 380, "Saídas no mês / quadro médio")
    fig.update_yaxes(tickformat=".0%")
    fig.update_xaxes(tickangle=-45)
    return fig


def fig_equipes_taxa(anual: pd.DataFrame, rede: float, saidas_rede: int) -> go.Figure:
    df = anual.sort_values("taxa_anual")
    y = [rotulo_equipe(r) for _, r in df.iterrows()]
    fig = go.Figure()
    for col, nome, cor, qtd in [("taxa_anual_pedido", "Pedido de demissão", VERDE, "saidas_pedido"),
                                ("taxa_anual_empresa", "Desligamento pela empresa", DOURADO, "saidas_empresa")]:
        fig.add_bar(y=y, x=df[col], orientation="h", name=nome, marker_color=cor, marker_line_color="#FFFFFF",
                    marker_line_width=1, customdata=[[saidas_txt(s), q] for s, q in zip(df[qtd], df["quadro_medio"])],
                    hovertemplate="%{y}<br>" + nome + ": %{customdata[0]} em 24 meses<br>"
                                  "%{x:.0%} ao ano (quadro médio %{customdata[1]:.1f})<extra></extra>")
    fig.add_vline(x=rede, line_dash="dot", line_color=CINZA, line_width=1.5,
                  annotation_text=f"rede: {pct(rede)} ao ano ({saidas_rede} saídas)", annotation_position="top",
                  annotation_font_color=CINZA, annotation_font_size=12)
    fig.update_layout(barmode="stack")
    estilo(fig, 440, None, "Saídas por ano / quadro médio")
    fig.update_xaxes(tickformat=".0%", showgrid=True, gridcolor="#ECE7DC")
    return fig


def fig_90_dias(df: pd.DataFrame, rotulo: str, rede: float, limite_alerta: float, rede_txt: str = "") -> go.Figure:
    # grupos com menos admitidos que a base mínima não viram barra (ficam na tabela sem percentual)
    df = df[df["admitidos"] >= BASE_MINIMA].sort_values("taxa_90_dias")
    cores = [VERMELHO if t >= limite_alerta else VERDE for t in df["taxa_90_dias"]]
    texto = [fracao(s, a) for s, a in zip(df["sairam_90_dias"], df["admitidos"])]
    fig = go.Figure(go.Bar(
        y=df[rotulo], x=df["taxa_90_dias"], orientation="h", marker_color=cores, text=texto,
        textposition="outside", cliponaxis=False, textfont=dict(color=TINTA),
        hovertemplate="%{y}<br>%{text} saíram antes de 90 dias<extra></extra>"))
    fig.add_vline(x=rede, line_dash="dot", line_color=CINZA, line_width=1.5,
                  annotation_text=f"rede: {rede_txt or pct(rede)}", annotation_position="top",
                  annotation_font_color=CINZA, annotation_font_size=12)
    estilo(fig, 90 + 36 * len(df), None, "Admitidos que saíram antes de 90 dias")
    fig.update_xaxes(tickformat=".0%", range=[0, min(1.0, max(0.5, df["taxa_90_dias"].max() * 1.5))],
                     showgrid=True, gridcolor="#ECE7DC")
    fig.update_layout(showlegend=False, margin=dict(l=8, r=16, t=36, b=8))
    return fig


def fig_faltas(curva: pd.DataFrame, ficou: float) -> go.Figure:
    c = curva.sort_values("meses_antes", ascending=False)
    x = [f"{k}" for k in c["meses_antes"]]
    fig = go.Figure()
    posicao = {k: i for i, k in enumerate(x)}
    fig.add_vrect(x0=posicao["3"] - 0.5, x1=posicao["1"] + 0.5, fillcolor=DOURADO, opacity=0.18, line_width=0, layer="below",
                  annotation_text="3 meses antes", annotation_position="top left",
                  annotation_font_color=TINTA, annotation_font_size=12)
    fig.add_scatter(x=x, y=c["absenteismo"], mode="lines+markers", name="Quem saiu",
                    line=dict(color=VERDE, width=2), marker=dict(size=8, color=VERDE),
                    customdata=[[p, f, d, meses_antes_txt(k)] for p, f, d, k
                                in zip(c["pessoas"], c["faltas"], c["dias_previstos"], c["meses_antes"])],
                    hovertemplate="%{customdata[3]}<br>Base do ponto: %{customdata[0]} pessoas que saíram<br>"
                                  "Absenteísmo %{y:.1%} (%{customdata[1]} faltas em %{customdata[2]} dias previstos)"
                                  "<extra></extra>")
    fig.add_scatter(x=[x[0], x[-1]], y=[ficou, ficou], mode="lines", name="Quem ficou (mesmos meses)",
                    line=dict(color=CINZA, width=2, dash="dash"), hoverinfo="skip")
    estilo(fig, 380, "Dias de falta / dias previstos", "Meses antes da saída")
    fig.update_yaxes(tickformat=".1%", rangemode="tozero")
    fig.update_xaxes(type="category")
    return fig


def fig_custo_area(custos: pd.DataFrame) -> go.Figure:
    df = custos.groupby("area")[["rescisao", "reposicao", "rampa", "total"]].sum().reset_index()
    df["saidas"] = custos.groupby("area").size().reindex(df["area"]).values
    df = df.sort_values("total")
    fig = go.Figure()
    for col, nome, cor in [("rescisao", "Rescisão", VERDE), ("reposicao", "Reposição", DOURADO),
                           ("rampa", "Tempo até render", VERDE_MEDIO)]:
        fig.add_bar(y=df["area"], x=df[col], orientation="h", name=nome, marker_color=cor,
                    marker_line_color="#FFFFFF", marker_line_width=1, customdata=[saidas_txt(s) for s in df["saidas"]],
                    hovertemplate="%{y}<br>" + nome + ": R$ %{x:,.0f}<br>%{customdata}<extra></extra>")
    fig.update_layout(barmode="stack")
    estilo(fig, 300, None, "Custo em 24 meses (R$)")
    fig.update_xaxes(tickformat=",.0f", showgrid=True, gridcolor="#ECE7DC")
    return fig


def fig_indice(indice: pd.DataFrame, rotulos: list[str]) -> go.Figure:
    # só grupos com base suficiente; cada barra é a soma das contribuições (peso x componente)
    manter = ~indice["base_insuficiente"].values
    df = indice[manter].iloc[::-1]
    y = [r for r, ok in zip(rotulos, manter) if ok][::-1]
    fig = go.Figure()
    # Ordem fixa das cores em todas as linhas: rotatividade, saída em 90 dias, absenteísmo.
    # Componente fora da conta entra como 0 só no desenho (o cálculo do índice não muda); com valor vazio,
    # o plotly deixa de empilhar a barra e o fim dela deixa de bater com o índice.
    for comp, nome, cor in [("rotatividade_12m", "Rotatividade 12 meses", VERDE),
                            ("saida_90_dias", "Saída em 90 dias", DOURADO),
                            ("absenteismo_6m", "Absenteísmo 6 meses", VERDE_MEDIO)]:
        situacao = [(f"fora da conta: {int(n)} admissões" if comp == "saida_90_dias" else "fora da conta") if pd.isna(c)
                    else f"componente {num(c, 2)}" for c, n in zip(df[f"comp_{comp}"], df["admitidos_90_dias"])]
        fig.add_bar(y=y, x=df[f"contrib_{comp}"].fillna(0.0), orientation="h", name=nome, marker_color=cor,
                    marker_line_color="#FFFFFF", marker_line_width=1, customdata=situacao,
                    hovertemplate="%{y}<br>" + nome + ": contribuição %{x:.2f}<br>%{customdata}<extra></extra>")
    fig.add_scatter(y=y, x=df["indice"], mode="text", text=[num(v, 2) for v in df["indice"]],
                    textposition="middle right", textfont=dict(color=TINTA, size=13), showlegend=False,
                    hoverinfo="skip")
    fig.update_layout(barmode="stack")
    estilo(fig, 90 + 36 * len(df), None, "Índice (0 a 1)")
    fig.update_xaxes(range=[0, 1.0], showgrid=True, gridcolor="#ECE7DC", tickformat=".1f")
    return fig


# ---------------------------------------------------------------- relatório

def gerar(raiz: Path) -> Path:
    global BASE_MINIMA, BASE_PEQUENA
    premissas = m.carregar_premissas(raiz / "config" / "premissas.toml")
    BASE_MINIMA = int(premissas["relatorio"]["base_minima"])
    BASE_PEQUENA = base_pequena = int(premissas["relatorio"]["base_pequena"])
    pessoas, faltas = m.carregar_dados(raiz / "dados")
    meses = m.meses_do_periodo(premissas["periodo"]["inicio"], premissas["periodo"]["meses"])
    inicio, fim = meses[0].start_time.normalize(), meses[-1].end_time.normalize()
    equipe = ["unidade", "area", "lider"]
    salarios = premissas["salario_por_cargo"]
    g = premissas["geracao"]

    # ------------------------------------------------------------ 1. Onde e quando
    mensal = m.rotatividade_mensal(pessoas, meses)
    total = m.rotatividade_anualizada(mensal).iloc[0]
    rot_12m = m.rotatividade_anualizada(mensal[mensal["mes"].isin(meses[-12:])]).iloc[0]
    n_pessoas = int(m.pessoas_no_periodo(pessoas, inicio, fim).iloc[0]["pessoas"])

    def anual(por):
        a = m.rotatividade_anualizada(m.rotatividade_mensal(pessoas, meses, por), por)
        return a.merge(m.pessoas_no_periodo(pessoas, inicio, fim, por), on=por)

    anual_eq, anual_area, anual_unid = anual(equipe), anual(["area"]), anual(["unidade"])
    saidas = int(total["saidas"])
    n_pedido, n_empresa = int(total["saidas_pedido"]), int(total["saidas_empresa"])
    picos = mensal.sort_values(["saidas", "mes"], ascending=[False, True]).head(2)
    # Hipótese da sazonalidade: meses com mais saídas no gerador (fator acima de 1) contra os meses comuns (sem fator)
    saz = {int(k): v for k, v in premissas["geracao"]["sazonalidade"].items()}
    meses_altos_txt = lista([MESES_PT_LONGO[k - 1] for k in sorted(saz) if saz[k] > 1])
    comp = m.comparacao_sazonalidade(mensal, saz)
    saidas_altos, n_altos, media_altos = comp["saidas_altos"], comp["n_altos"], comp["media_altos"]
    saidas_comuns, n_comuns, media_comuns = comp["saidas_comuns"], comp["n_comuns"], comp["media_comuns"]
    sazonalidade_confirmada = media_altos > media_comuns
    # Poder do método (scripts/poder_sazonalidade.py): em quantos sorteios do gerador o padrão aparece
    poder = json.loads((raiz / "dados" / "poder_sazonalidade.json").read_text(encoding="utf-8"))
    n_sorteios, x_sorteios = poder["sorteios"], poder["sorteios_com_meses_altos_acima"]
    poder_fato = (f"Rodando o gerador com {n_sorteios} sementes, a sazonalidade plantada aparece em {x_sorteios} de "
                  f"{n_sorteios} sorteios ({meses_altos_txt} com mais saídas por mês do que os meses comuns).")
    poder_interp = (f"Em linguagem simples: o efeito existe no gerador, porém um único sorteio de "
                    f"{premissas['periodo']['meses']} meses numa rede deste tamanho pode não mostrá-lo. "
                    + (f"O sorteio deste relatório ({num(media_altos, 2)} contra {num(media_comuns, 2)} saídas por mês) "
                       f"é um dos casos em que ele não aparece." if not sazonalidade_confirmada else
                       "No sorteio deste relatório ele aparece."))
    area_ord = anual_area.sort_values("taxa_anual", ascending=False)
    unid_ord = anual_unid.sort_values("taxa_anual", ascending=False)
    area_top = area_ord.iloc[0]

    def lista_taxas(df, chave):
        return lista([f"{r[chave]}, {taxa_ano(r['taxa_anual'], r['saidas'], r['quadro_medio'], r['pessoas'])}"
                      for _, r in df.iterrows()])

    def lista_tipos(df, chave):
        return lista([f"{r[chave]}, {fracao(r['saidas_pedido'], r['saidas'])} por pedido" if r["saidas"] >= BASE_MINIMA
                      else f"{r[chave]}, {SEM_PERCENTUAL}" for _, r in df.iterrows()])

    # ------------------------------------------------------------ 2. Primeiros 90 dias
    s90_rede = m.saida_90_dias(pessoas, inicio, fim).iloc[0]
    s90_area = m.saida_90_dias(pessoas, inicio, fim, ["area"])
    s90_eq = m.saida_90_dias(pessoas, inicio, fim, equipe)
    s90_eq["rotulo"] = [rotulo_equipe(r) for _, r in s90_eq.iterrows()]
    limite_alerta = 1.3 * s90_rede["taxa_90_dias"]
    s90_area_ok = s90_area[s90_area["admitidos"] >= BASE_MINIMA]
    a90_top = s90_area_ok.sort_values("taxa_90_dias", ascending=False).iloc[0]
    outras = s90_area[s90_area["area"] != a90_top["area"]]
    eq_area_top = s90_eq[(s90_eq["area"] == a90_top["area"]) & (s90_eq["admitidos"] >= BASE_MINIMA)]
    acima_rede = int((eq_area_top["taxa_90_dias"] > s90_rede["taxa_90_dias"]).sum())
    saidas_periodo = pessoas[pessoas["data_desligamento"].between(inicio, fim)]
    casa = (saidas_periodo["data_desligamento"] - saidas_periodo["data_admissao"]).dt.days
    n_saidas_90 = int((casa < 90).sum())
    n_saidas_90_area = int(((casa < 90) & (saidas_periodo["area"] == a90_top["area"])).sum())
    eq_pequenas_90 = s90_eq[s90_eq["admitidos"] < BASE_MINIMA]["rotulo"].tolist()
    areas_pequenas_90 = s90_area[s90_area["admitidos"] < BASE_MINIMA]["area"].tolist()

    # ------------------------------------------------------------ 3. Faltas antes da saída
    fa = m.faltas_antes_da_saida(pessoas, faltas, meses)
    sd, fd = fa["saiu_detalhe"], fa["ficou_detalhe"]
    tp, te = fa["por_tipo"][m.PEDIDO], fa["por_tipo"][m.EMPRESA]
    curva = fa["curva"]
    antes = curva[curva["meses_antes"].between(4, 12)]
    abs_lider = (m.absenteismo(faltas, pessoas, equipe).merge(m.pessoas_no_periodo(pessoas, inicio, fim, equipe), on=equipe)
                 .sort_values("absenteismo", ascending=False))
    lider_abs = abs_lider.iloc[0]
    pessoas_lider_abs = int(lider_abs["pessoas"])
    resto = faltas[~faltas["id"].isin(pessoas.loc[pessoas["lider"] == lider_abs["lider"], "id"])]
    resto_abs = m.absenteismo(resto).iloc[0]

    # ------------------------------------------------------------ 4. Custo
    pc = premissas["custo"]
    custos = m.custo_rotatividade(pessoas, m.cenario_custo(pc, "medio"), salarios, inicio, fim)
    sens = m.sensibilidade_custo(pessoas, pc, salarios, inicio, fim).set_index("cenario")
    custo_total = float(custos["total"].sum())
    custo_medio = float(custos["total"].mean())
    partes = custos[["rescisao", "reposicao", "rampa"]].sum().sort_values(ascending=False)
    custo_90 = float(custos[(custos["data_desligamento"] - custos["data_admissao"]).dt.days < 90]["total"].sum())
    por_area_custo = custos.groupby("area")["total"].sum().sort_values(ascending=False)
    nomes_partes = {"rampa": "tempo até a pessoa nova render", "reposicao": "reposição", "rescisao": "rescisão"}

    # ------------------------------------------------------------ 5. Índice
    pi = premissas["indice"]
    indice_eq = m.indice_risco(m.fatores_por_grupo(pessoas, faltas, meses, equipe), pi, BASE_MINIMA)
    indice_area = m.indice_risco(m.fatores_por_grupo(pessoas, faltas, meses, ["area"]), pi, BASE_MINIMA)
    rotulos_indice = [rotulo_equipe(r) + (" *" if eh_base_pequena(r) else "") for _, r in indice_eq.iterrows()]
    nota_asterisco, _ = frase_asterisco(indice_eq)
    nomes_comp = {"rotatividade_12m": "rotatividade dos últimos 12 meses", "saida_90_dias": "saída nos primeiros 90 dias",
                  "absenteismo_6m": "absenteísmo dos últimos 6 meses"}
    nomes_comp_curto = {"rotatividade_12m": "Rotatividade", "saida_90_dias": "Saída em 90 dias", "absenteismo_6m": "Absenteísmo"}

    def maior_contrib(linha):
        return max(m.COMPONENTES, key=lambda c: -1 if pd.isna(linha[f"contrib_{c}"]) else linha[f"contrib_{c}"])

    def valor_comp(linha, comp):
        if comp == "rotatividade_12m":
            return taxa_ano(linha["rotatividade_12m"], linha["saidas_12m"], linha["quadro_medio_12m"], linha["pessoas_12m"])
        if comp == "saida_90_dias":
            return fracao(linha["sairam_90_dias"], linha["admitidos_90_dias"])
        return falta_txt(linha["faltas_6m"], linha["dias_previstos_6m"], linha["pessoas_12m"])

    def fora_txt(linha, comp):
        return f"fora da conta: {int(linha['admitidos_90_dias'])} admissões" if comp == "saida_90_dias" else "fora da conta"

    def conta_comp(linha, comp):
        """Texto da conta de um componente; componente sem base fica fora da conta, sem valor imputado."""
        if pd.isna(linha[f"contrib_{comp}"]):
            return fora_txt(linha, comp)
        return (f"componente {num(linha[f'comp_{comp}'], 2)} × peso {num(linha[f'peso_{comp}'], 2)} "
                f"= {num(linha[f'contrib_{comp}'], 2)}")

    def tabela_indice(df, chave, legenda, aberta=False):
        """No computador, cada célula traz o valor e a conta. Até 600 px, só as contribuições e o índice;
        a conta completa fica numa linha expansível logo abaixo do grupo."""
        # cabeçalho completo no computador e curto até 600 px
        cab = [("Grupo", "Grupo"), ("Pessoas (12 meses)", "Pessoas"), ("Rotatividade 12 meses", "Rotatividade"),
               ("Saída em 90 dias", "90 dias"), ("Absenteísmo 6 meses", "Faltas"), ("Índice", "Índice")]
        corpo = []
        for _, r in df.iterrows():
            rot = html.escape(rotulo_equipe(r) if chave == "equipe" else r["area"])
            if r["base_insuficiente"]:
                corpo.append(f"<tr><td>{rot}</td><td>{num(r['pessoas_12m'])}</td>" + "<td></td>" * 3 + "<td>sem índice</td></tr>")
                continue
            grupo = rot + ('<br><span class="marca base-pequena">base pequena</span>' if eh_base_pequena(r) else "")
            celulas = []
            for comp in m.COMPONENTES:
                fora = pd.isna(r[f"contrib_{comp}"])
                curto = "fora" if fora else num(r[f"contrib_{comp}"], 2)
                completo = (fora_txt(r, comp) if fora
                            else f'{html.escape(valor_comp(r, comp))}<br><span class="conta">{conta_comp(r, comp)}</span>')
                celulas.append(f'<td><span class="cel-completa">{completo}</span><span class="cel-curta">{curto}</span></td>')
            n_comp = int(r["componentes_usados"])
            marca = ("" if n_comp == len(m.COMPONENTES)
                     else f'<br><span class="marca"><span class="cel-completa">índice com {n_comp} de {len(m.COMPONENTES)} componentes</span>'
                          f'<span class="cel-curta">{n_comp} de {len(m.COMPONENTES)}</span></span>')
            idx = f"<strong>{num(r['indice'], 2)}</strong>{marca}"
            corpo.append(f"<tr><td>{grupo}</td><td>{num(r['pessoas_12m'])}</td>{''.join(celulas)}<td>{idx}</td></tr>")
            detalhe = "".join(f"<li><strong>{nomes_comp_curto[c]}:</strong> "
                              + (f"{fora_txt(r, c)}.</li>" if pd.isna(r[f"contrib_{c}"])
                                 else f"{html.escape(valor_comp(r, c))}; {conta_comp(r, c)}.</li>")
                              for c in m.COMPONENTES)
            corpo.append(f'<tr class="linha-conta"><td colspan="6"><details><summary>Ver a conta de {rot}</summary>'
                         f'<ul>{detalhe}</ul></details></td></tr>')
        cabecalho = "".join(f'<th><span class="cel-completa">{html.escape(longo)}</span><span class="cel-curta">{html.escape(curto)}</span></th>'
                            for longo, curto in cab)
        return (f'<details class="tabela"{" open" if aberta else ""}><summary>{html.escape(legenda)}</summary>'
                f'<div class="rolagem"><table class="tab-indice"><thead><tr>{cabecalho}</tr></thead>'
                f'<tbody>{"".join(corpo)}</tbody></table></div></details>')

    eq_ok = indice_eq[~indice_eq["base_insuficiente"]]
    top3 = eq_ok.head(3)
    area_ok = indice_area[~indice_area["base_insuficiente"]]
    sem_indice = indice_eq[indice_eq["base_insuficiente"]]
    parciais = eq_ok[eq_ok["componentes_usados"] < len(m.COMPONENTES)]

    # Exemplo de base pequena: a equipe do topo do ranking com menos de base_pequena admissões, e o que uma saída a menos faria
    exemplo_txt = ""
    for pos, (idx_linha, r) in reversed(list(enumerate(eq_ok.head(3).iterrows(), 1))):
        if (r["componentes_usados"] == len(m.COMPONENTES) and r["admitidos_90_dias"] < base_pequena
                and r["sairam_90_dias"] > 0):
            novo_comp = min((r["sairam_90_dias"] - 1) / r["admitidos_90_dias"] / pi["referencia_saida_90_dias"], 1.0)
            novo = r["indice"] - r["peso_saida_90_dias"] * (r["comp_saida_90_dias"] - novo_comp)
            nova_pos = 1 + int((eq_ok.drop(index=idx_linha)["indice"] > novo).sum())
            exemplo_txt = (f"Exemplo da base: {html.escape(rotulo_equipe(r))} está em {pos}º lugar com "
                           f"{int(r['sairam_90_dias'])} saídas em {int(r['admitidos_90_dias'])} admissões nos primeiros 90 dias. "
                           f"Com uma saída a menos, o componente dos 90 dias cairia de {num(r['comp_saida_90_dias'], 2)} para "
                           f"{num(novo_comp, 2)}, o índice de {num(r['indice'], 2)} para {num(novo, 2)}, e a equipe passaria "
                           f"para o {nova_pos}º lugar.")
            break

    # ------------------------------------------------------------ tabelas
    tab_mensal = tabela_bruta(
        ["Mês", "Admissões", "Pedidos de demissão", "Desligamentos pela empresa", "Quadro no fim do mês", "Saídas no mês"],
        [[mes_curto(r["mes"]), num(r["admissoes"]), num(r["saidas_pedido"]), num(r["saidas_empresa"]),
          num(r["quadro_fim_mes"]), taxa_mes(r["saidas"], r["quadro_medio"])] for _, r in mensal.iterrows()],
        "Ver os números de cada mês")

    def tabela_grupos(df, chave, titulo, legenda):
        df = df.sort_values("taxa_anual", ascending=False)
        linhas = []
        for _, r in df.iterrows():
            rot = rotulo_equipe(r) if chave == "equipe" else r[chave]
            linhas.append([html.escape(rot), num(r["pessoas"]), num(r["saidas_pedido"]), num(r["saidas_empresa"]),
                           html.escape(fracao(r["saidas_pedido"], r["saidas"])),
                           html.escape(taxa_ano(r["taxa_anual"], r["saidas"], r["quadro_medio"], r["pessoas"]))])
        return tabela_bruta([titulo, "Pessoas no período", "Pedido de demissão", "Desligamento pela empresa", "Parte por pedido", "Rotatividade"],
                            linhas, legenda)

    tab_unid = tabela_grupos(anual_unid, "unidade", "Unidade", "Ver por unidade")
    tab_area = tabela_grupos(anual_area, "area", "Área", "Ver por área")
    tab_eq = tabela_grupos(anual_eq, "equipe", "Equipe", "Ver por equipe (líder)")
    tab_90 = tabela_bruta(
        ["Equipe", "Admitidos no período", "Saíram antes de 90 dias", "Taxa"],
        [[html.escape(r["rotulo"]), num(r["admitidos"]), num(r["sairam_90_dias"]),
          html.escape(fracao(r["sairam_90_dias"], r["admitidos"]))]
         for _, r in s90_eq.sort_values("taxa_90_dias", ascending=False).iterrows()],
        "Ver os números de cada equipe")
    tab_faltas = tabela_bruta(
        ["Meses antes da saída", "Quem saiu: pessoas no ponto", "Faltas", "Dias previstos", "Absenteísmo"],
        [[num(r["meses_antes"]), num(r["pessoas"]), num(r["faltas"]), num(r["dias_previstos"]),
          html.escape(falta_txt(r["faltas"], r["dias_previstos"], r["pessoas"]))]
         for _, r in curva.sort_values("meses_antes", ascending=False).iterrows()],
        "Ver os números de cada mês antes da saída")
    tab_abs_lider = tabela_bruta(
        ["Equipe", "Absenteísmo em 24 meses"],
        [[html.escape(rotulo_equipe(r)), html.escape(falta_txt(r["faltas"], r["dias_previstos"], r["pessoas"]))]
         for _, r in abs_lider.iterrows()],
        "Ver o absenteísmo de cada equipe")
    ca = custos.groupby("area")[["rescisao", "reposicao", "rampa", "total"]].sum().sort_values("total", ascending=False)
    tab_custo = tabela_bruta(
        ["Área", "Saídas", "Rescisão", "Reposição", "Tempo até render", "Total"],
        [[html.escape(a), num(custos[custos["area"] == a].shape[0]), reais(r["rescisao"]), reais(r["reposicao"]),
          reais(r["rampa"]), reais(r["total"])] for a, r in ca.iterrows()],
        "Ver o custo de cada área (cenário médio)")
    nomes_cenario = {"baixo": "Baixo", "medio": "Médio", "alto": "Alto"}
    tab_sens = tabela_bruta(
        ["Cenário", "Custo em 24 meses", "Por saída", "Rescisão", "Reposição", "Tempo até render"],
        [[nomes_cenario[c], reais(r["total"]), reais(r["por_saida"]), reais(r["rescisao"]), reais(r["reposicao"]),
          reais(r["rampa"])] for c, r in sens.iterrows()],
        "Análise de sensibilidade: três cenários", aberta=True)

    def valor_cenario(chave, formato):
        return " / ".join(formato(m.cenario_custo(pc, c)[chave]) for c in ("baixo", "medio", "alto"))

    prod = lambda lst: ", ".join(num(p, 2) for p in lst) + f" ({len(lst)} {'mês' if len(lst) == 1 else 'meses'})"
    linhas_premissas = [
        ["Encargos e provisões, por real de salário", valor_cenario("encargos_sobre_salario", lambda v: num(v, 2)),
         "Referência para Lucro Presumido; no Simples Nacional costuma ser menor."],
        ["Recrutamento", valor_cenario("custo_recrutamento", reais), "Anúncios, triagem e horas de entrevista."],
        ["Admissão", valor_cenario("custo_admissao", reais), "Exame admissional, uniforme e cadastro."],
        ["Treinamento inicial", valor_cenario("custo_treinamento", reais), "Horas de quem treina e material de integração."],
        ["Produtividade da pessoa nova, mês a mês (1 = rende como quem já estava)", valor_cenario("produtividade_mes", prod),
         "O que falta para 1 é custo: salário com encargos sem retorno em produção."],
        ["Aviso prévio indenizado", f"{pc['aviso_previo_dias_base']} dias + {pc['aviso_previo_dias_por_ano']} por ano de casa, até {pc['aviso_previo_dias_maximo']}",
         "Igual nos três cenários. Só quando a empresa desliga depois da experiência."],
        ["Multa do FGTS", f"{num(pc['multa_fgts'], 2)} do saldo (depósito de {num(pc['deposito_fgts_mensal'], 2)} do salário ao mês)",
         "Igual nos três cenários. Só quando a empresa desliga depois da experiência."],
        ["Saída na experiência", f"{pc['dias_experiencia']} dias, sem aviso nem multa", "Supõe término no prazo do contrato."],
        ["Custo administrativo do desligamento", reais(pc["custo_administrativo_desligamento"]), "Exame demissional e horas do RH."],
        ["Férias e 13º proporcionais", "não entram", "Seriam pagos de qualquer forma."],
    ]
    tab_premissas = tabela_bruta(["Premissa", "Baixo / Médio / Alto", "Observação"],
                                 [[html.escape(a), html.escape(b), html.escape(c)] for a, b, c in linhas_premissas],
                                 "Premissas do custo (valores fictícios)", aberta=True)
    tab_salarios = tabela_bruta(["Cargo", "Salário mensal usado no custo"],
                                [[html.escape(c), reais(v)] for c, v in salarios.items()],
                                "Salário por cargo (fictício)")
    tab_pesos = tabela_bruta(
        ["Componente", "Peso", "Referência que vale 1", "Como é medido"],
        [["Rotatividade dos últimos 12 meses", num(pi["peso_rotatividade_12m"], 2), num(pi["referencia_rotatividade_12m"], 2) + " saída por pessoa do quadro médio, ao ano",
          "Saídas sobre o quadro médio, ajustadas para 12 meses."],
         ["Saída nos primeiros 90 dias", num(pi["peso_saida_90_dias"], 2), num(pi["referencia_saida_90_dias"], 2) + " dos admitidos",
          "Admitidos nos 24 meses que saíram antes de 90 dias."],
         ["Absenteísmo dos últimos 6 meses", num(pi["peso_absenteismo_6m"], 2), num(pi["referencia_absenteismo_6m"], 2) + " dos dias previstos",
          "Dias de falta sobre dias de trabalho previstos."]],
        "Pesos e referências do índice", aberta=True)
    tab_indice_eq = tabela_indice(indice_eq, "equipe", "Índice por líder: cada componente e sua contribuição", aberta=True)
    tab_indice_area = tabela_indice(indice_area, "area", "Índice por área: cada componente e sua contribuição")

    # ------------------------------------------------------------ gráficos
    g_mensal = grafico_html(fig_mensal(mensal), "g-mensal", carregar_plotly=True)
    g_equipes = grafico_html(fig_equipes_taxa(anual_eq, total["taxa_anual"], saidas), "g-equipes")
    g_90_area = grafico_html(fig_90_dias(s90_area, "area", s90_rede["taxa_90_dias"], limite_alerta, fracao(s90_rede["sairam_90_dias"], s90_rede["admitidos"])), "g-90-area")
    g_90_eq = grafico_html(fig_90_dias(s90_eq, "rotulo", s90_rede["taxa_90_dias"], limite_alerta, fracao(s90_rede["sairam_90_dias"], s90_rede["admitidos"])), "g-90-lider")
    g_faltas = grafico_html(fig_faltas(curva, fa["ficou"]), "g-faltas")
    g_custo = grafico_html(fig_custo_area(custos), "g-custo")
    g_indice = grafico_html(fig_indice(indice_eq, rotulos_indice), "g-indice")

    # ------------------------------------------------------------ textos das perguntas
    p1_fato = f"""<ul>
    <li>{fracao(n_pedido, saidas)} das saídas foram pedidos de demissão.</li>
    <li>{area_top['area']} tem a maior rotatividade entre as áreas: {taxa_ano(area_top['taxa_anual'], area_top['saidas'], area_top['quadro_medio'], area_top['pessoas'])}.</li>
    <li>{unid_ord.iloc[0]['unidade']} tem a maior entre as unidades: {taxa_ano(unid_ord.iloc[0]['taxa_anual'], unid_ord.iloc[0]['saidas'], unid_ord.iloc[0]['quadro_medio'], unid_ord.iloc[0]['pessoas'])}.</li>
    <li>{meses_altos_txt.capitalize()} tiveram {saidas_txt(saidas_altos)} em {n_altos} meses ({num(media_altos, 2)} por mês); os meses comuns, sem ajuste de época no gerador, {saidas_txt(saidas_comuns)} em {n_comuns} meses ({num(media_comuns, 2)} por mês).</li>
    </ul>"""
    sazonal_interp = (
        f"{meses_altos_txt.capitalize()} têm mais saídas por mês do que os meses comuns, como no padrão colocado no gerador."
        if sazonalidade_confirmada else
        f"O gerador tinha mais chance de saída em {meses_altos_txt}, mas o padrão não apareceu: esses meses ficaram abaixo dos meses comuns. "
        f"Com {saidas} saídas em {len(mensal)} meses, poucas saídas por mês, o sorteio pesa mais do que o padrão.")
    p1_interp = f"""<p>{area_top['area']} concentra a maior rotatividade da rede{", e os pedidos de demissão são a maior parte das saídas, o que aponta mais para decisões de quem trabalha do que para cortes" if n_pedido > n_empresa else ""}. {sazonal_interp}
    Em equipes pequenas, duas ou três saídas já mudam muito a taxa, então a leitura por equipe vale como sinal para investigar.</p>"""
    resto_hipo = (f"se a rotatividade de {area_top['area']} acompanha meta, comissão e escala;\n"
                  "    e se a diferença entre unidades se repete em outro ano ou é efeito de poucas pessoas.")
    p1_hipo = (f"""<p>Na vida real seria preciso verificar: se as saídas de {meses_altos_txt} vêm de quem espera o 13º e as festas
    (entrevista de desligamento com as mesmas perguntas para todos); {resto_hipo}</p>"""
               if sazonalidade_confirmada else
               f"""<p>Hipótese testada e não confirmada: mais pessoas sairiam em {meses_altos_txt}, depois do 13º e das festas.
    Nesta base, {meses_altos_txt} ficaram com {num(media_altos, 2)} saídas por mês, contra {num(media_comuns, 2)} nos meses comuns.
    Com dados reais, valeria testar de novo com mais anos de histórico.</p>
    <p>Também seria preciso verificar {resto_hipo}</p>""")

    a90_nome = a90_top["area"]
    p2_fato = f"""<ul>
    <li>Na rede, {fracao(s90_rede['sairam_90_dias'], s90_rede['admitidos'])} dos admitidos saíram antes de 90 dias.</li>
    <li>Em {a90_nome}, {fracao(a90_top['sairam_90_dias'], a90_top['admitidos'])}.</li>
    <li>As saídas na experiência são {fracao(n_saidas_90, saidas)} de todas as saídas.</li>
    </ul>"""
    p2_interp = f"""<p>{a90_nome} perde gente cedo: a taxa de saída na experiência fica acima da rede em {acima_rede} das
    {len(eq_area_top)} equipes da área com base suficiente. Quando o problema se repete com líderes diferentes, a explicação mais
    provável está na própria função (o que se promete na vaga, a escala, a pressão do caixa, o treinamento inicial) e não em um líder.</p>"""
    p2_hipo = f"""<p>Seria preciso verificar com quem saiu na experiência e com quem ficou: se o anúncio e a entrevista mostram a rotina,
    a escala e a meta antes do aceite; quanto tempo de treino a pessoa nova recebe em {a90_nome}; e se as saídas pela empresa nesse
    período são decisão do líder ou da pessoa. Equipes com menos de {BASE_MINIMA} admissões aparecem sem percentual.</p>"""

    p3_fato = f"""<ul>
    <li>Nos 3 meses antes da saída, quem saiu faltou {falta_txt(sd['faltas'], sd['dias'], sd['pessoas'])}.</li>
    <li>Quem ficou, nos mesmos meses do calendário, faltou {falta_txt(fd['faltas'], fd['dias'], fd['pessoas'])}.</li>
    <li>Antes de um pedido de demissão, {falta_txt(tp['saiu']['faltas'], tp['saiu']['dias'], tp['saiu']['pessoas'])}.</li>
    </ul>"""
    p3_interp = f"""<p>A falta sobe perto da saída e é mais alta antes de um pedido de demissão. Longe da saída, com menos pessoas em
    cada ponto, o nível fica parecido com o de quem ficou, então a alta não parece um traço antigo. O absenteísmo também
    se concentra na equipe {html.escape(rotulo_equipe(lider_abs))}: {falta_txt(lider_abs['faltas'], lider_abs['dias_previstos'], pessoas_lider_abs)}
    em 24 meses, contra {falta_txt(resto_abs['faltas'], resto_abs['dias_previstos'], BASE_MINIMA)} no resto da rede, o que sugere um
    fator de grupo além do individual.</p>"""
    p3_hipo = """<p>Este padrão foi plantado no gerador, então aqui ele confirma o método, não descobre nada. Em dados reais seria preciso
    verificar se a alta de faltas antecede a decisão de sair ou é consequência dela, e que parte das faltas tem motivo de saúde.
    O motivo da falta não está na base de propósito, porque pode revelar dado de saúde: essa verificação seria feita em conversa, com
    cuidado, e nunca para marcar uma pessoa.</p>"""

    s_b, s_m, s_a = sens.loc["baixo"], sens.loc["medio"], sens.loc["alto"]
    p4_fato = f"""<ul>
    <li>Cenário médio: {reais_mil(s_m['total'])} em 24 meses.</li>
    <li>Cenário baixo: {reais_mil(s_b['total'])}.</li>
    <li>Cenário alto: {reais_mil(s_a['total'])}.</li>
    </ul>"""
    p4_interp = f"""<p>Mesmo no cenário baixo o custo é alto, e a maior parte não aparece em nenhuma linha da
    contabilidade com esse nome: está no tempo em que a pessoa nova ainda não rende e nas horas de recrutar e treinar. A rescisão
    não muda entre os cenários, porque segue a lei; o que move o total são as premissas de reposição e de aprendizado.</p>"""
    p4_hipo = """<p>Seria preciso trocar as premissas pelos números reais da empresa: encargos do regime tributário, custo de
    cada processo seletivo, horas de treino e a curva de aprendizado de cada função (medida, por exemplo, por vendas ou itens por
    hora no primeiro trimestre). Ficam de fora vendas perdidas com a vaga aberta, horas extras de quem cobre e efeito no clima.</p>"""

    def marca_parcial(r):
        n = int(r["componentes_usados"])
        return "" if n == len(m.COMPONENTES) else f" (índice com {n} de {len(m.COMPONENTES)} componentes)"

    top_txt = "".join(f"<li>{html.escape(rotulo_equipe(r))}: {num(r['indice'], 2)}{marca_parcial(r)}.</li>" for _, r in top3.iterrows())
    p5_fato = f"""<ul>{top_txt}</ul>"""
    primeiro = top3.iloc[0]
    p5_interp = f"""<p>A equipe {html.escape(rotulo_equipe(primeiro))} aparece primeiro, puxada por {nomes_comp[maior_contrib(primeiro)]};
    a segunda, por {nomes_comp[maior_contrib(top3.iloc[1])]}; a terceira, por {nomes_comp[maior_contrib(top3.iloc[2])]}.
    O índice mostra onde começar uma conversa; ele não prevê quem vai sair e não olha para pessoas.</p>"""
    p5_hipo = """<p>Seria preciso ouvir cada liderança antes de qualquer ação: mudança de escala, reforma, troca de gestor ou
    mercado aquecido aparecem só na conversa. Os pesos e as referências são uma escolha; quem discordar pode trocá-los em
    <code>config/premissas.toml</code> e ver se a ordem das equipes muda. Vale recalcular a cada trimestre.</p>"""

    # ------------------------------------------------------------ como os dados foram gerados
    from scripts.gerar_dados import EQUIPES
    vagas = sum(e[3] for e in EQUIPES)
    nomes_mes = {int(k): MESES_PT_LONGO[int(k) - 1] for k in g["sazonalidade"]}
    risco_txt = lista([f"{a} {num(v, 3)}" for a, v in g["risco_base_mes"].items()])
    saz_txt = lista([f"{nomes_mes[int(k)]} ×{num(v, 1)}" for k, v in g["sazonalidade"].items()])
    meses_altos = lista([MESES_PT_LONGO[k - 1] for k in g["meses_faltas_altas"]])
    geracao = f"""<ul>
    <li>Rede fictícia de 3 unidades e {len(EQUIPES)} equipes, cada uma com um líder identificado só por código (L01 a L{len(EQUIPES):02d}),
    e {vagas} vagas ocupadas no início do período. Cada vaga que fica livre é reposta entre {g['reposicao_dias_min']} e
    {g['reposicao_dias_max']} dias depois.</li>
    <li>Chance mensal de saída de quem tem mais de 1 ano de casa: {risco_txt}. Sazonalidade: {saz_txt}.</li>
    <li>Mais saídas nos primeiros 90 dias: chance ×{num(g['multiplicador_saida_90_dias_geral'], 1)} em todas as áreas e
    ×{num(g['multiplicador_saida_90_dias_area'], 1)} em {g['area_saida_90_dias']}. De 90 dias a 1 ano, ×{num(g['multiplicador_saida_primeiro_ano'], 1)};
    depois de 1 ano, ×{num(g['multiplicador_saida_veteranos'], 1)}.</li>
    <li>Uma equipe com problema plantado: na equipe do líder {g['lider_faltas_alto']}, faltas ×{num(g['multiplicador_faltas_lider'], 1)},
    saídas ×{num(g['multiplicador_saida_lider'], 1)} e chance {num(g['chance_pedido_lider'], 2)} de a saída ser pedido de demissão.</li>
    <li>Faltas: média de {num(g['faltas_base_mes'], 2)} por pessoa por mês, com uma propensão individual sorteada (média 1) e
    ×{num(g['multiplicador_faltas_meses_altos'], 2)} em {meses_altos}. Nos 3 meses antes da saída as faltas sobem, mais perto do fim:
    até ×{num(g['multiplicador_faltas_antes_pedido'], 1)} antes de um pedido de demissão e até ×{num(g['multiplicador_faltas_antes_empresa'], 1)}
    antes de um desligamento pela empresa.</li>
    <li>Chance de a saída ser pedido de demissão: {num(g['chance_pedido'], 2)}; na experiência, {num(g['chance_pedido_experiencia'], 2)}
    ({num(g['chance_pedido_90_dias_area'], 2)} em {g['area_saida_90_dias']}).</li>
    <li>Semente fixa {g['semente']}: rodar o gerador de novo produz exatamente os mesmos dados (há um teste para isso).</li>
    </ul>"""

    corpo = f"""
<header class="topo">
  <div class="faixa">
    <p class="selo">Projeto de portfólio · dados totalmente fictícios</p>
    <h1>Rotatividade em uma rede de lojas</h1>
    <p class="sub">Três unidades, {n_pessoas} pessoas ao longo de {len(meses)} meses ({mes_longo(meses[0])} a {mes_longo(meses[-1])}).
    Cinco perguntas de gestão de pessoas respondidas com dados, separando o fato, a interpretação e o que ainda precisaria
    ser verificado.</p>
  </div>
  <nav aria-label="Seções">
    <a href="#resumo">Resumo</a><a href="#dados">Como os dados foram gerados</a><a href="#p1">Onde e quando</a><a href="#p2">90 dias</a>
    <a href="#p3">Faltas</a><a href="#p4">Custo</a><a href="#p5">Índice</a><a href="#etica">Ética e LGPD</a><a href="#limites">Limitações</a>
  </nav>
</header>

<main>
<section id="resumo" class="resumo">
  <h2>Resumo</h2>
  <div class="kpis">
    <div class="kpi"><span class="valor">{saidas}</span><span class="rotulo">saídas em {len(meses)} meses; {fracao(n_pedido, saidas)} por pedido de demissão</span></div>
    <div class="kpi"><span class="valor">{pct(total['taxa_anual'])}</span><span class="rotulo">rotatividade ao ano ({saidas} saídas, quadro médio de {num(total['quadro_medio'], 1)})</span></div>
    <div class="kpi alerta"><span class="valor">{fracao(a90_top['sairam_90_dias'], a90_top['admitidos']).split(' (')[0]}</span><span class="rotulo">dos admitidos em {a90_nome} saem antes de 90 dias ({int(a90_top['sairam_90_dias'])} de {int(a90_top['admitidos'])})</span></div>
    <div class="kpi"><span class="valor">{reais_mil(s_m['total'])}</span><span class="rotulo">custo em 24 meses no cenário médio (de {reais_mil(s_b['total'])} a {reais_mil(s_a['total'])})</span></div>
  </div>
  <p class="nota">Tudo aqui é fictício: a rede, as pessoas e os líderes não existem. O objetivo é demonstrar o método de análise,
  não descobrir algo novo. A seção seguinte lista os padrões que foram colocados no gerador.</p>
</section>

<section id="dados">
  <h2>Como os dados foram gerados</h2>
  <p>Os dados saem de um script (<code>scripts/gerar_dados.py</code>) com semente fixa, a partir dos números de
  <code>config/premissas.toml</code>. Os padrões abaixo foram embutidos de propósito, para a análise ter o que encontrar:</p>
  {geracao}
  <p>Quando a análise reencontra esses padrões, isso mostra que o método funciona. Não é uma descoberta sobre o comércio.
  A base tem só código da pessoa, unidade, área, cargo, líder, datas de admissão e de desligamento, tipo de desligamento e
  a contagem de faltas por mês, sem motivo. Não há nome, salário individual nem dado sensível.</p>
</section>

<section id="p1">
  <p class="numero">Pergunta 1</p>
  <h2>Onde e quando as pessoas saem?</h2>
  <div class="grafico">{g_mensal}</div>
  {tab_mensal}
  <div class="grafico">{g_equipes}</div>
  {tab_unid}{tab_area}{tab_eq}
  {blocos(p1_fato, p1_interp, p1_hipo)}
</section>

<section id="p2">
  <p class="numero">Pergunta 2</p>
  <h2>Quantas pessoas saem nos primeiros 90 dias?</h2>
  <h3 class="grafico-titulo">Por área</h3>
  <div class="grafico">{g_90_area}</div>
  <h3 class="grafico-titulo">Por equipe (líder)</h3>
  <div class="grafico">{g_90_eq}</div>
  <p class="legenda">Em vermelho, grupos com taxa de pelo menos 1,3 vez a da rede, que tem {fracao(s90_rede['sairam_90_dias'], s90_rede['admitidos'])}.
  Só entram admissões feitas no período com 90 dias completos até {mes_longo(meses[-1])}. Grupos com menos de {BASE_MINIMA}
  admissões não viram barra{": " + lista(areas_pequenas_90 + eq_pequenas_90) if (areas_pequenas_90 or eq_pequenas_90) else ""}.</p>
  {tab_90}
  {blocos(p2_fato, p2_interp, p2_hipo)}
</section>

<section id="p3">
  <p class="numero">Pergunta 3</p>
  <h2>A falta aumenta antes da saída?</h2>
  <div class="grafico">{g_faltas}</div>
  <p class="legenda">Quem saiu: pessoas com pelo menos 3 meses completos de casa antes do mês da saída, dentro do período (o mês
  da saída não entra). Quem ficou: pessoas sem saída até o fim do período, medidas nos mesmos meses do calendário.
  Quanto mais longe da saída, menos pessoas entram no ponto; as oscilações à esquerda vêm da base menor.</p>
  {tab_faltas}
  {tab_abs_lider}
  {blocos(p3_fato, p3_interp, p3_hipo)}
</section>

<section id="p4">
  <p class="numero">Pergunta 4</p>
  <h2>Quanto custa a rotatividade?</h2>
  <div class="grafico">{g_custo}</div>
  {tab_custo}
  {tab_sens}
  {tab_premissas}
  {tab_salarios}
  <p class="legenda">Cálculo por saída: rescisão (custo administrativo, mais aviso e multa quando a empresa desliga depois da
  experiência), mais reposição (recrutamento, admissão e treinamento), mais o salário do cargo com encargos multiplicado pela parte
  que a pessoa nova ainda não produz. Supõe que toda vaga é reposta, no mesmo cargo. Todos os valores são fictícios e ficam em
  <code>config/premissas.toml</code>.</p>
  {blocos(p4_fato, p4_interp, p4_hipo)}
</section>

<section id="p5">
  <p class="numero">Pergunta 5</p>
  <h2>Onde abrir a conversa primeiro?</h2>
  <p>Índice por área e por líder, de 0 a 1. Cada componente é o valor do grupo dividido por uma referência, com teto em 1;
  a contribuição é o componente vezes o peso; o índice é a soma das contribuições. Não há modelo de previsão nem rótulo de pessoa.
  Três limites de base:</p>
  <ul class="limites">
    <li><strong>Sem índice:</strong> grupo com menos de {BASE_MINIMA} pessoas nos últimos 12 meses.</li>
    <li><strong>Fora da conta:</strong> com menos de {BASE_MINIMA} admissões, o componente dos 90 dias sai do cálculo, sem valor
    imputado, e os pesos dos demais são redistribuídos na mesma proporção ({num(pi['peso_rotatividade_12m'], 2)} e
    {num(pi['peso_absenteismo_6m'], 2)} viram {num(pi['peso_rotatividade_12m'] / (1 - pi['peso_saida_90_dias']), 2)} e
    {num(pi['peso_absenteismo_6m'] / (1 - pi['peso_saida_90_dias']), 2)}); a linha recebe a marcação "índice com 2 de 3 componentes".</li>
    <li><strong>Base pequena:</strong> com menos de {base_pequena} pessoas ou de {base_pequena} admissões, o índice aparece, com
    leitura cautelosa (marcado com *).</li>
  </ul>
  {tab_pesos}
  <div class="grafico">{g_indice}</div>
  <p class="legenda">{nota_asterisco}</p>
  {tab_indice_eq}
  {tab_indice_area}
  <p class="legenda">Valores arredondados; o índice usa os valores exatos.</p>
  <p>Nos grupos de base pequena, 1 ou 2 eventos mudam a posição no ranking. {exemplo_txt}</p>
  {blocos(p5_fato, p5_interp, p5_hipo)}
</section>

<section id="etica">
  <h2>Ética e LGPD</h2>
  <p><strong>Por que o índice é por área e por líder.</strong> O objetivo é encontrar onde as condições de trabalho merecem atenção,
  e essas condições são do grupo (rotina, escala, liderança, treinamento). Um índice por pessoa viraria uma previsão sobre alguém,
  com risco de rótulo e de decisão injusta. Por isso nenhum gráfico, tabela ou índice deste relatório olha para uma pessoa.</p>
  <p><strong>Regra de base mínima.</strong> Em grupo pequeno, um percentual identifica a pessoa mesmo sem nome: dizer que metade
  de uma equipe de 2 pessoas pediu demissão aponta quem foi. Por isso todo percentual vem com o número absoluto ao lado, e grupo
  com menos de {BASE_MINIMA} pessoas aparece "sem percentual". No índice valem três limites:</p>
  <ul class="limites">
    <li><strong>Sem índice:</strong> grupo com menos de {BASE_MINIMA} pessoas nos últimos 12 meses.</li>
    <li><strong>Fora da conta:</strong> com menos de {BASE_MINIMA} admissões, o componente dos 90 dias sai do cálculo, sem valor
    imputado, e os pesos dos demais são redistribuídos na mesma proporção ({num(pi['peso_rotatividade_12m'], 2)} e
    {num(pi['peso_absenteismo_6m'], 2)} viram {num(pi['peso_rotatividade_12m'] / (1 - pi['peso_saida_90_dias']), 2)} e
    {num(pi['peso_absenteismo_6m'] / (1 - pi['peso_saida_90_dias']), 2)}); a linha recebe a marcação "índice com 2 de 3 componentes".</li>
    <li><strong>Base pequena:</strong> com menos de {base_pequena} pessoas ou de {base_pequena} admissões, o índice aparece, com
    leitura cautelosa (marcado com *).</li>
  </ul>
  <p><strong>Sem dados sensíveis.</strong> A base não tem nada de saúde, origem racial, religião, opinião política, filiação
  sindical, vida sexual, dados genéticos ou biométricos (Lei 13.709/2018, art. 5º, II), nem nome, gênero, idade ou salário
  individual: não são necessários para as cinco perguntas, e a lei pede só o mínimo necessário para a finalidade (art. 6º, III).
  As faltas estão sem motivo, porque o motivo pode revelar saúde.</p>
  <p><strong>O índice por líder não avalia o líder.</strong> Ele não é avaliação de desempenho de quem lidera a equipe: indica onde
  ouvir primeiro, e a liderança participa da leitura dos números antes de qualquer decisão.</p>
  <p><strong>Limites de uso.</strong> O índice serve para abrir conversa com a liderança e orientar ações de retenção. Não deve ser
  usado para avaliação de desempenho, punição, nem decisão sobre uma pessoa específica, inclusive sobre líderes. Faltas entram
  como sinal do grupo; em nenhum caso o índice deve ser usado para cobrar presença de uma pessoa ou questionar atestado. Em uma empresa
  real, o uso destes dados precisa de finalidade informada às pessoas, acesso restrito a quem precisa e revisão periódica.</p>
</section>

<section id="limites">
  <h2>Limitações</h2>
  <ul>
    <li>Os dados são fictícios e os padrões foram plantados; os resultados demonstram o método e não dizem nada sobre o varejo.</li>
    <li>As equipes têm de 5 a 14 vagas. Uma ou duas saídas mudam muito as taxas; nenhum resultado por equipe tem significância estatística.</li>
    <li>{poder_fato} {poder_interp}</li>
    <li>Cada pessoa tem um único líder durante todo o tempo de casa.</li>
    <li>O custo usa o salário do cargo, sem reajustes, comissões, benefícios ou horas extras.</li>
    <li>A rotatividade usa saídas sobre o quadro médio. A fórmula que soma admissões e saídas e divide por dois dá números parecidos aqui, porque quase toda vaga é reposta.</li>
    <li>A comparação de faltas mostra associação, não causa.</li>
  </ul>
</section>
</main>

<footer>
  <p>Análise e código: <strong>Daniela Matos</strong> · <a href="{LINKEDIN}">LinkedIn</a> ·
  <a href="{SITE}">capitalhumanointelligence.com</a></p>
  <p>Código aberto em Python (pandas, plotly e pytest), com testes para cada métrica e para os dados gerados. Licença MIT.
  Todos os dados são fictícios.</p>
</footer>
"""
    pagina = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rotatividade em uma rede de lojas | People Analytics com dados fictícios</title>
<meta name="description" content="Análise de rotatividade com dados fictícios: onde e quando as pessoas saem, saídas nos 90 dias, faltas antes da saída, custo com cenários e índice por área e por líder.">
<meta name="author" content="Daniela Matos">
{etiquetas_previa()}
<style>{CSS}</style>
</head>
<body>
{corpo}
{SCRIPT_CELULAR}
</body>
</html>
"""
    destino = raiz / "docs" / "index.html"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(pagina, encoding="utf-8")
    return destino


CSS = f"""
:root {{
  --verde: {VERDE}; --creme: {CREME}; --dourado: {DOURADO}; --vermelho: {VERMELHO};
  --tinta: {TINTA}; --cinza: {CINZA}; --linha: #D9D2C3;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; }}
body {{ margin: 0; background: var(--creme); color: var(--tinta);
  font-family: "Segoe UI", Roboto, Helvetica, Arial, sans-serif; font-size: 17px; line-height: 1.6; }}
/* Texto justificado com hifenização só em palavras longas: 10 letras ou mais, com 4 antes e 4 depois do hífen */
p, li {{ text-align: justify; hyphens: auto; -webkit-hyphens: auto; hyphenate-limit-chars: 10 4 4;
  -webkit-hyphenate-limit-before: 4; -webkit-hyphenate-limit-after: 4; }}
h1, h2, h3 {{ font-family: Georgia, "Times New Roman", serif; color: var(--verde); line-height: 1.25; }}
h1 {{ font-size: 2.3rem; margin: .2rem 0 .6rem; color: var(--creme); }}
h2 {{ font-size: 1.75rem; margin: .2rem 0 1rem; }}
h3 {{ font-size: 1.2rem; margin: 1.6rem 0 .4rem; }}
h3.grafico-titulo {{ font-family: inherit; font-size: 1rem; color: var(--tinta); margin: 1.2rem 0 .3rem; }}
.topo {{ background: var(--verde); color: var(--creme); }}
.faixa {{ max-width: 1040px; margin: 0 auto; padding: 2.4rem 24px 1.4rem; }}
.selo {{ display: inline-block; margin: 0; font-size: .85rem; letter-spacing: .04em; color: var(--dourado);
  border: 1px solid var(--dourado); border-radius: 999px; padding: .1rem .8rem; text-align: left; }}
.sub {{ max-width: 760px; margin: 0; font-size: 1.05rem; }}
nav {{ max-width: 1040px; margin: 0 auto; padding: 0 24px 1rem; display: flex; flex-wrap: wrap; gap: .3rem 1.2rem; }}
nav a {{ color: var(--creme); text-decoration: none; border-bottom: 2px solid transparent; font-size: .95rem; }}
nav a:hover, nav a:focus {{ border-bottom-color: var(--dourado); }}
main {{ max-width: 1040px; margin: 0 auto; padding: 0 24px; }}
section {{ background: #FFFFFF; border-radius: 10px; padding: 1.6rem 1.8rem; margin: 1.6rem 0;
  border-top: 4px solid var(--dourado); }}
.numero {{ margin: 0; font-size: .85rem; letter-spacing: .08em; text-transform: uppercase; color: var(--cinza); text-align: left; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .9rem; margin: .4rem 0 1.2rem; }}
.kpis-3 {{ grid-template-columns: repeat(3, 1fr); }}
.kpi {{ background: var(--creme); border-radius: 8px; padding: .9rem 1rem; border-left: 4px solid var(--verde);
  display: flex; flex-direction: column; gap: .2rem; }}
.kpi.alerta {{ border-left-color: var(--vermelho); }}
.kpi.alerta .valor {{ color: var(--vermelho); }}
.kpi .valor {{ font-family: Georgia, serif; font-size: 1.8rem; color: var(--verde); line-height: 1.1; }}
.kpi .rotulo {{ font-size: .9rem; color: var(--tinta); line-height: 1.35; }}
.respostas {{ padding-left: 1.3rem; margin: 0; }}
.respostas li {{ margin: .35rem 0; }}
.nota, .legenda {{ font-size: .9rem; color: var(--cinza); }}
.grafico {{ margin: .6rem 0; border: 1px solid #EEE8DC; border-radius: 8px; overflow: hidden; }}
details.tabela {{ margin: .2rem 0 1rem; font-size: .92rem; }}
details.tabela summary {{ cursor: pointer; color: var(--verde); font-weight: 600; }}
.rolagem {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; margin: .6rem 0; font-size: .92rem; }}
th, td {{ text-align: left; padding: .45rem .6rem; border-bottom: 1px solid var(--linha); vertical-align: top; }}
th {{ background: var(--creme); color: var(--verde); font-weight: 600; }}
code {{ background: var(--creme); padding: .05rem .35rem; border-radius: 4px; font-size: .9em; }}
footer {{ max-width: 1040px; margin: 0 auto; padding: 0 24px 2.5rem; font-size: .9rem; color: var(--cinza); }}
footer a {{ color: var(--verde); }}
/* cartões no computador: Fato na largura inteira; Interpretação e Hipótese lado a lado, em duas colunas iguais */
.fih {{ display: grid; grid-template-columns: 1fr 1fr; gap: .9rem; margin-top: 1.2rem; }}
.fih .fato {{ grid-column: 1 / -1; }}
.fih .b {{ background: var(--creme); border-radius: 8px; padding: .8rem 1rem; border-top: 4px solid var(--verde); }}
.fih .interp {{ border-top-color: var(--dourado); }}
.fih .hipo {{ border-top-color: var(--cinza); }}
.fih h3 {{ margin: 0 0 .4rem; font-size: 1.05rem; }}
.fih ul {{ padding-left: 1.1rem; margin: 0; }}
.fih li {{ margin: .3rem 0; }}
.fih p {{ margin: 0; }}
/* cartões: texto justificado e hifenização em português (só palavras longas), para não abrir espaços grandes */
.fih p, .fih li {{ text-align: justify; hyphens: auto; -webkit-hyphens: auto; hyphenate-limit-chars: 10 4 4;
  -webkit-hyphenate-limit-before: 4; -webkit-hyphenate-limit-after: 4; }}
.base-pequena {{ color: var(--vermelho); }}
.conta {{ font-size: .85rem; color: var(--cinza); }}
ul.limites {{ margin: .4rem 0 1rem; padding-left: 1.2rem; }}
ul.limites li {{ margin: .3rem 0; }}
.marca {{ font-size: .8rem; color: var(--cinza); font-weight: 400; }}
/* Tabela do índice: no computador, valor e conta em cada célula; até 600 px, só as contribuições e a conta numa linha expansível */
.tab-indice .cel-curta, .tab-indice .linha-conta {{ display: none; }}
.tab-indice .linha-conta details summary {{ cursor: pointer; color: var(--verde); font-size: .85rem; }}
.tab-indice .linha-conta ul {{ margin: .4rem 0 0; padding-left: 1.1rem; }}
.tab-indice .linha-conta li {{ text-align: left; font-size: .85rem; }}
@media (max-width: 600px) {{
  .tab-indice {{ font-size: .76rem; }}
  .tab-indice th, .tab-indice td {{ padding: .4rem .2rem; }}
  .tab-indice th {{ hyphens: none; }}
  .tab-indice td:first-child {{ width: 30%; }}
  .tab-indice .cel-completa {{ display: none; }}
  .tab-indice .cel-curta {{ display: inline; }}
  .tab-indice .linha-conta {{ display: table-row; }}
  .tab-indice tr:has(+ .linha-conta) td {{ border-bottom: none; }}
}}
@media (max-width: 900px) {{ .fih {{ grid-template-columns: 1fr; }} }}
@media (max-width: 760px) {{
  body {{ font-size: 16px; }}
  h1 {{ font-size: 1.75rem; }}
  h2 {{ font-size: 1.4rem; }}
  .faixa {{ padding: 1.6rem 16px 1rem; }}
  nav {{ padding: 0 16px .9rem; }}
  main, footer {{ padding-left: 16px; padding-right: 16px; }}
  section {{ padding: 1.2rem 1rem; }}
  .kpis, .kpis-3 {{ grid-template-columns: 1fr 1fr; }}
  .kpi .valor {{ font-size: 1.35rem; white-space: nowrap; }}
}}
@media (max-width: 420px) {{
  .kpis-3 {{ grid-template-columns: 1fr; }}
}}
"""
