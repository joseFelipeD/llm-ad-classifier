# Classificador de anúncios com LLM

Classifica títulos de anúncios (multilíngues) em 9 categorias com o modelo
`openai/gpt-oss-20b` via API do Groq. Usa lotes de 20 anúncios por chamada, JSON Schema
estrito, prompt zero-shot com o guia de desempates e tratamento explícito de falhas.

> O enunciado original do desafio está em [`ENUNCIADO_ORIGINAL.md`](ENUNCIADO_ORIGINAL.md).
> Decisões e relato do processo: [`DECISIONS.md`](DECISIONS.md). Experimentos:
> [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md).

| validação (partições do treino) | n | acurácia | macro-F1 | tokens/item |
|---|---|---|---|---|
| `dev_eval` (escolha da configuração) | 136 | 98,5% | 0,985 | 70,6 |
| `holdout` (uso único, configuração congelada) | 40 | 97,5% | 0,975 | 69,5 |

> **Estado: concluído.** [`predictions.jsonl`](predictions.jsonl) e [`usage.json`](usage.json)
> foram gerados em 2026-10-16, numa única execução bem-sucedida sobre os 100 anúncios de
> teste: 100 predições, 7 requisições, **75,6 tokens/item** (5.296 entrada + 2.266 saída).
> `usage_exact: false`: uma tentativa rejeitada com HTTP 400 (JSON fora do schema) não
> informou `usage`. A média é um piso; o pior caso calculado é ≤ ~107 tokens/item (ver
> [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md)). A acurácia no teste é desconhecida
> (sem gabarito).

## Requisitos

- Python 3 (desenvolvido e testado com 3.14.5). **Nenhuma dependência externa**: só a
  biblioteca padrão (`urllib`, `unittest`).
- Uma chave de API do Groq (há plano gratuito). A empresa não fornece chave.

## Configurar a chave do Groq

1. Crie uma conta em <https://console.groq.com> e gere uma chave em **API Keys**.
2. Copie o modelo e preencha a chave. O `.env` é ignorado pelo Git:
   ```
   cp .env.example .env        # Windows PowerShell: Copy-Item .env.example .env
   # edite .env: GROQ_API_KEY=<sua chave>
   ```
   Alternativa: defina a variável de ambiente `GROQ_API_KEY`. Ela tem prioridade sobre o
   `.env`, que é lido do diretório atual.

Limites do plano gratuito observados nesta conta (headers da API): 1.000 requisições/dia
e 8.000 tokens/minuto para o `gpt-oss-20b`. O padrão `--tpm-limit 6000` fica abaixo disso.

## Executar

```
python classify.py data/test_unlabeled.jsonl --usage usage.json > predictions.jsonl
```

- **stdout:** só JSONL `{"id": ..., "label": ...}`, na ordem da entrada.
- **stderr:** logs, progresso e erros.
- **`usage.json`:** consumo real somado de todas as respostas da API, inclusive
  retentativas:
  - campos exigidos: `items`, `input_tokens`, `output_tokens`, `avg_tokens_per_item`,
    `model`;
  - campos extras de diagnóstico: `complete`, `usage_exact`, `http_attempts`,
    `reasoning_tokens_included_in_output` (já contido em `output_tokens`), hash do
    prompt, entre outros.

| código de saída | significado |
|---|---|
| 0 | todos os itens classificados |
| 1 | execução incompleta: algum item ficou sem label. **O stdout fica vazio**; as falhas vão para o stderr e para `--failures`, as predições obtidas para `--partial` |
| 2 | erro de entrada, de argumento ou de configuração (ex.: sem chave), erro fatal da API (401/403/404) ou falhas seguidas (circuit breaker) |

Opções úteis (`python classify.py -h` lista todas):

| opção | padrão | para quê |
|---|---|---|
| `--batch-size` | 20 | anúncios por chamada |
| `--format json\|lines` | `json` | JSON Schema estrito, ou texto `<n>\|<label>` (experimental) |
| `--reasoning-effort` | `low` | esforço de raciocínio do GPT-OSS |
| `--tpm-limit` | 6000 | ritmo: tokens por minuto a não ultrapassar (0 desliga) |
| `--max-total-tokens` | — | teto operacional (best-effort: usa estimativa da próxima chamada) |
| `--call-log` | — | JSONL com um registro por requisição HTTP, inclusive falhas e 429 |
| `--failures` / `--partial` | — | itens sem label / predições parciais numa execução incompleta |

