# Registro de experimentos

Todos os números desta página vêm de execuções reais (saída de `evaluate.py` e
`usage.json`). Os arquivos brutos de cada execução (`runs/`) ficam locais e não são
versionados. O teste oculto ainda não foi classificado.

## Partições (geradas por `python scripts/make_split.py`, seed 42)

| arquivo | itens | uso |
|---|---|---|
| `splits/dev.jsonl` | 160 (20/classe) | desenvolvimento |
| `splits/fewshot_k3.jsonl` | 24 (3/classe, do dev) | pool de exemplos few-shot (não usado no prompt final) |
| `splits/fewshot_k1.jsonl` | 8 (1/classe, subconjunto do k3) | few-shot mínimo (não usado) |
| `splits/dev_eval.jsonl` | 136 (dev − pool k3) | **comparação entre variantes** |
| `splits/holdout.jsonl` | 40 (5/classe) | **uma única medição final**, configuração congelada |
| `synthetic/other_sanity.jsonl` | 8 (sintéticos, escritos à mão) | sanidade de `other`; não entra em métricas reportadas |

Os exemplos few-shot foram sorteados (seed), não escolhidos a dedo. Todas as variantes
foram comparadas no mesmo `dev_eval`, que não contém nenhum exemplo do pool.

Limitação: com 40 itens, cada erro no holdout vale 2,5 p.p.; o intervalo de confiança é
largo (aprox. ±11 p.p. em torno de 85%).

## Tamanho do prompt de sistema (caracteres, medido offline)

| few-shot | json | lines |
|---|---|---|
| nenhum | 2093 | 2083 |
| k1 (8 ex.) | 2624 | 2614 |
| k3 (24 ex.) | 3587 | 3577 |

## Experimentos

Base: `openai/gpt-oss-20b`, `reasoning_effort=low`, lote 20.

| id | hipótese | status |
|---|---|---|
| E0 | smoke test: 1 chamada confirma auth, formato e se o reasoning entra em `completion_tokens` | executado (`scripts/smoke_test.py`) |
| E1 | baseline zero-shot, JSON estrito | executado; **configuração escolhida** |
| E2 | Gemini: formato `lines` reduz tokens sem perder acurácia | executado |
| E3 | Gemini: few-shot 1/classe | **não executado** (ver abaixo) |
| E4 | Gemini: few-shot 3/classe | **não executado** (ver abaixo) |
| E5 | Gemini: `other` sem few-shot de lixo (dados sintéticos) | executado (`scripts/smoke_test.py`, 1 chamada) |
| E6 | 120B vs 20B | **não executado**: o 20B já atendia com folga |
| E7 | holdout final, uma vez | executado |

**E3 e E4 não foram executados:** o candidato decidiu não autorizá-los depois do E1
(134/136). O ganho possível, de 1–2 itens, não seria distinguível do ruído com 136
itens, e o few-shot aumenta o prompt e a complexidade. Não há nenhum resultado medido
de few-shot.

Avaliação: `python evaluate.py <gabarito.jsonl> runs/eN.jsonl runs/eN_usage.json`.

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

### E1 e E2 — formato de saída (2026-10-13, autorizados; teto conjunto de 30.000 tokens)

Configuração comum: `openai/gpt-oss-20b`, `reasoning_effort=low`, `include_reasoning=false`,
lote 20, `max_completion_tokens=2048`, zero-shot, `--tpm-limit 6000`, mesmo prompt de
categorias e regras, `splits/dev_eval.jsonl` (136 itens, 17/classe). Holdout e teste
oculto não tocados. Limites da conta lidos nos headers: 1.000 req/dia, 8.000 tokens/min.

```
python classify.py splits/dev_eval.jsonl --format json  --tpm-limit 6000 --max-total-tokens 15000 \
  --usage runs/e1_usage.json --call-log runs/e1_calls.jsonl > runs/e1.jsonl
python classify.py splits/dev_eval.jsonl --format lines --tpm-limit 6000 --max-total-tokens 20392 \
  --usage runs/e2_usage.json --call-log runs/e2_calls.jsonl > runs/e2.jsonl
python evaluate.py splits/dev_eval.jsonl runs/eN.jsonl runs/eN_usage.json
```

