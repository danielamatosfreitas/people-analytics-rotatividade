"""Gera os dados fictícios da rede de lojas.

Uso:
    python scripts/gerar_dados.py

Saída:
    dados/pessoas.csv          uma linha por pessoa
    dados/faltas_mensais.csv   uma linha por pessoa e mês em que esteve ativa

Tudo é fictício: códigos de pessoa e de líder não correspondem a ninguém.
Não há nome, gênero, idade, raça, estado civil, salário individual nem nenhum outro dado sensível.
As faltas são só uma contagem por mês, sem motivo.
Todos os números que guiam a geração ficam em config/premissas.toml, seção [geracao].
"""

from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")  # acentos certos no terminal do Windows
import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]

# Estrutura da rede: (unidade, área, líder, vagas)
EQUIPES = [
    ("Loja Centro", "Vendas", "L01", 12),
    ("Loja Centro", "Caixa", "L02", 7),
    ("Loja Centro", "Estoque", "L03", 6),
    ("Loja Shopping", "Caixa", "L04", 8),
    ("Loja Shopping", "Vendas", "L05", 14),
    ("Loja Shopping", "Estoque", "L06", 6),
    ("Loja Bairro", "Vendas", "L07", 9),
    ("Loja Bairro", "Caixa", "L08", 6),
    ("Loja Bairro", "Estoque", "L09", 5),
    ("Loja Centro", "Administrativo", "L10", 7),
]

# Cargos por área: (cargo, proporção). O salário de cada cargo fica em config/premissas.toml.
CARGOS = {
    "Vendas": [("Vendedor(a)", 0.80), ("Vendedor(a) sênior", 0.20)],
    "Caixa": [("Operador(a) de caixa", 0.85), ("Fiscal de caixa", 0.15)],
    "Estoque": [("Auxiliar de estoque", 0.70), ("Conferente", 0.30)],
    "Administrativo": [("Assistente administrativo", 0.50), ("Assistente de RH", 0.20), ("Analista financeiro", 0.30)],
}

# Colunas publicadas em dados/pessoas.csv. Nada além disto sai do gerador.
COLUNAS_PESSOAS = ["id", "unidade", "area", "cargo", "lider", "data_admissao", "data_desligamento", "tipo_desligamento"]
COLUNAS_FALTAS = ["id", "mes", "dias_previstos", "faltas"]


def sortear_cargo(rng, area):
    opcoes = CARGOS[area]
    i = rng.choice(len(opcoes), p=[o[1] for o in opcoes])
    return opcoes[i][0]


