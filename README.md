# Rotatividade em uma rede de lojas

Projeto de People Analytics com dados totalmente fictícios, de Daniela Matos
([LinkedIn](https://www.linkedin.com/in/danielamatosfreitas) · [capitalhumanointelligence.com](https://capitalhumanointelligence.com)).

**Relatório:** [https://danielamatosfreitas.github.io/people-analytics-rotatividade/](https://danielamatosfreitas.github.io/people-analytics-rotatividade/)  
**Report:** [https://danielamatosfreitas.github.io/people-analytics-rotatividade/](https://danielamatosfreitas.github.io/people-analytics-rotatividade/)

[Português](#português) · [English](#english)

> Todos os dados deste projeto são fictícios. A rede, as pessoas e os líderes não existem.
> All data in this project is fictitious. The store chain, the people and the team leaders do not exist.

## Português

### O problema

Em uma rede de lojas, cada saída custa dinheiro e tempo, mas esse custo fica espalhado: rescisão em um lugar, recrutamento em outro, a pessoa nova aprendendo devagar em um terceiro. Este projeto mostra como responder, com dados simples de RH, às perguntas que um dono ou uma diretoria de RH faz sobre rotatividade.

A base é uma rede fictícia com 3 unidades, 80 vagas e 24 meses (outubro de 2024 a setembro de 2026). Em cada pergunta, o relatório separa três blocos: **Fato** (o número), **Interpretação** (o que ele sugere) e **Hipótese** (o que precisaria ser verificado na vida real).

### As cinco perguntas

1. **Onde e quando as pessoas saem?** Por unidade, área e mês, separando pedido de demissão e desligamento pela empresa.
2. **Quantas saem nos primeiros 90 dias?** Quantas, em que áreas e qual o peso dessas saídas no total.
3. **A falta aumenta antes da saída?** Faltas nos 3 meses antes da saída comparadas com as de quem ficou, nos mesmos meses do calendário (grupo de comparação).
4. **Quanto custa a rotatividade?** Rescisão, reposição e tempo até a pessoa nova render, com premissas declaradas e análise de sensibilidade em três cenários (baixo, médio e alto).
5. **Onde abrir a conversa primeiro?** Índice de 0 a 1 por área e por líder, com componentes normalizados, pesos fixos e a contribuição de cada componente à vista, seguindo os três limites de base descritos em Ética e LGPD. Sem modelo de previsão e sem rótulo de pessoa.

### O que o método encontra (padrões plantados)

* **69 saídas em 24 meses**, rotatividade de 44% ao ano (69 saídas, quadro médio de 77,8); 61% (42 de 69) por pedido de demissão.
* **Caixa perde gente cedo:** 44% (7 de 16) dos admitidos saem antes de 90 dias; nas outras áreas somadas, 22% (10 de 46).
* **A falta sobe antes da saída:** nos 3 meses antes de sair, 3,8% (128 faltas em 3.354 dias previstos); quem ficou, nos mesmos meses, 1,3% (378 faltas em 30.031 dias previstos).
* **Custo:** R$ 472 mil em 24 meses no cenário médio, entre R$ 293 mil (baixo) e R$ 722 mil (alto).
* **Índice:** as equipes dos líderes L05 (0,72), L03 (0,61) e L04 (0,44) abrem a lista, cada uma puxada por um componente diferente.

Esses resultados reencontram o que foi colocado no gerador. O objetivo é demonstrar o método, não descobrir algo novo.

### Como os dados foram gerados

Os dados saem de `scripts/gerar_dados.py`, com semente fixa e todos os parâmetros em `config/premissas.toml`. Padrões embutidos de propósito:

* chance de saída maior nos primeiros 90 dias, muito maior em Caixa;
* mais saídas em janeiro e fevereiro e menos em novembro e dezembro (sazonalidade do comércio);
* uma equipe (líder L05) com mais faltas, mais saídas e quase só pedidos de demissão;
* faltas que sobem nos 3 meses antes da saída, mais antes de um pedido de demissão;
* reposição de cada vaga entre 10 e 40 dias depois da saída.

A base tem só código da pessoa (P0001...), unidade, área, cargo, líder (L01 a L10), datas de admissão e de desligamento, tipo de desligamento e a contagem de faltas por mês. Sem nome, sem salário individual (o custo usa o salário do cargo, declarado nas premissas) e sem motivo de falta.

### Ética e LGPD

* **Índice por área e por líder, nunca por pessoa.** O que se procura são condições de trabalho do grupo; um índice individual viraria previsão sobre alguém.
* **Regra de base mínima:** em grupo pequeno o percentual identifica a pessoa mesmo sem nome. Todo percentual vem com o número absoluto ao lado, e grupo com menos de 5 pessoas aparece "sem percentual". No índice valem três limites:
  * **sem índice:** grupo com menos de 5 pessoas;
  * **fora da conta:** com menos de 5 admissões, o componente dos 90 dias sai do cálculo e os pesos dos demais são redistribuídos na mesma proporção (0,40 e 0,30 viram 0,57 e 0,43), com a marcação "índice com 2 de 3 componentes";
  * **base pequena:** com menos de 10 pessoas ou de 10 admissões, o índice aparece, com leitura cautelosa (marcado com *).
* **Sem dados sensíveis** (Lei 13.709/2018, art. 5º, II): nada de saúde, origem racial, religião, opinião política, filiação sindical, vida sexual, dados genéticos ou biométricos. Faltas sem motivo, porque o motivo pode revelar saúde.
* **Limites de uso:** o índice serve para abrir conversa com a liderança e orientar ações de retenção, nunca para avaliação de desempenho, punição ou decisão sobre uma pessoa. Faltas entram como sinal do grupo; em nenhum caso o índice deve ser usado para cobrar presença de uma pessoa ou questionar atestado.

### Como rodar

Requer Python 3.11 ou mais recente.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Gerar os dados fictícios (semente fixa, sempre os mesmos dados):

```bash
python scripts/gerar_dados.py
```

Rodar os testes:

```bash
python -m pytest
```

Gerar o relatório em `docs/index.html`:

```bash
python scripts/gerar_relatorio.py
```

Para ver o relatório no computador, abra `docs/index.html` no navegador (os gráficos carregam o plotly pela internet).

Todas as premissas (geração dos dados, salário por cargo, custo e cenários, pesos do índice e base mínima) ficam em `config/premissas.toml`. Troque um valor e gere de novo.

### Como os testes funcionam

`python -m pytest` roda 32 testes, sem internet e em poucos segundos:

* **Dados** (`tests/test_dados.py`): a mesma semente gera exatamente os mesmos dados e o CSV incluído no repositório é igual ao gerado; nenhuma coluna sensível nem salário individual; os totais batem (quadro do mês anterior mais admissões menos saídas igual ao quadro do mês, em todos os meses, e a soma das áreas igual à rede).
* **Métricas** (`tests/test_metricas.py`): casos pequenos montados à mão, em que o resultado certo se confere de cabeça (rotatividade, 90 dias, faltas com grupo de comparação, custo e cenários). No índice: os componentes ponderados somam o índice, grupos com menos de 5 pessoas não recebem índice e componente sem base não entra (os pesos restantes somam 1).
* **Relatório** (`tests/test_relatorio.py`): percentual sempre com o número absoluto, "sem percentual" abaixo de 5, frase do asterisco com exatamente as equipes fora da base pequena, fim de cada barra do gráfico do índice igual ao índice, plotly por CDN e etiquetas de prévia (Open Graph) com a capa em endereço absoluto e no tamanho declarado.

### Estrutura

```
config/premissas.toml     premissas de geração, salário por cargo, custo, cenários e índice
scripts/gerar_dados.py    gera dados/pessoas.csv e dados/faltas_mensais.csv
scripts/gerar_relatorio.py  gera docs/index.html
scripts/gerar_capa.py     gera docs/capa.png, a imagem de prévia do link (precisa do Chrome)
analise/metricas.py       funções de cálculo (sem leitura de arquivo nem gráfico)
analise/relatorio.py      monta o HTML; o plotly vem por CDN
tests/                    testes dos dados, das métricas e do relatório
docs/index.html           relatório, pronto para o GitHub Pages
docs/capa.png             imagem de prévia do relatório em redes sociais (1200 x 630)
```

### Limitações

Dados fictícios com padrões plantados; equipes pequenas (5 a 14 vagas), sem significância estatística por equipe; um líder fixo por pessoa; salário do cargo sem reajustes; custo dependente das premissas; a comparação de faltas mostra associação, não causa.

### Autoria e licença

Daniela Matos · [LinkedIn](https://www.linkedin.com/in/danielamatosfreitas) · [capitalhumanointelligence.com](https://capitalhumanointelligence.com)

Licença MIT. Veja [LICENSE](LICENSE).

## English

### The problem

In a retail chain, every exit costs money and time, but that cost is scattered: severance in one place, recruiting in another, a new hire slowly getting up to speed in a third. This project shows how to answer, with simple HR data, the questions an owner or an HR director asks about turnover.

The data is a fictitious chain with 3 stores, 80 positions and 24 months (October 2024 to September 2026). The report is in Portuguese. For each question it separates three blocks: **Fact** (the number), **Interpretation** (what it suggests) and **Hypothesis** (what would need to be checked in real life).

### The five questions

1. **Where and when do people leave?** By store, area and month, splitting resignations from dismissals.
2. **How many leave in the first 90 days?** How many, in which areas and their share of all exits.
3. **Do absences rise before an exit?** Absences in the 3 months before leaving compared with people who stayed, in the same calendar months (comparison group).
4. **How much does turnover cost?** Severance, replacement and time to full productivity, with declared assumptions and a sensitivity analysis in three scenarios (low, medium, high).
5. **Where to start the conversation?** A 0 to 1 index by area and by team leader, with normalized components, fixed weights and each component's contribution in plain sight, following the three base limits described under Ethics and LGPD. No prediction model and no label on any person.

### What the method finds (planted patterns)

* **69 exits in 24 months**, 44% annual turnover (69 exits, average headcount 77.8); 61% (42 of 69) were resignations.
* **Cashiers leave early:** 44% (7 of 16) of new hires leave before 90 days; in the other areas combined, 22% (10 of 46).
* **Absences rise before an exit:** in the 3 months before leaving, 3.8% (128 absences in 3,354 scheduled days); people who stayed, same months, 1.3% (378 in 30,031).
* **Cost:** R$ 472 thousand in 24 months in the medium scenario, from R$ 293 thousand (low) to R$ 722 thousand (high).
* **Index:** the teams of leaders L05 (0.72), L03 (0.61) and L04 (0.44) top the list, each driven by a different component.

These results recover what was planted in the generator. The goal is to demonstrate the method, not to discover anything new.

### How the data was generated

`scripts/gerar_dados.py` generates the data with a fixed seed; every parameter lives in `config/premissas.toml`. Planted patterns: higher exit risk in the first 90 days (much higher for cashiers); more exits in January and February and fewer in November and December; one team (leader L05) with more absences, more exits and mostly resignations; absences rising in the 3 months before an exit, more before a resignation; each position refilled 10 to 40 days after the exit. People are identified only by code (P0001...), with no names, no individual salary (cost uses the salary per role declared in the assumptions) and no reason for absences.

### Ethics and LGPD (Brazil's data protection law)

* **Index by area and team leader, never by person.** The goal is to find group working conditions; an individual index would become a prediction about someone.
* **Minimum group size:** in a small group a percentage identifies the person even without a name. Every percentage comes with the absolute number next to it, and groups with fewer than 5 people show "sem percentual" (no percentage). The index has three limits:
  * **"sem índice" (no index):** group with fewer than 5 people;
  * **"fora da conta" (left out):** with fewer than 5 hires, the 90 day component is removed from the calculation and the other weights are scaled up in the same proportion (0.40 and 0.30 become 0.57 and 0.43), marked "índice com 2 de 3 componentes";
  * **"base pequena" (small base):** with fewer than 10 people or 10 hires, the index is shown but should be read with caution (marked with *).
* **No sensitive data** (Law 13,709/2018, art. 5, II): no health, racial origin, religion, political opinion, union membership, sex life, genetic or biometric data. Absences have no reason attached, since the reason can reveal health information.
* **Use limits:** the index is for opening a conversation with leadership and guiding retention actions, never for performance review, punishment or decisions about a specific person. Absences count as a group signal; under no circumstances should the index be used to press a person about attendance or to question a medical certificate.

### How to run

Requires Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/gerar_dados.py
python -m pytest
python scripts/gerar_relatorio.py
```

The first script generates the fictitious data (fixed seed), the second runs the tests and the third writes the report to `docs/index.html`; open that file in a browser to view it (charts load plotly from the internet). All assumptions live in `config/premissas.toml`.

### Tests

`python -m pytest` runs 32 tests, offline, in a few seconds: the same seed produces exactly the same data and the committed CSV matches it; no sensitive column and no individual salary; totals add up (previous month headcount plus hires minus exits equals the month's headcount, every month); weighted components add up to the index; groups with fewer than 5 people get no index; a component without base is left out and the remaining weights add up to 1; every percentage in the report comes with its absolute number; each bar in the index chart ends exactly at the index value; the asterisk note names exactly the teams outside the small base; the link preview tags point to the cover image by absolute URL and match its real size.

### Author and license

Daniela Matos · [LinkedIn](https://www.linkedin.com/in/danielamatosfreitas) · [capitalhumanointelligence.com](https://capitalhumanointelligence.com)

MIT. See [LICENSE](LICENSE).