| | E1 `json` (schema estrito) | E2 `lines` (`<n>\|<label>`) |
|---|---|---|
| hash do prompt de sistema | `e86ce774405004da` | `b0163060d4749a29` |
| acurácia (evaluate.py) | **98,5%** (134/136) | **97,8%** (133/136) |
| macro-F1 | 0,985 | 0,977 |
| erros | automotive 15/17 | automotive 14/17 |
| requisições HTTP / retentativas | 7 / 0 | 7 / 0 |
| respostas com problema de parsing/validação | 0 | 0 |
| itens com falha | 0 | 0 |
| tokens entrada / saída / total | 6.379 / 3.229 / 9.608 | 5.637 / 2.442 / 8.079 |
| … dos quais reasoning (dentro da saída) | 1.928 | 1.758 |
| saída visível (saída − reasoning) | 1.301 | 684 |
| média por item | 70,6 | 59,4 |
| reasoning por chamada (mín–máx) | 134–511 | 72–392 |
| tempo total (inclui espera de ritmo) | 64,5 s | 64,5 s |
| `usage_exact` | true | true |

Matriz de confusão: todas as classes na diagonal (17/17), exceto `automotive`:
- E1: automotive → entertainment 1, fashion 1.
- E2: automotive → technology 1, entertainment 1, fashion 1.

Erros (textos do treino):
- `tr108` "Película automotiva com proteção UV…" → entertainment (E1 e E2). "Película"
  também significa "filme" em espanhol: ambiguidade multilíngue.
- `tr169` "Built for the trail. Priced for the driveway." → fashion (E1 e E2). Slogan sem
  o produto explícito.
- `tr027` "Rastreador veicular com app e bloqueio remoto" → technology (só E2).
  Eletrônico de uso veicular, uma convenção do treino que o guia não explicita.

Total E1 + E2: **17.687 tokens** (teto: 30.000), 14 requisições, nenhuma falha ou 429.

Observação operacional: na 5ª chamada do E2, o header `x-ratelimit-remaining-tokens` chegou
a **206**. O controle de ritmo funciona dentro de cada processo e não enxergava os tokens
do E1, que ainda estavam na janela de 60 s do Groq (o E2 começou logo depois). Não houve
429, mas a margem foi mínima.
Corrigido depois: o ritmo passou a considerar também os headers de rate limit do Groq
(`0ccc476`, 2026-10-14). O holdout (E7, 2026-10-15) rodou com essa versão. O ajuste
posterior do prazo de reset (`61c8d4c`, 2026-10-16) é **posterior** ao holdout.

Limitações: uma execução por configuração (o modelo não é determinístico); a diferença
E1 × E2 é de 1 item, dentro do ruído esperado. O `dev_eval` não contém `other`.

### E5 — sanidade de `other` com dados sintéticos (2026-10-14, autorizado: 1 chamada)

**É um teste de sanidade, não uma medição de desempenho em `other` no teste oculto.** São
8 entradas escritas à mão, fáceis e enviadas num lote composto só de anomalias.

- Comando: `python scripts/smoke_test.py synthetic/other_sanity.jsonl --n 8 --out runs/e5`
  (configuração do E1, sem nenhuma alteração: `gpt-oss-20b`, `low`, JSON estrito,
  zero-shot; `max_retries=0` e bloqueio de uma segunda chamada).
- Verificações prévias:
  - nenhum texto idêntico ao teste; similaridade máxima (difflib) de 0,43;
  - arquivo commitado em `7d3a3b4`, antes de qualquer chamada à API;
  - nenhuma predição do teste foi gerada; ids `synNN`.
  - Ressalva: os *tipos* de anomalia (HTML, placeholder latino, teclado aleatório)
    foram inspirados pelos perfis vistos ao ler o teste sem rótulos e pela recomendação
    do Gemini; os textos são diferentes.
- Tipos de entrada:
  - markup HTML (`syn01`);
  - placeholder latino (`syn02`);
  - teclado aleatório (`syn03`);
  - variável de template (`syn04`);
  - entidades HTML escapadas (`syn05`);
  - pseudopalavras (`syn06`);
  - só espaços (`syn07`);
  - frase coerente fora de qualquer categoria (`syn08`).
- Rotas: 1 tratado localmente (`syn07`, regra de texto vazio) e 7 enviados à API.
- Resultado: **8/8 `other`** (7/7 pela API, 1/1 local). JSON válido, `finish_reason=stop`,
  0 problemas.
