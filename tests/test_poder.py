"""Poder do método para a sazonalidade: o script reproduz o resultado gravado e publicado nas Limitações.

Roda o gerador 200 vezes (sem as faltas), por isso leva cerca de 1 minuto.
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "scripts"))

import poder_sazonalidade as ps  # noqa: E402
from analise import metricas as m  # noqa: E402


def test_poder_da_sazonalidade_reproduz_o_mesmo_x_de_n():
    premissas = m.carregar_premissas(RAIZ / "config" / "premissas.toml")
    gravado = json.loads((RAIZ / "dados" / "poder_sazonalidade.json").read_text(encoding="utf-8"))
    assert premissas["geracao"]["semente"] not in ps.SEMENTES  # a semente oficial fica de fora
    assert ps.medir(premissas) == gravado
    # e é esse o número publicado nas Limitações
    n, x = gravado["sorteios"], gravado["sorteios_com_meses_altos_acima"]
    pagina = (RAIZ / "docs" / "index.html").read_text(encoding="utf-8")
    assert f"Rodando o gerador com {n} sementes, a sazonalidade plantada aparece em {x} de {n} sorteios" in pagina


def test_sem_faltas_as_pessoas_saem_iguais():
    # o atalho com_faltas=False não muda as pessoas sorteadas
    import gerar_dados as gd
    premissas = m.carregar_premissas(RAIZ / "config" / "premissas.toml")
    com, _ = gd.gerar(premissas, semente=7)
    sem, faltas = gd.gerar(premissas, semente=7, com_faltas=False)
    assert com.equals(sem) and faltas.empty
