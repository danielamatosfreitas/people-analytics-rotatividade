"""Gera o relatório em docs/index.html a partir dos dados em dados/ e das premissas em config/.

Uso:
    python scripts/gerar_relatorio.py
"""

import sys

sys.stdout.reconfigure(encoding="utf-8")  # acentos certos no terminal do Windows
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from analise.relatorio import gerar  # noqa: E402

if __name__ == "__main__":
    destino = gerar(RAIZ)
    print(f"Relatório gerado em {destino.relative_to(RAIZ)}")