## Medir no treino

```
python scripts/make_split.py          # gera splits/ (já versionado; determinístico, seed 42)
mkdir runs                            # saídas locais (ignoradas pelo Git)
python classify.py splits/dev_eval.jsonl --usage runs/dev_usage.json > runs/dev.jsonl
python evaluate.py splits/dev_eval.jsonl runs/dev.jsonl runs/dev_usage.json
```

O campo `label` das partições é ignorado na entrada e nunca enviado ao modelo.

## Testes

```
python -m unittest discover -s tests
```

São 78 testes offline, sem rede: cliente falso, transporte HTTP falso e relógio falso.
Cobrem:
- leitura e validação da entrada, montagem do prompt e parsing da resposta;
- retentativas (429 com `retry-after`, 5xx, timeout, leitura incompleta) e ritmo por
  tokens/minuto e headers de rate limit;
- contabilidade de tokens e reenvio de itens faltantes;
- circuit breaker, códigos de saída e um subprocesso real de `classify.py`.

## Comportamento em falhas

Nenhuma falha vira rótulo silenciosamente.

| situação | o que acontece |
|---|---|
| texto vazio ou só espaços | `other` sem chamar a API (regra literal do enunciado). HTML, lorem ipsum e lixo vão ao LLM |
| JSON malformado, label fora da lista, item ausente ou duplicado com labels diferentes | só os itens sem label válido são reenviados; lote sem nada aproveitável é dividido ao meio; item isolado: 2 tentativas; depois disso, falha |
| 429, 408, 5xx, timeout, erro de rede ou de leitura | até 4 retentativas (respeita `retry-after`, ou backoff exponencial até 60 s); `retry-after` > 60 s desiste na hora |
| ritmo | antes de cada chamada, estima o consumo (anterior + 20%) e espera se a janela local de 60 s ou os headers `x-ratelimit-remaining/reset-tokens` indicarem falta de tokens |
| 4 chamadas seguidas sem nenhum label válido | aborta (exit 2) em vez de repetir o erro em todos os lotes |
| 401 / 403 / 404 | aborta (exit 2) |
| entrada inválida (JSON, id ausente ou duplicado, sem `text`) ou argumento inválido | aborta antes de chamar a API (exit 2) |
| consumo de tokens desconhecido (resposta sem `usage`, timeout, erro 400/5xx sem `usage`) | não é estimado; `usage_exact: false` no `usage.json` |

## Limitações conhecidas

- **`usage_exact: false`** significa que o consumo total efetivo **não pôde ser
  comprovado**: alguma resposta veio sem `usage` válido, ou houve timeout ou erro de rede
  (o servidor pode ter processado o pedido). A soma reportada é então um piso, não o
  total.
- **401/403/404/429 sem `usage` são contados como consumo zero.** É uma convenção
  operacional (rejeições antes da geração); a API não confirma isso explicitamente.
- **Rate limit com reset longo:** o prazo de reset informado pelos headers é limitado ao
  teto operacional de espera (60 s). Se o servidor indicar um reset maior, o cliente pode
  voltar a chamar antes do fim do prazo. Nesse caso, o 429 seguinte é tratado por
  `retry-after`; se `retry-after` passar de 60 s, o lote falha sem novas tentativas e a
  execução termina incompleta (exit 1), ou abortada (exit 2) se o circuit breaker
  disparar.
- **O teto `--max-total-tokens` é best-effort:** usa a chamada anterior + 20% como
  estimativa, e uma chamada maior que a estimada pode ultrapassá-lo.

## Estrutura

```
classify.py              CLI
classifier/
  labels.py              os 9 rótulos
  dataset.py             leitura e validação do JSONL
  prompt.py              prompt (categorias + guia de desempates) e JSON Schema
  parsing.py             validação da resposta do modelo
  client.py              HTTP (urllib), retentativas, ritmo e contagem de tokens
  pipeline.py            lotes, reenvio de itens faltantes e circuit breaker
scripts/make_split.py    partições derivadas do treino (dev/holdout/few-shot)
scripts/smoke_test.py    teste com no máximo 1 chamada à API
splits/, synthetic/      partições derivadas e 8 entradas sintéticas de `other`
tests/                   testes offline
evaluate.py, data/       fornecidos pelo desafio, sem alterações
```
