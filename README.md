# Classificador de anúncios com LLM

Classificador de títulos de anúncios em 9 categorias (`finance`, `automotive`, `health`,
`travel`, `technology`, `food_beverage`, `fashion`, `entertainment` e `other`) usando um
LLM via API. Os títulos podem estar em vários idiomas, e as categorias seguem um guia de
desempates (seguros, financiamento, eletrônicos, beleza, cursos etc.).

O projeto foi desenvolvido para um desafio técnico. As metas eram acurácia ≥ 85% no teste
oculto, custo médio ≤ 400 tokens por item, medido pelo `usage` da API, e tratamento
explícito de falhas. O enunciado completo está em
[`ENUNCIADO_ORIGINAL.md`](ENUNCIADO_ORIGINAL.md).

## Funcionalidades

- Classificação em lotes de 20 anúncios por chamada, com saída restrita por JSON Schema
  (`enum` com os 9 rótulos).
- Contagem de tokens a partir do `usage` real de cada resposta, inclusive retentativas,
  gravada em `usage.json`.
- Retentativas para 429, 5xx, timeout e erros de rede, com controle de ritmo por tokens
  por minuto.
- Reenvio apenas dos itens que voltaram sem rótulo válido. Nenhuma falha vira rótulo
  silenciosamente.
- `stdout` contém só o JSONL de predições; logs e erros vão para `stderr`.
- 78 testes automatizados offline.

## Tecnologias

- Python, somente a biblioteca padrão (`urllib`, `json`, `unittest`). Não há
  dependências externas.