- Tokens: entrada 737, saída 90 (reasoning 16), total **827**; 103,4/item sobre os 8, ou
  118/item sobre os 7 enviados. A média por item é maior que no E1 porque o custo fixo do
  prompt se dilui em só 7 itens. `usage_exact: true`.
- Evidência complementar sobre falsos positivos de `other`: no E1, nenhum dos 136 anúncios
  legítimos do `dev_eval` recebeu `other`.
- Limitações:
  - lote homogêneo (no teste, as anomalias vêm misturadas a anúncios normais);
  - só 1 caso coerente fora de domínio;
  - nenhum caso em outro idioma ou só com URL/emoji.

### E7 — holdout final (2026-10-15, autorizado: execução única)

O holdout foi usado **uma única vez**, depois de a configuração ter sido escolhida (E1) e
congelada. Nenhum ajuste foi feito com base nele.

- Configuração congelada (padrões da CLI): `openai/gpt-oss-20b`, `--format json` (JSON
  Schema estrito), zero-shot, `reasoning_effort=low`, `include_reasoning=false`, lote 20,
  `max_completion_tokens=2048`, `--tpm-limit 6000`. Hash do prompt de sistema
  `e86ce774405004da`, idêntico ao do E1. Prompt, parser, pipeline e CLI sem diff desde o
  commit do E1 (`213da9c`); só o controle de ritmo do cliente mudou (`0ccc476`).
  **Cronologia:** o holdout rodou em 2026-10-15 com o código do commit `0ccc476`. Os
  commits `2275535`, `61c8d4c`, `52c54b7` e `0b9fae1` (contabilidade de usage em erros,
  prazo de reset, circuit breaker, validação de argumentos) são posteriores. Eles não
  alteram prompt, schema, lote nem parsing; só o tratamento de falhas e de ritmo.
- Comando:
  ```
  python classify.py splits/holdout.jsonl --tpm-limit 6000 --max-total-tokens 6000     --usage runs/holdout_usage.json --call-log runs/holdout_calls.jsonl > runs/holdout.jsonl
  python evaluate.py splits/holdout.jsonl runs/holdout.jsonl runs/holdout_usage.json
  ```
- Resultado (`evaluate.py`): **acurácia de 97,5% (39/40), macro-F1 de 0,975**. Todas as
  classes 5/5, exceto health 4/5.
- Único erro: `tr075` "Health insurance plans for freelancers and gig workers" → finance
  (gold: health). A regra 1 do guia, que está no prompt, diz que planos de saúde são
  `health`; o modelo aplicou a regra geral de seguros e ignorou a exceção. Não corrigido,
  por decisão de não ajustar com base no holdout.
- Tokens: entrada 1.828, saída 951 (dos quais 570 de reasoning, já contidos na saída),
  total **2.779**, **69,5/item**. Conferência: 910+528 + 918+423 = 2.779, a soma dos
  `prompt_tokens + completion_tokens` das 2 chamadas, sem somar o reasoning de novo.
- Requisições: 2, retentativas: 0, falhas de API/parsing/validação: 0,
  `usage_exact: true`, 2,1 s. Os headers indicavam 5.100–6.240 tokens restantes no
  minuto, sem espera de ritmo.
- Integridade:
  - 40 IDs, cada um uma vez, mesma ordem e conjunto do gabarito; só as chaves `id`/`label`;
    nenhum label fora da lista; LF, sem CR;
  - exit 0; MD5 de `data/` inalterado; nenhum padrão de chave nos arquivos gerados.
- Limitação: com 40 itens, o intervalo de confiança é largo (1 erro = 2,5 p.p.); é uma
  única execução de um modelo não determinístico.

### Resumo

| | conjunto | rótulos | n | acurácia | macro-F1 | tokens/item |
|---|---|---|---|---|---|---|
| E1 (escolhida) | `dev_eval` | treino (reais) | 136 | 98,5% | 0,985 | 70,6 |
| E2 | `dev_eval` | treino (reais) | 136 | 97,8% | 0,977 | 59,4 |
| E7 holdout | `holdout` | treino (reais) | 40 | 97,5% | 0,975 | 69,5 |
| E5 (sanidade) | sintético | escritos à mão | 8 | 8/8 `other` | — | 103,4 (lote de 7) |
