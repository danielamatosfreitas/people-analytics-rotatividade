"""Funções de cálculo das métricas de rotatividade.

Todas as funções recebem DataFrames simples e devolvem DataFrames ou números,
sem ler arquivos nem desenhar gráficos, para poderem ser testadas com casos
pequenos montados à mão (ver tests/test_metricas.py).

Convenções:
- pessoas: colunas id, unidade, area, cargo, lider, data_admissao,
  data_desligamento (vazia para quem está ativo), tipo_desligamento. Não há salário individual:
  o custo usa o salário do cargo, declarado em config/premissas.toml.
- faltas: colunas id, mes (texto AAAA-MM), dias_previstos, faltas.
- Uma pessoa está ativa no dia d se foi admitida até d e não saiu antes de d.
- A data de desligamento é o último dia trabalhado: no fim desse dia a pessoa já não está no quadro.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import numpy as np
import pandas as pd

PEDIDO = "Pedido de demissão"
EMPRESA = "Desligamento pela empresa"


# ---------------------------------------------------------------- leitura

def carregar_premissas(caminho: str | Path) -> dict:
    with open(caminho, "rb") as f:
        return tomllib.load(f)


def carregar_dados(pasta: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    pasta = Path(pasta)
    pessoas = pd.read_csv(pasta / "pessoas.csv", parse_dates=["data_admissao", "data_desligamento"])
    faltas = pd.read_csv(pasta / "faltas_mensais.csv")
    return pessoas, faltas


def meses_do_periodo(inicio: str, quantidade: int) -> pd.PeriodIndex:
    return pd.period_range(pd.Timestamp(inicio), periods=quantidade, freq="M")


# ---------------------------------------------------------------- quadro e rotatividade

def ativos_em(pessoas: pd.DataFrame, dia) -> pd.Series:
    """Marca quem estava ativo no dia informado."""
    dia = pd.Timestamp(dia)
    return (pessoas["data_admissao"] <= dia) & (
        pessoas["data_desligamento"].isna() | (pessoas["data_desligamento"] >= dia)
    )


def quadro_fim_do_dia(pessoas: pd.DataFrame, dia) -> int:
    """Quantas pessoas estão no quadro ao fim do dia: admitidas até o dia e sem saída até o dia."""
    dia = pd.Timestamp(dia)
    return int(((pessoas["data_admissao"] <= dia) &
                (pessoas["data_desligamento"].isna() | (pessoas["data_desligamento"] > dia))).sum())


def rotatividade_mensal(pessoas: pd.DataFrame, meses: pd.PeriodIndex, por: list[str] | None = None) -> pd.DataFrame:
    """Saídas e quadro médio em cada mês, opcionalmente por grupo (área, unidade, líder).

    Quadro médio = (ativos no primeiro dia do mês + ativos no primeiro dia do mês seguinte) / 2.
    Taxa = saídas no mês / quadro médio. A taxa é separada por tipo de saída.
    Também traz admissões do mês e o quadro ao fim do último dia do mês anterior e do próprio mês,
    para conferir a conta: quadro anterior + admissões menos saídas = quadro no fim do mês.
    """
    por = por or []
    grupos = pessoas.groupby(por) if por else [((), pessoas)]
    linhas = []
    for chave, df in grupos:
        chave = chave if isinstance(chave, tuple) else (chave,)
        for mes in meses:
            ini = mes.start_time.normalize()
            prox = (mes + 1).start_time.normalize()
            saiu = df["data_desligamento"].notna() & (df["data_desligamento"] >= ini) & (df["data_desligamento"] < prox)
            entrou = (df["data_admissao"] >= ini) & (df["data_admissao"] < prox)
            linha = dict(zip(por, chave))
            linha.update({
                "mes": mes,
                "quadro_inicio": int(ativos_em(df, ini).sum()),
                "quadro_fim": int(ativos_em(df, prox).sum()),
                "quadro_fim_mes_anterior": quadro_fim_do_dia(df, ini - pd.Timedelta(days=1)),
                "quadro_fim_mes": quadro_fim_do_dia(df, prox - pd.Timedelta(days=1)),
                "admissoes": int(entrou.sum()),
                "saidas_pedido": int((saiu & (df["tipo_desligamento"] == PEDIDO)).sum()),
                "saidas_empresa": int((saiu & (df["tipo_desligamento"] == EMPRESA)).sum()),
            })
            linhas.append(linha)
    out = pd.DataFrame(linhas)
    out["quadro_medio"] = (out["quadro_inicio"] + out["quadro_fim"]) / 2
    out["saidas"] = out["saidas_pedido"] + out["saidas_empresa"]
    base = out["quadro_medio"].replace(0, np.nan)
    out["taxa"] = out["saidas"] / base
    out["taxa_pedido"] = out["saidas_pedido"] / base
    out["taxa_empresa"] = out["saidas_empresa"] / base
    return out


def rotatividade_anualizada(mensal: pd.DataFrame, por: list[str] | None = None) -> pd.DataFrame:
    """Taxa anual equivalente: saídas do período / quadro médio do período, ajustada para 12 meses."""
    por = por or []
    agg = {"saidas": "sum", "saidas_pedido": "sum", "saidas_empresa": "sum", "quadro_medio": "mean", "mes": "nunique"}
    if por:
        out = mensal.groupby(por).agg(agg).reset_index()
    else:
        out = mensal.agg(agg).to_frame().T
    fator = 12 / out["mes"].astype(float)
    base = out["quadro_medio"].astype(float).replace(0, np.nan)
    out["taxa_anual"] = out["saidas"].astype(float) / base * fator
    out["taxa_anual_pedido"] = out["saidas_pedido"].astype(float) / base * fator
    out["taxa_anual_empresa"] = out["saidas_empresa"].astype(float) / base * fator
    return out.rename(columns={"mes": "meses"})


def comparacao_sazonalidade(mensal: pd.DataFrame, sazonalidade: dict) -> dict:
    """Saídas por mês nos meses com fator acima de 1 no gerador contra os meses comuns (sem fator).

    Regra da Pergunta 1. sazonalidade: {número do mês: fator}; meses ausentes valem 1.
    """
    altos = mensal["mes"].map(lambda p: sazonalidade.get(p.month, 1.0) > 1)
    comuns = mensal["mes"].map(lambda p: p.month not in sazonalidade)
    saidas_altos, n_altos = int(mensal.loc[altos, "saidas"].sum()), int(altos.sum())
    saidas_comuns, n_comuns = int(mensal.loc[comuns, "saidas"].sum()), int(comuns.sum())
    return {"saidas_altos": saidas_altos, "n_altos": n_altos, "media_altos": saidas_altos / n_altos,
            "saidas_comuns": saidas_comuns, "n_comuns": n_comuns, "media_comuns": saidas_comuns / n_comuns}


# ---------------------------------------------------------------- primeiros 90 dias

def saida_90_dias(pessoas: pd.DataFrame, inicio, data_corte, por: list[str] | None = None, dias: int = 90) -> pd.DataFrame:
    """Entre quem foi admitido no período e já completaria 90 dias até a data de corte,
    a proporção que saiu antes de completar 90 dias de casa."""
    inicio, data_corte = pd.Timestamp(inicio), pd.Timestamp(data_corte)
    elegivel = (pessoas["data_admissao"] >= inicio) & (pessoas["data_admissao"] + pd.Timedelta(days=dias) <= data_corte)
    df = pessoas[elegivel].copy()
    casa = (df["data_desligamento"] - df["data_admissao"]).dt.days
    df["saiu_90"] = df["data_desligamento"].notna() & (casa < dias)
    por = por or []
    if por:
        out = df.groupby(por).agg(admitidos=("id", "count"), sairam_90_dias=("saiu_90", "sum")).reset_index()
    else:
        out = pd.DataFrame({"admitidos": [len(df)], "sairam_90_dias": [int(df["saiu_90"].sum())]})
    out["taxa_90_dias"] = out["sairam_90_dias"] / out["admitidos"].replace(0, np.nan)
    return out


# ---------------------------------------------------------------- absenteísmo

def absenteismo(faltas: pd.DataFrame, pessoas: pd.DataFrame | None = None, por: list[str] | None = None,
                meses: list[str] | None = None) -> pd.DataFrame:
    """Absenteísmo = dias de falta / dias de trabalho previstos."""
    df = faltas if meses is None else faltas[faltas["mes"].isin([str(m) for m in meses])]
    por = por or []
    if por:
        df = df.merge(pessoas[["id"] + por], on="id")
        out = df.groupby(por)[["faltas", "dias_previstos"]].sum().reset_index()
    else:
        out = df[["faltas", "dias_previstos"]].sum().to_frame().T
    out["absenteismo"] = out["faltas"] / out["dias_previstos"].replace(0, np.nan)
    return out


def faltas_antes_da_saida(pessoas: pd.DataFrame, faltas: pd.DataFrame, meses: pd.PeriodIndex,
                          janela: int = 3) -> dict:
    """Compara o absenteísmo de quem saiu, nos meses anteriores ao mês da saída,
    com o de quem ficou nos mesmos meses do calendário (grupo de comparação).

    Quem saiu: só entra quem tem a janela inteira dentro do período e já tinha sido admitido antes dela.
    O mês da saída não entra (é incompleto).
    Quem ficou: pessoas sem saída até o fim do período, medidas só nos meses do calendário que aparecem
    nas janelas de quem saiu. Assim os dois grupos são medidos nas mesmas épocas do ano.
    """
    f = faltas.copy()
    f["mes"] = pd.PeriodIndex(f["mes"], freq="M")
    saiu = pessoas[pessoas["data_desligamento"].notna()].copy()
    saiu["mes_saida"] = saiu["data_desligamento"].dt.to_period("M")
    saiu["inicio_janela"] = saiu["mes_saida"] - janela
    saiu = saiu[(saiu["inicio_janela"] >= meses[0]) &
                (saiu["data_admissao"] <= saiu["inicio_janela"].dt.start_time)]

    linhas = f.merge(saiu[["id", "mes_saida", "tipo_desligamento"]], on="id")
    linhas["meses_antes"] = [(s - m).n for s, m in zip(linhas["mes_saida"], linhas["mes"])]
    na_janela = linhas[(linhas["meses_antes"] >= 1) & (linhas["meses_antes"] <= janela)]

    ficou = pessoas[pessoas["data_desligamento"].isna()]
    f_ficou = f[f["id"].isin(ficou["id"])]
    por_mes_ficou = f_ficou.groupby("mes")[["faltas", "dias_previstos"]].sum()

    def comparacao(janela_df):
        """Faltas e dias de quem ficou, nos mesmos meses do calendário da janela de quem saiu."""
        meses_janela = janela_df["mes"].unique()
        base = por_mes_ficou.reindex(meses_janela).fillna(0)
        faltas_, dias = int(base["faltas"].sum()), int(base["dias_previstos"].sum())
        pessoas_mes = f_ficou[f_ficou["mes"].isin(meses_janela)]["id"].nunique()
        return {"taxa": faltas_ / dias if dias else float("nan"), "faltas": faltas_, "dias": dias,
                "pessoas": int(pessoas_mes)}

    def resumo(df):
        d = int(df["dias_previstos"].sum())
        return {"taxa": float(df["faltas"].sum() / d) if d else float("nan"), "faltas": int(df["faltas"].sum()),
                "dias": d, "pessoas": int(df["id"].nunique())}

    por_tipo = {}
    for tipo in (PEDIDO, EMPRESA):
        sub = na_janela[na_janela["tipo_desligamento"] == tipo]
        por_tipo[tipo] = {"saiu": resumo(sub), "ficou": comparacao(sub)}
    curva = (linhas[(linhas["meses_antes"] >= 1) & (linhas["meses_antes"] <= 12)]
             .groupby("meses_antes")[["faltas", "dias_previstos"]].sum())
    curva["absenteismo"] = curva["faltas"] / curva["dias_previstos"]
    curva["pessoas"] = (linhas[(linhas["meses_antes"] >= 1) & (linhas["meses_antes"] <= 12)]
                        .groupby("meses_antes")["id"].nunique())
    s, c = resumo(na_janela), comparacao(na_janela)
    return {
        "saiu": s["taxa"],
        "ficou": c["taxa"],
        "saiu_detalhe": s,
        "ficou_detalhe": c,
        "pessoas_saiu": int(saiu["id"].nunique()),
        "pessoas_ficou": c["pessoas"],
        "por_tipo": por_tipo,
        "curva": curva.reset_index(),
    }


# ---------------------------------------------------------------- custo

def cenario_custo(premissas_custo: dict, nome: str) -> dict:
    """Premissas de um cenário da análise de sensibilidade.

    "medio" usa os valores de [custo]; "baixo" e "alto" trocam só os itens de [custo.cenarios.<nome>].
    """
    base = {k: v for k, v in premissas_custo.items() if k != "cenarios"}
    if nome == "medio":
        return base
    return {**base, **premissas_custo["cenarios"][nome]}


def custo_por_saida(pessoa, premissas_custo: dict, salario_por_cargo: dict) -> dict:
    """Custo de uma saída em três partes: rescisão, reposição e tempo até a pessoa nova render.

    O salário é o do cargo (config/premissas.toml, [salario_por_cargo]); a base não tem salário individual.
    Entra só o que existe por causa da saída: férias e 13º proporcionais seriam pagos de qualquer forma.
    """
    c = premissas_custo
    salario = float(salario_por_cargo[pessoa["cargo"]])
    dias_casa = (pessoa["data_desligamento"] - pessoa["data_admissao"]).days
    rescisao = c["custo_administrativo_desligamento"]
    if pessoa["tipo_desligamento"] == EMPRESA and dias_casa >= c["dias_experiencia"]:
        anos = dias_casa // 365
        dias_aviso = min(c["aviso_previo_dias_base"] + c["aviso_previo_dias_por_ano"] * anos,
                         c["aviso_previo_dias_maximo"])
        aviso = salario / 30 * dias_aviso
        saldo_fgts = c["deposito_fgts_mensal"] * salario * (dias_casa / 30)
        rescisao += aviso + c["multa_fgts"] * saldo_fgts
    reposicao = c["custo_recrutamento"] + c["custo_admissao"] + c["custo_treinamento"]
    rampa = salario * (1 + c["encargos_sobre_salario"]) * sum(1 - p for p in c["produtividade_mes"])
    return {"salario": salario, "rescisao": rescisao, "reposicao": reposicao, "rampa": rampa,
            "total": rescisao + reposicao + rampa}


def custo_rotatividade(pessoas: pd.DataFrame, premissas_custo: dict, salario_por_cargo: dict, inicio, fim) -> pd.DataFrame:
    """Uma linha por saída no período, com o salário do cargo e o custo de cada parte."""
    inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    s = pessoas[pessoas["data_desligamento"].between(inicio, fim)].copy()
    partes = s.apply(lambda p: pd.Series(custo_por_saida(p, premissas_custo, salario_por_cargo)), axis=1)
    if partes.empty:
        partes = pd.DataFrame(columns=["salario", "rescisao", "reposicao", "rampa", "total"])
    return pd.concat([s, partes], axis=1)


def sensibilidade_custo(pessoas: pd.DataFrame, premissas_custo: dict, salario_por_cargo: dict, inicio, fim) -> pd.DataFrame:
    """Custo total e por saída nos cenários baixo, médio e alto."""
    linhas = []
    for nome in ("baixo", "medio", "alto"):
        c = custo_rotatividade(pessoas, cenario_custo(premissas_custo, nome), salario_por_cargo, inicio, fim)
        linhas.append({"cenario": nome, "saidas": len(c), "total": float(c["total"].sum()),
                       "por_saida": float(c["total"].mean()) if len(c) else 0.0,
                       "rescisao": float(c["rescisao"].sum()), "reposicao": float(c["reposicao"].sum()),
                       "rampa": float(c["rampa"].sum())})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------- índice de risco

# Componente do índice: (peso, referência que vale 1) em config/premissas.toml, seção [indice]
COMPONENTES = {
    "rotatividade_12m": ("peso_rotatividade_12m", "referencia_rotatividade_12m"),
    "saida_90_dias": ("peso_saida_90_dias", "referencia_saida_90_dias"),
    "absenteismo_6m": ("peso_absenteismo_6m", "referencia_absenteismo_6m"),
}


# Base de cada componente: quantas pessoas sustentam a taxa do grupo
BASE_DO_COMPONENTE = {"rotatividade_12m": "pessoas_12m", "saida_90_dias": "admitidos_90_dias", "absenteismo_6m": "pessoas_12m"}


def indice_risco(fatores: pd.DataFrame, premissas_indice: dict, base_minima: int) -> pd.DataFrame:
    """Índice de risco por grupo (líder ou área), de 0 a 1, sem modelo de previsão.

    fatores: uma linha por grupo, com pessoas_12m, admitidos_90_dias e as colunas de COMPONENTES.
    Cada componente = valor do grupo / referência, limitado a 1. Contribuição = peso usado x componente.
    Índice = soma das contribuições. Os pesos usados somam 1, então o índice também fica entre 0 e 1.

    Regra de base pequena, sem valor imputado:
    * grupo com menos de base_minima pessoas nos últimos 12 meses não recebe índice (fica vazio);
    * componente cuja base tem menos de base_minima pessoas (por exemplo, menos de 5 admissões no
      componente dos 90 dias) sai da conta, e os pesos dos componentes restantes são redistribuídos
      proporcionalmente (0,40 e 0,30 viram 0,57 e 0,43). A coluna componentes_usados diz quantos entraram.
    """
    p = premissas_indice
    soma_pesos = sum(p[peso] for peso, _ in COMPONENTES.values())
    if abs(soma_pesos - 1) > 1e-9:
        raise ValueError(f"Os pesos do índice precisam somar 1, mas somam {soma_pesos}")
    out = fatores.copy()
    out["base_insuficiente"] = out["pessoas_12m"] < base_minima
    tem = {c: out[BASE_DO_COMPONENTE[c]] >= base_minima for c in COMPONENTES}
    peso_disponivel = sum(p[COMPONENTES[c][0]] * tem[c] for c in COMPONENTES)
    out["componentes_usados"] = sum(tem[c].astype(int) for c in COMPONENTES)
    out["indice"] = 0.0
    for comp, (peso, referencia) in COMPONENTES.items():
        componente = (out[comp].fillna(0.0) / p[referencia]).clip(lower=0.0, upper=1.0)
        peso_usado = (p[peso] / peso_disponivel).where(tem[comp])
        out[f"comp_{comp}"] = componente.where(tem[comp])
        out[f"peso_{comp}"] = peso_usado
        out[f"contrib_{comp}"] = peso_usado * componente
        out["indice"] += out[f"contrib_{comp}"].fillna(0.0)
    vazias = (["indice"] + [f"comp_{c}" for c in COMPONENTES] + [f"peso_{c}" for c in COMPONENTES]
              + [f"contrib_{c}" for c in COMPONENTES])
    out.loc[out["base_insuficiente"], vazias] = np.nan
    return out.sort_values("indice", ascending=False, na_position="last").reset_index(drop=True)


def pessoas_no_periodo(pessoas: pd.DataFrame, inicio, fim, por: list[str] | None = None) -> pd.DataFrame:
    """Quantas pessoas diferentes estiveram no quadro em algum dia entre inicio e fim."""
    inicio, fim = pd.Timestamp(inicio), pd.Timestamp(fim)
    passou = (pessoas["data_admissao"] <= fim) & (pessoas["data_desligamento"].isna() | (pessoas["data_desligamento"] >= inicio))
    df = pessoas[passou]
    if por:
        return df.groupby(por)["id"].nunique().rename("pessoas").reset_index()
    return pd.DataFrame({"pessoas": [df["id"].nunique()]})


def fatores_por_grupo(pessoas: pd.DataFrame, faltas: pd.DataFrame, meses: pd.PeriodIndex,
                      por: list[str] | None) -> pd.DataFrame:
    """Monta os três componentes do índice para cada grupo (ou para a rede, com por=None):
    rotatividade anual dos últimos 12 meses, saída em 90 dias no período todo
    e absenteísmo dos últimos 6 meses, com os números absolutos de cada um."""
    ultimos_12 = meses[-12:]
    ultimos_6 = [str(m) for m in meses[-6:]]
    fim = meses[-1].end_time.normalize()
    rot = rotatividade_anualizada(rotatividade_mensal(pessoas, ultimos_12, por), por)
    s90 = saida_90_dias(pessoas, meses[0].start_time, fim, por)
    ab = absenteismo(faltas, pessoas, por, ultimos_6)
    pes = pessoas_no_periodo(pessoas, ultimos_12[0].start_time, fim, por)
    rot = rot.rename(columns={"saidas": "saidas_12m", "quadro_medio": "quadro_medio_12m"})
    ab = ab.rename(columns={"faltas": "faltas_6m", "dias_previstos": "dias_previstos_6m"})
    s90 = s90.rename(columns={"admitidos": "admitidos_90_dias", "sairam_90_dias": "sairam_90_dias"})
    colunas_rot = ["taxa_anual", "saidas_12m", "quadro_medio_12m"]
    colunas_s90 = ["admitidos_90_dias", "sairam_90_dias", "taxa_90_dias"]
    colunas_ab = ["absenteismo", "faltas_6m", "dias_previstos_6m"]
    if por:
        out = pes.merge(rot[por + colunas_rot], on=por, how="left")
        out = out.merge(s90[por + colunas_s90], on=por, how="left")
        out = out.merge(ab[por + colunas_ab], on=por, how="left")
    else:
        out = pd.concat([pes, rot[colunas_rot].reset_index(drop=True), s90[colunas_s90].reset_index(drop=True),
                         ab[colunas_ab].reset_index(drop=True)], axis=1)
    out = out.rename(columns={"pessoas": "pessoas_12m"})
    for col in ("admitidos_90_dias", "sairam_90_dias", "saidas_12m", "faltas_6m", "dias_previstos_6m"):
        out[col] = out[col].fillna(0).astype(int)
    return out.rename(columns={"taxa_anual": "rotatividade_12m", "taxa_90_dias": "saida_90_dias",
                               "absenteismo": "absenteismo_6m"})
