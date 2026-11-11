"""Mede o poder do método para detectar a sazonalidade plantada de janeiro e fevereiro.

O relatório mostra um único sorteio do gerador (semente fixa em config/premissas.toml). Este script roda o
mesmo gerador com outras sementes, uma lista fixa e reproduzível (SEMENTES, de 1 a 200, sem a semente oficial),
aplica a cada sorteio a mesma comparação da Pergunta 1 (analise.metricas.comparacao_sazonalidade: saídas por
mês nos meses com fator acima de 1 contra os meses comuns) e conta em quantos sorteios os meses de saída alta
ficam acima. Também mede a diferença entre as duas médias, com a média e a faixa do percentil 10 ao 90.

Grava dados/poder_sazonalidade.json, que o relatório lê na seção de Limitações. Não muda a semente oficial
nem os dados do relatório. Leva cerca de 1 minuto.

Uso:
    python scripts/poder_sazonalidade.py
"""

from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")  # acentos certos no terminal do Windows
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from analise import metricas as m  # noqa: E402
from gerar_dados import gerar  # noqa: E402

SEMENTES = list(range(1, 201))
DESTINO = RAIZ / "dados" / "poder_sazonalidade.json"


def comparar(premissas: dict, semente: int) -> dict:
    """Um sorteio do gerador com a semente dada e a comparação da Pergunta 1 sobre ele."""
    pessoas, _ = gerar(premissas, semente=semente, com_faltas=False)
    pessoas = pessoas.copy()
    for col in ("data_admissao", "data_desligamento"):
        pessoas[col] = pd.to_datetime(pessoas[col])  # mesmo tipo que m.carregar_dados lê do CSV
    meses = m.meses_do_periodo(premissas["periodo"]["inicio"], premissas["periodo"]["meses"])
    saz = {int(k): v for k, v in premissas["geracao"]["sazonalidade"].items()}
    return m.comparacao_sazonalidade(m.rotatividade_mensal(pessoas, meses), saz)


def medir(premissas: dict, sementes: list[int] = SEMENTES) -> dict:
    difs = []
    for s in sementes:
        c = comparar(premissas, s)
        difs.append(c["media_altos"] - c["media_comuns"])
    difs = np.array(difs)
    return {
        "sementes": f"{sementes[0]} a {sementes[-1]}" if sementes == list(range(sementes[0], sementes[-1] + 1))
        else sementes,
        "sorteios": len(sementes),
        "sorteios_com_meses_altos_acima": int((difs > 0).sum()),
        "diferenca_media": round(float(difs.mean()), 4),
        "diferenca_percentil_10": round(float(np.percentile(difs, 10)), 4),
        "diferenca_percentil_90": round(float(np.percentile(difs, 90)), 4),
        "unidade": "saídas por mês (média dos meses com fator acima de 1 menos a média dos meses comuns)",
    }


if __name__ == "__main__":
    premissas = m.carregar_premissas(RAIZ / "config" / "premissas.toml")
    if premissas["geracao"]["semente"] in SEMENTES:
        raise SystemExit("A semente oficial não pode estar na lista.")
    oficial = comparar(premissas, premissas["geracao"]["semente"])
    print(f"Semente oficial: {oficial['media_altos']:.2f} contra {oficial['media_comuns']:.2f} saídas por mês")
    r = medir(premissas)
    DESTINO.write_text(json.dumps(r, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{r['sorteios_com_meses_altos_acima']} de {r['sorteios']} sorteios com os meses de saída alta acima; "
          f"diferença média {r['diferenca_media']:+.2f} (percentil 10 a 90: {r['diferenca_percentil_10']:+.2f} "
          f"a {r['diferenca_percentil_90']:+.2f}) saídas por mês")
    print(f"Gravado em {DESTINO.relative_to(RAIZ)}")