- API do [Groq](https://console.groq.com), modelo `openai/gpt-oss-20b`, com
  `reasoning_effort=low`.

## Arquitetura

1. `classify.py` (CLI) lê a entrada com `dataset.py`, que valida o JSONL e os ids.
2. `pipeline.py` divide os itens em lotes, monta as mensagens com `prompt.py`
   (instruções + JSON Schema) e as envia por `client.py` (HTTP, retentativas, ritmo e
   contagem de `usage`).
3. `parsing.py` valida cada resposta; itens sem label válido voltam para o pipeline e
   são reenviados.
4. A CLI escreve as predições no stdout e o consumo em `usage.json`; logs vão para o
   stderr.

- Prompt zero-shot com as definições das categorias e o guia de desempates do enunciado.
- Dentro de cada lote, os anúncios são numerados de 1 a N; o modelo não recebe os ids
  originais.
- Texto vazio ou só com espaços é classificado como `other` sem chamar a API, conforme o
  enunciado. HTML, lorem ipsum e outros textos ilegíveis são enviados ao modelo.

## Resultados

Medidos com o `evaluate.py` fornecido, em partições estratificadas do treino (seed 42):

| conjunto | n | acurácia | macro-F1 | tokens/item |
|---|---|---|---|---|
| `dev_eval` (escolha da configuração) | 136 | 98,5% | 0,985 | 70,6 |
| `holdout` (uso único, configuração congelada) | 40 | 97,5% | 0,975 | 69,5 |
| teste (100 anúncios, entrega) | 100 | desconhecida (sem gabarito) | — | 75,6 |

- A execução final gerou [`predictions.jsonl`](predictions.jsonl) e [`usage.json`](usage.json)
  em 2026-10-16: 100 predições e 7 requisições, com 5.296 tokens de entrada e 2.266 de
  saída.
- `usage_exact` é `false` porque uma tentativa rejeitada com HTTP 400 não informou `usage`.
  Assim, 75,6 tokens/item é um piso. O pior caso calculado fica em torno de 107
  tokens/item.
- Com 40 itens no holdout, cada erro vale 2,5 p.p.; a estimativa tem margem larga.

Detalhes de cada experimento: [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md).

## Requisitos

- Python 3. O projeto foi desenvolvido e testado com Python 3.14.5.
- Uma chave de API do Groq. O plano gratuito foi suficiente para todo o desenvolvimento.

Não é preciso instalar pacotes.

## Configuração da chave do Groq

1. Crie uma conta em <https://console.groq.com> e gere uma chave em **API Keys**.
2. Crie o arquivo `.env` a partir do modelo e preencha `GROQ_API_KEY`:
   ```
   cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
   ```
   O `.env` é lido do diretório atual e está no `.gitignore`. Se preferir, defina a
   variável de ambiente `GROQ_API_KEY`, que tem prioridade sobre o `.env`.

Limites do plano gratuito observados nos headers da API durante o desenvolvimento:
1.000 requisições/dia e 8.000 tokens/minuto para o `gpt-oss-20b`. O padrão
`--tpm-limit 6000` fica abaixo desse limite.

## Execução

Na raiz do repositório:

```
python classify.py data/test_unlabeled.jsonl --usage usage.json > predictions.jsonl
```

O comando gera `predictions.jsonl` (uma linha `{"id": ..., "label": ...}` por anúncio, na
ordem da entrada) e `usage.json` (`items`, `input_tokens`, `output_tokens`,
`avg_tokens_per_item`, `model` e campos extras de diagnóstico). Os arquivos versionados
são os da execução final; rodar de novo os sobrescreve, e o resultado pode variar, porque
o modelo não é determinístico.

| código de saída | significado |
|---|---|
| 0 | todos os itens classificados |
| 1 | execução incompleta: algum item ficou sem label. O stdout fica vazio; as falhas vão para o stderr e para `--failures`, e as predições obtidas, para `--partial` |
| 2 | erro de entrada, de argumento ou de configuração (ex.: sem chave), erro fatal da API (401/403/404) ou falhas seguidas (circuit breaker) |

Opções úteis (`python classify.py -h` lista todas):

| opção | padrão | para quê |
|---|---|---|
| `--batch-size` | 20 | anúncios por chamada |
| `--format json\|lines` | `json` | JSON Schema estrito, ou texto `<n>\|<label>` (experimental) |
| `--reasoning-effort` | `low` | esforço de raciocínio do GPT-OSS |
| `--tpm-limit` | 6000 | tokens por minuto a não ultrapassar (0 desliga) |
| `--max-total-tokens` | — | teto de consumo da execução (best-effort) |
| `--call-log` | — | JSONL com um registro por requisição HTTP, inclusive falhas e 429 |
| `--failures` / `--partial` | — | itens sem label / predições parciais numa execução incompleta |

### Medir no treino

```
python scripts/make_split.py          # recria splits/ (já versionado; determinístico, seed 42)
mkdir runs                            # saídas locais, ignoradas pelo Git
python classify.py splits/dev_eval.jsonl --usage runs/dev_usage.json > runs/dev.jsonl
python evaluate.py splits/dev_eval.jsonl runs/dev.jsonl runs/dev_usage.json
```

O campo `label` das partições é ignorado na entrada e nunca é enviado ao modelo.

## Testes

```
python -m unittest discover -s tests
```

São 78 testes offline, sem rede, com cliente, transporte HTTP e relógio falsos. Eles
cobrem leitura e validação da entrada, montagem do prompt, parsing da resposta,
retentativas (429 com `retry-after`, 5xx, timeout, leitura incompleta), controle de
ritmo, contabilidade de tokens, reenvio de itens faltantes, circuit breaker, códigos de
saída e uma execução real de `classify.py` em subprocesso.

## Comportamento em falhas

| situação | o que acontece |
|---|---|
| texto vazio ou só espaços | `other` sem chamar a API |
| JSON malformado, label fora da lista, item ausente ou duplicado com labels diferentes | só os itens sem label válido são reenviados; um lote sem nada aproveitável é dividido ao meio; um item isolado tem 2 tentativas; depois disso, falha |
| 429, 408, 5xx, timeout, erro de rede ou de leitura | até 4 retentativas (respeita `retry-after`, ou backoff exponencial até 60 s); `retry-after` acima de 60 s faz o lote desistir na hora |
| 4 chamadas seguidas sem nenhum label válido | aborta (exit 2) |
| 401 / 403 / 404 | aborta (exit 2) |
| entrada inválida (JSON, id ausente ou duplicado, sem `text`) ou argumento inválido | aborta antes de chamar a API (exit 2) |
| resposta sem `usage`, timeout ou erro sem `usage` | o consumo não é estimado; `usage.json` registra `usage_exact: false` |

## Estrutura do repositório

```
classify.py              CLI
classifier/
  labels.py              os 9 rótulos
  dataset.py             leitura e validação do JSONL
  prompt.py              prompt (categorias + guia de desempates) e JSON Schema
  parsing.py             validação da resposta do modelo
  client.py              HTTP (urllib), retentativas, ritmo e contagem de tokens
  pipeline.py            lotes, reenvio de itens faltantes e circuit breaker
tests/                   testes offline
scripts/make_split.py    gera as partições derivadas do treino
scripts/smoke_test.py    teste com no máximo 1 chamada à API (usado nos experimentos E0 e E5)
splits/                  partições do treino: dev_eval, holdout e pools few-shot
synthetic/               8 entradas sintéticas de `other` (teste de sanidade)
data/, evaluate.py       fornecidos pelo desafio, sem alterações
predictions.jsonl        predições da execução final
usage.json               consumo de tokens da execução final
docs/                    registro de experimentos e revisão do Gemini
AGENTS.md, CLAUDE.md,    instruções e agentes usados com as ferramentas de IA
.claude/, prompts/       (ver abaixo)
```

## Limitações

- **Consumo inexato:** com `usage_exact: false`, o total reportado é um piso. Isso ocorre
  quando alguma resposta vem sem `usage` ou há timeout depois que o servidor já
  processou o pedido.
- **Rejeições sem `usage`** (401/403/404/429) são contadas como consumo zero. É uma
  convenção operacional; a API não confirma isso explicitamente.
- **Reset longo de rate limit:** o prazo de reset lido nos headers é limitado a 60 s. Se o
  servidor indicar um prazo maior, o cliente pode voltar a chamar antes do fim dele; o
  429 seguinte é tratado por `retry-after`, e, se este passar de 60 s, o lote falha e a
  execução termina incompleta (exit 1), ou abortada (exit 2) se o circuit breaker
  disparar.
- **`--max-total-tokens` é best-effort:** a estimativa usa a chamada anterior + 20%, e uma
  chamada maior pode ultrapassar o teto.
- **`other` não foi medido em dados reais:** o treino não tem exemplos dessa categoria;
  só houve um teste de sanidade com 8 entradas sintéticas.
- Cada configuração foi executada uma vez, e o modelo não é determinístico.

## Uso de ferramentas de IA

O enunciado avalia também como as ferramentas de IA foram usadas. Os arquivos abaixo
foram mantidos como registro desse processo; não são necessários para executar o
classificador.

- [`AGENTS.md`](AGENTS.md) e [`CLAUDE.md`](CLAUDE.md): regras comuns dadas aos assistentes
  (papéis, restrições de dados e segredos, aprovação antes de commits e gastos de API).
- [`.claude/`](.claude): subagentes de auditoria somente leitura (`auditor-dados`,
  `auditor-robustez`) e a skill `auditar-entrega`, usados com o Claude Code.
- [`prompts/`](prompts): prompts usados em cada etapa, na ordem: diagnóstico (01),
  análise do plano pelo Gemini (06–07), baseline (02), revisão do Codex (05),
  experimentos (03), segunda revisão do Codex (08) e finalização (04).
- [`docs/RECOMENDACOES_GEMINI.md`](docs/RECOMENDACOES_GEMINI.md): recomendações do
  Gemini sobre o plano.

O que foi aproveitado, rejeitado ou corrigido está em [`DECISIONS.md`](DECISIONS.md).

## Documentação

- [`DECISIONS.md`](DECISIONS.md): decisões, abordagens descartadas e onde a IA ajudou ou
  errou.
- [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md): comandos, métricas e custo de cada
  experimento.
- [`ENUNCIADO_ORIGINAL.md`](ENUNCIADO_ORIGINAL.md): enunciado do desafio.
