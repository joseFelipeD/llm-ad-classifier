# Registro de experimentos

**Nenhum experimento com API foi executado até agora.** Esta página lista os
experimentos planejados e os comandos exatos; os resultados só serão preenchidos com
números reais (saída de `evaluate.py` e `usage.json`).

## Partições (geradas por `python scripts/make_split.py`, seed 42)

| arquivo | itens | uso |
|---|---|---|
| `splits/dev.jsonl` | 160 (20/classe) | desenvolvimento |
| `splits/fewshot_k3.jsonl` | 24 (3/classe, do dev) | pool de exemplos few-shot |
| `splits/fewshot_k1.jsonl` | 8 (1/classe, subconjunto do k3) | few-shot mínimo |
| `splits/dev_eval.jsonl` | 136 (dev − pool k3) | **comparação entre variantes** |
| `splits/holdout.jsonl` | 40 (5/classe) | **uma única medição final**, configuração congelada |
| `synthetic/other_sanity.jsonl` | 8 (sintéticos, escritos à mão) | sanidade de `other`; não entra em métricas reportadas |

Os exemplos few-shot foram sorteados (seed), não escolhidos a dedo. Todas as variantes
são comparadas no mesmo `dev_eval`, que não contém nenhum exemplo usado no prompt.

Limitação: com 40 itens, cada erro no holdout vale 2,5 p.p.; o intervalo de confiança é
largo (aprox. ±11 p.p. em torno de 85%).

## Tamanho do prompt de sistema (caracteres, medido offline)

| few-shot | json | lines |
|---|---|---|
| nenhum | 2093 | 2083 |
| k1 (8 ex.) | 2624 | 2614 |
| k3 (24 ex.) | 3587 | 3577 |

Tokens reais só serão conhecidos pelo `usage` da API.

## Experimentos planejados

Modelo base: `openai/gpt-oss-20b`, `--reasoning-effort low`, lote 20.

| id | hipótese | comando (saída em `runs/`) |
|---|---|---|
| E0 | smoke test: 1 chamada confirma auth, formato e se reasoning entra em `completion_tokens` | `python classify.py splits/fewshot_k1.jsonl --usage runs/e0_usage.json > runs/e0.jsonl` |
| E1 | baseline zero-shot, JSON estrito | `python classify.py splits/dev_eval.jsonl --usage runs/e1_usage.json > runs/e1.jsonl` |
| E2 | Gemini: formato `lines` reduz tokens de saída sem perder acurácia | `... --format lines --usage runs/e2_usage.json > runs/e2.jsonl` |
| E3 | Gemini: few-shot 1/classe | `... --examples splits/fewshot_k1.jsonl ...` |
| E4 | Gemini: few-shot 3/classe | `... --examples splits/fewshot_k3.jsonl ...` |
| E5 | Gemini: `other` sem few-shot de lixo (dados sintéticos) | `python classify.py synthetic/other_sanity.jsonl ...` |
| E6 | 120B vs 20B na melhor configuração | `... --model openai/gpt-oss-120b ...` |
| E7 | holdout final, uma vez | `python classify.py splits/holdout.jsonl ...` |

Avaliação: `python evaluate.py splits/dev_eval.jsonl runs/eN.jsonl runs/eN_usage.json`.

Consumo estimado (não medido): ~7 lotes por rodada do `dev_eval`; dentro dos limites
documentados do Groq (8K TPM / 200K TPD por modelo), a confirmar no painel da conta.

## Resultados

### E0 — smoke test (2026-10-13, autorizado: 1 chamada)

- Comando: `python scripts/smoke_test.py splits/fewshot_k3.jsonl --n 20 --out runs/e0`
  (caminho real do pipeline, `max_retries=0`, bloqueio de uma segunda chamada).
- Entrada: os 20 primeiros itens (por id) do pool `fewshot_k3`. Não toca no `dev_eval`.
- Modelo `openai/gpt-oss-20b`, `--format json` (JSON Schema estrito), `reasoning_effort=low`,
  `include_reasoning=false`, zero-shot, lote 20, `max_completion_tokens=2048`.
- Resultado: 1 requisição HTTP, status 200, `finish_reason=stop`, JSON válido no schema,
  20/20 itens com label válido, nenhuma retentativa.
- `usage` real: `prompt_tokens=916`, `completion_tokens=364`, `total_tokens=1280`,
  `completion_tokens_details.reasoning_tokens=177`. Média de **64,0 tokens/item**.
- `usage_exact: true` (1 resposta com usage, 0 falhas de transporte).
- Headers: `x-ratelimit-limit-requests=1000` (por dia), `x-ratelimit-limit-tokens=8000`
  (por minuto). Isso confirma os limites documentados para esta conta.
- `evaluate.py` sobre esses 20 itens: 20/20. **Não é estimativa de acurácia**: são só 20
  itens do pool de exemplos, com classes desbalanceadas (food_beverage 1, fashion 2...).
- Reasoning: 364 − 177 = 187 tokens visíveis, o que bate com o tamanho do JSON de 20
  entradas. Isso indica que `reasoning_tokens` é um detalhamento **contido** em
  `completion_tokens`, que é o único campo que somamos (sem contagem dupla). Inferência
  pela aritmética; a documentação do Groq não declara isso explicitamente.
- Arquivos locais, **não versionados** (`runs/` está no `.gitignore`):
  `runs/e0_usage.json`, `runs/e0_response.json` (resposta bruta e headers de rate
  limit), `runs/e0.jsonl`, `runs/e0_gold.jsonl`. Os números acima são o resumo desses
  arquivos, e o comando acima os reproduz (com variação, porque o modelo não é
  determinístico).
- Decisão: `reasoning_effort=low` mantido como padrão; folga de ~6× no orçamento.
