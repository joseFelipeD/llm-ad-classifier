# Classificador de anúncios com LLM

Classifica títulos de anúncios, em vários idiomas, em 9 categorias (`finance`,
`automotive`, `health`, `travel`, `technology`, `food_beverage`, `fashion`,
`entertainment` e `other`), seguindo o guia de desempates do
[enunciado](ENUNCIADO_ORIGINAL.md). As metas eram acurácia ≥ 85% no teste oculto, custo
médio ≤ 400 tokens por item, medido pelo `usage` da API, e tratamento explícito de falhas.

Usa o modelo `openai/gpt-oss-20b` via API do Groq, com prompt zero-shot, lotes de 20
anúncios e saída restrita por JSON Schema. É escrito em Python, só com a biblioteca
padrão.

## Resultados

Medidos com o `evaluate.py` fornecido, em partições estratificadas do treino (seed 42):

| conjunto | n | acurácia | macro-F1 | tokens/item |
|---|---|---|---|---|
| `dev_eval` (escolha da configuração) | 136 | 98,5% | 0,985 | 70,6 |
| `holdout` (uso único, configuração congelada) | 40 | 97,5% | 0,975 | 69,5 |
| teste (entrega) | 100 | desconhecida (sem gabarito) | — | 75,6 |

[`predictions.jsonl`](predictions.jsonl) e [`usage.json`](usage.json) vêm da execução
final, de 2026-10-16. Uma tentativa rejeitada com HTTP 400 não informou `usage`
(`usage_exact: false`); por isso, 75,6 tokens/item é um piso. O pior caso calculado é
de cerca de 107.

## Como executar

Requisitos: Python 3 (testado com 3.14.5) e uma chave de API do Groq. O plano gratuito
foi suficiente para todo o desenvolvimento. Não há pacotes a instalar.

1. Gere uma chave em <https://console.groq.com> (**API Keys**).
2. Crie o `.env` e preencha `GROQ_API_KEY`. O arquivo está no `.gitignore`; a variável
   de ambiente `GROQ_API_KEY`, se definida, tem prioridade.
   ```
   cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
   ```
3. Na raiz do repositório:
   ```
   python classify.py data/test_unlabeled.jsonl --usage usage.json > predictions.jsonl
   ```

O stdout recebe só as predições em JSONL, na ordem da entrada; logs e erros vão para o
stderr. Rodar de novo sobrescreve os arquivos da entrega, e o resultado pode variar,
porque o modelo não é determinístico. Opções (lote, formato, ritmo, logs):
`python classify.py -h`.

| código de saída | significado |
|---|---|
| 0 | todos os itens classificados |
| 1 | execução incompleta: o stdout fica vazio; as falhas vão para o stderr e para `--failures`, as predições obtidas para `--partial` |
| 2 | erro de entrada, argumento ou configuração, erro fatal da API (401/403/404) ou falhas seguidas (circuit breaker) |

Para medir no treino:

```
mkdir runs
python classify.py splits/dev_eval.jsonl --usage runs/dev_usage.json > runs/dev.jsonl
python evaluate.py splits/dev_eval.jsonl runs/dev.jsonl runs/dev_usage.json
```

## Testes

```
python -m unittest discover -s tests
```

São 78 testes offline, com cliente, transporte HTTP e relógio falsos. Eles cobrem
validação da entrada, prompt, parsing, retentativas, ritmo, contagem de tokens, circuit
breaker e a CLI em subprocesso.

## Comportamento em falhas

Nenhuma falha vira rótulo silenciosamente.

| situação | o que acontece |
|---|---|
| texto vazio ou só espaços | `other` sem chamar a API (regra do enunciado); textos ilegíveis vão ao modelo |
| JSON malformado, label fora da lista, item ausente ou duplicado com labels diferentes | só os itens sem label válido são reenviados; um lote sem nada aproveitável é dividido ao meio; um item isolado tem 2 tentativas; depois disso, falha |
| 429, 408, 5xx, timeout, erro de rede | até 4 retentativas (`retry-after` ou backoff exponencial até 60 s) |
| 4 chamadas seguidas sem nenhum label válido, ou 401/403/404 | aborta (exit 2) |
| entrada ou argumento inválido | aborta antes de chamar a API (exit 2) |
| resposta sem `usage` | o consumo não é estimado; `usage_exact: false` |

## Limitações

- O `other` não foi medido em dados reais, porque o treino não tem exemplos dessa
  categoria. Houve só um teste de sanidade com 8 entradas sintéticas.
- Cada configuração rodou uma vez, e o holdout tem 40 itens (cada erro vale 2,5 p.p.).
- Com `usage_exact: false`, o consumo reportado é um piso. Rejeições sem `usage`
  (401/403/404/429) contam como zero.
- A espera por rate limit é limitada a 60 s. Um reset mais longo pode deixar a execução
  incompleta (exit 1).

## Estrutura

```
classify.py            CLI
classifier/            labels, leitura da entrada, prompt e schema, parsing, cliente HTTP e pipeline
tests/                 testes offline
scripts/               geração das partições e smoke test (no máximo 1 chamada)
splits/, synthetic/    partições do treino e entradas sintéticas de `other`
data/, evaluate.py     fornecidos pelo desafio, sem alterações
docs/                  experimentos e revisão do Gemini
```

## Documentação e processo

- [`DECISIONS.md`](DECISIONS.md): decisões, abordagens descartadas e onde a IA ajudou ou
  errou.
- [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md): comandos, métricas e custo de cada
  experimento.
- Registro do uso de IA (não é necessário para executar):
  - [`AGENTS.md`](AGENTS.md) e [`CLAUDE.md`](CLAUDE.md): regras dadas aos assistentes;
  - [`.claude/`](.claude): subagentes de auditoria e skill do Claude Code;
  - [`prompts/`](prompts): prompts de cada etapa, na ordem 01 → 06/07 (Gemini) → 02 → 05
    (Codex) → 03 → 08 (Codex) → 04;
  - [`docs/RECOMENDACOES_GEMINI.md`](docs/RECOMENDACOES_GEMINI.md): revisão do plano
    pelo Gemini.
