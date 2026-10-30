"""Gera uma capa de barras (1200 x 630) em capturas/para-revisao/capa-gerada.png, só para conferência.

A capa publicada (docs/capa-2026-10.png) vem do sistema de peças (capturas/scripts/montar_pecas.py);
este script nunca grava dentro de docs, para não sobrescrever a capa aprovada.

Monta um HTML com as cores e fontes do relatório e um gráfico simplificado do índice por líder
(barras empilhadas com as três cores, sem eixos), e salva a tela do Chrome em modo headless como PNG.

Uso:
    python scripts/gerar_capa.py
"""

import html
import os
import shutil
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")  # acentos certos no terminal do Windows
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from analise import metricas as m  # noqa: E402
from analise.relatorio import CINZA, CREME, DOURADO, TINTA, VERDE, VERDE_MEDIO  # noqa: E402

LARGURA, ALTURA, MARGEM = 1200, 630, 60

CHROME = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
          r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"]

FONTE_TITULO = 'Georgia, "Times New Roman", serif'
FONTE_TEXTO = '"Segoe UI", Roboto, Helvetica, Arial, sans-serif'


def renderizar_png(pagina: str, destino: Path, largura: int, altura: int) -> Path:
    """Abre o HTML no Chrome headless, com perfil temporário e sem porta de depuração, e salva a tela em PNG."""
    chrome = next((c for c in CHROME if os.path.exists(c)), None) or shutil.which("chrome")
    if not chrome:
        raise SystemExit("Chrome não encontrado.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="capa-") as tmp:
        arquivo = Path(tmp) / "capa.html"
        arquivo.write_text(pagina, encoding="utf-8")
        subprocess.run([chrome, "--headless=new", f"--user-data-dir={Path(tmp) / 'perfil'}",
                        "--no-first-run", "--disable-gpu",
                        "--hide-scrollbars", "--force-device-scale-factor=1",
                        f"--window-size={largura},{altura}", f"--screenshot={destino}",
                        arquivo.as_uri()], check=True, capture_output=True, timeout=60)
    return destino


def barras_indice() -> list[tuple[float, float, float]]:
    """Contribuições (rotatividade, 90 dias, absenteísmo) de cada líder com índice, na ordem do relatório."""
    premissas = m.carregar_premissas(RAIZ / "config" / "premissas.toml")
    pessoas, faltas = m.carregar_dados(RAIZ / "dados")
    meses = m.meses_do_periodo(premissas["periodo"]["inicio"], premissas["periodo"]["meses"])
    indice = m.indice_risco(m.fatores_por_grupo(pessoas, faltas, meses, ["unidade", "area", "lider"]),
                            premissas["indice"], premissas["relatorio"]["base_minima"])
    indice = indice[~indice["base_insuficiente"]].sort_values("indice", ascending=False)
    # componente fora da conta entra como 0, como no gráfico do relatório
    return [tuple(float(r[f"contrib_{c}"]) if r[f"contrib_{c}"] == r[f"contrib_{c}"] else 0.0
                  for c in ("rotatividade_12m", "saida_90_dias", "absenteismo_6m"))
            for _, r in indice.iterrows()]


def svg_barras(barras, largura: int, altura: int) -> str:
    passo = altura / len(barras)
    espessura = passo * 0.62
    partes = []
    for i, contrib in enumerate(barras):
        x, y = 0.0, i * passo + (passo - espessura) / 2
        for valor, cor in zip(contrib, (VERDE, DOURADO, VERDE_MEDIO)):
            w = valor * largura  # escala de 0 a 1, como no relatório
            if w > 0:
                partes.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{espessura:.1f}" fill="{cor}"/>')
            x += w
    return (f'<svg width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" '
            f'xmlns="http://www.w3.org/2000/svg">{"".join(partes)}</svg>')


def pagina_capa(barras) -> str:
    e = html.escape
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><style>
* {{ box-sizing: border-box; margin: 0; }}
html, body {{ width: {LARGURA}px; height: {ALTURA}px; overflow: hidden; }}
body {{ background: {CREME}; color: {TINTA}; font-family: {FONTE_TEXTO}; position: relative; }}
.faixa {{ position: absolute; left: 0; top: 0; width: 100%; height: 10px; background: {VERDE}; }}
.area {{ position: absolute; inset: {MARGEM}px; display: grid; grid-template-columns: 1fr 430px;
  grid-template-rows: 1fr auto; column-gap: 56px; }}
.texto {{ display: flex; flex-direction: column; justify-content: center; }}
.selo {{ align-self: flex-start; font-size: 19px; letter-spacing: .03em; color: {VERDE}; font-weight: 600;
  border: 2px solid {DOURADO}; border-radius: 999px; padding: 5px 18px; background: #FFFFFF; }}
h1 {{ font-family: {FONTE_TITULO}; font-weight: 400; color: {VERDE}; font-size: 62px; line-height: 1.08;
  margin: 26px 0 22px; text-wrap: balance; }}
.sub {{ font-size: 27px; line-height: 1.35; color: {TINTA}; max-width: 560px; }}
.grafico {{ background: #FFFFFF; border-top: 6px solid {DOURADO}; border-radius: 10px; padding: 26px 28px;
  align-self: center; }}
.rodape {{ grid-column: 1 / 3; border-top: 2px solid {VERDE}; padding-top: 14px; font-size: 22px;
  color: {VERDE}; font-weight: 600; }}
.rodape span {{ color: {CINZA}; font-weight: 400; }}
</style></head><body>
<div class="faixa"></div>
<div class="area">
  <div class="texto">
    <p class="selo">{e("Projeto de portfólio · dados fictícios")}</p>
    <h1>{e("Rotatividade em uma rede de lojas")}</h1>
    <p class="sub">{e("Cinco perguntas de gestão de pessoas respondidas com dados")}</p>
  </div>
  <div class="grafico">{svg_barras(barras, 374, 330)}</div>
  <p class="rodape">Daniela Matos <span>· People Analytics</span></p>
</div>
</body></html>
"""


if __name__ == "__main__":
    print("Aviso: a capa publicada (docs/capa-2026-10.png) vem do sistema de peças; esta é só uma capa de conferência.")
    destino = renderizar_png(pagina_capa(barras_indice()), RAIZ / "capturas" / "para-revisao" / "capa-gerada.png",
                             LARGURA, ALTURA)
    print(f"Capa gerada em {destino.relative_to(RAIZ)}")