def gerar(premissas: dict, semente: int | None = None, com_faltas: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """com_faltas=False pula o sorteio das faltas (mais rápido; as pessoas saem iguais, porque as faltas
    são sorteadas depois) e devolve a tabela de faltas vazia. Usado por scripts/poder_sazonalidade.py."""
    g = premissas["geracao"]
    rng = np.random.default_rng(g["semente"] if semente is None else semente)
    risco_base = g["risco_base_mes"]
    sazonalidade = {int(k): v for k, v in g["sazonalidade"].items()}
    inicio = pd.Timestamp(premissas["periodo"]["inicio"])
    meses = pd.period_range(inicio, periods=premissas["periodo"]["meses"], freq="M")
    fim = meses[-1].end_time.normalize()

    pessoas = []

    def nova_pessoa(unidade, area, lider, admissao):
        cargo = sortear_cargo(rng, area)
        pessoa = {
            "id": None,
            "unidade": unidade,
            "area": area,
            "cargo": cargo,
            "lider": lider,
            "data_admissao": admissao,
            "data_desligamento": pd.NaT,
            "tipo_desligamento": None,
            "propensao_falta": rng.gamma(2.0, 0.5),  # média 1: há quem falte mais e quem falte menos
        }
        pessoas.append(pessoa)
        return pessoa

    # Quadro inicial: cada vaga ocupada por alguém admitido antes do período
    ativos = []
    for unidade, area, lider, vagas in EQUIPES:
        for _ in range(vagas):
            dias_casa = int(min(rng.exponential(650) + 20, 3000))
            ativos.append(nova_pessoa(unidade, area, lider, inicio - pd.Timedelta(days=dias_casa)))

    # Simulação mês a mês
    for mes in meses:
        ini_mes, fim_mes = mes.start_time.normalize(), mes.end_time.normalize()
        dias_mes = mes.days_in_month
        proximos = []
        for p in ativos:
            if p["data_admissao"] > fim_mes:
                proximos.append(p)
                continue
            comeco = max(p["data_admissao"] + pd.Timedelta(days=1), ini_mes)
            if comeco > fim_mes:
                proximos.append(p)
                continue
            dias_ativos = (fim_mes - comeco).days + 1
            casa_dias = (comeco + pd.Timedelta(days=dias_ativos // 2) - p["data_admissao"]).days

            risco = risco_base[p["area"]] * sazonalidade.get(mes.month, 1.0)
            if casa_dias < 90:
                if p["area"] == g["area_saida_90_dias"]:
                    risco *= g["multiplicador_saida_90_dias_area"]
                else:
                    risco *= g["multiplicador_saida_90_dias_geral"]
            elif casa_dias < 365:
                risco *= g["multiplicador_saida_primeiro_ano"]
            else:
                risco *= g["multiplicador_saida_veteranos"]
            if p["lider"] == g["lider_faltas_alto"]:
                risco *= g["multiplicador_saida_lider"]
            risco = min(risco, 0.6)
            chance = 1 - (1 - risco) ** (dias_ativos / dias_mes)

            if rng.random() < chance:
                saida = comeco + pd.Timedelta(days=int(rng.integers(0, dias_ativos)))
                experiencia = (saida - p["data_admissao"]).days < 90
                if p["lider"] == g["lider_faltas_alto"]:
                    chance_pedido = g["chance_pedido_lider"]
                elif experiencia and p["area"] == g["area_saida_90_dias"]:
                    chance_pedido = g["chance_pedido_90_dias_area"]
                elif experiencia:
                    chance_pedido = g["chance_pedido_experiencia"]
                else:
                    chance_pedido = g["chance_pedido"]
                p["data_desligamento"] = saida
                p["tipo_desligamento"] = "Pedido de demissão" if rng.random() < chance_pedido else "Desligamento pela empresa"
                # Reposição da vaga depois do prazo sorteado
                admissao = saida + pd.Timedelta(days=int(rng.integers(g["reposicao_dias_min"], g["reposicao_dias_max"] + 1)))
                if admissao <= fim:
                    proximos.append(nova_pessoa(p["unidade"], p["area"], p["lider"], admissao))
            else:
                proximos.append(p)
        ativos = proximos

    df = pd.DataFrame(pessoas)
    df = df.sort_values(["data_admissao", "unidade", "area"]).reset_index(drop=True)
    df["id"] = [f"P{i:04d}" for i in range(1, len(df) + 1)]
    if not com_faltas:
        df["data_admissao"] = df["data_admissao"].dt.date
        df["data_desligamento"] = df["data_desligamento"].dt.date
        return df[COLUNAS_PESSOAS], pd.DataFrame(columns=COLUNAS_FALTAS)

    # Faltas por mês
    linhas = []
    for p in df.itertuples():
        for mes in meses:
            ini_mes, fim_mes = mes.start_time.normalize(), mes.end_time.normalize()
            comeco = max(p.data_admissao, ini_mes)
            final = fim_mes if pd.isna(p.data_desligamento) else min(p.data_desligamento, fim_mes)
            if comeco > final:
                continue
            fracao = ((final - comeco).days + 1) / mes.days_in_month
            dias_previstos = max(1, round(g["dias_previstos_mes"] * fracao))
            media = g["faltas_base_mes"] * fracao * p.propensao_falta
            if p.lider == g["lider_faltas_alto"]:
                media *= g["multiplicador_faltas_lider"]
            if mes.month in g["meses_faltas_altas"]:  # volta às aulas e férias escolares pesam um pouco
                media *= g["multiplicador_faltas_meses_altos"]
            if not pd.isna(p.data_desligamento):
                distancia = (p.data_desligamento.to_period("M") - mes).n
                if 0 <= distancia <= 3:
                    if p.tipo_desligamento == "Pedido de demissão":
                        extra = g["multiplicador_faltas_antes_pedido"] - 1
                    else:
                        extra = g["multiplicador_faltas_antes_empresa"] - 1
                    # a alta cresce à medida que a saída se aproxima
                    media *= 1 + extra * {3: 0.6, 2: 0.8, 1: 1.0, 0: 1.0}[distancia]
            faltas = min(int(rng.poisson(media)), dias_previstos)
            linhas.append({"id": p.id, "mes": str(mes), "dias_previstos": dias_previstos, "faltas": faltas})
    faltas = pd.DataFrame(linhas, columns=COLUNAS_FALTAS)

    df["data_admissao"] = df["data_admissao"].dt.date
    df["data_desligamento"] = df["data_desligamento"].dt.date
    return df[COLUNAS_PESSOAS], faltas


def main():
    with open(RAIZ / "config" / "premissas.toml", "rb") as f:
        premissas = tomllib.load(f)
    pessoas, faltas = gerar(premissas)
    pasta = RAIZ / "dados"
    pasta.mkdir(exist_ok=True)
    pessoas.to_csv(pasta / "pessoas.csv", index=False, encoding="utf-8")
    faltas.to_csv(pasta / "faltas_mensais.csv", index=False, encoding="utf-8")
    saidas = pessoas["data_desligamento"].notna().sum()
    print(f"{len(pessoas)} pessoas, {saidas} saídas, {len(faltas)} linhas de faltas.")


if __name__ == "__main__":
    sys.exit(main())
