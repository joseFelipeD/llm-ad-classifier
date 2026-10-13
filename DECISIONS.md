# DECISIONS

> Documento em construção. Ainda **não há métricas medidas com API**: as seções de
> acurácia e custo serão preenchidas só com números reais (`docs/EXPERIMENTOS.md`).

## Nota sobre o histórico de commits

A primeira implementação (código, testes e documentação) foi escrita inteira numa única
sessão, antes de qualquer commit. Os 7 commits seguintes ao commit inicial a registram
**depois**, agrupada por responsabilidade técnica. Para cada commit compilar e passar
nos próprios testes, o arquivo de testes de pipeline/CLI/split foi dividido em
`fakes.py`, `test_pipeline.py`, `test_cli.py` e `test_split.py` antes dos commits. Não
houve mudança de comportamento: os mesmos 52 testes. Os commits não representam etapas
de desenvolvimento separadas no tempo.

## Acurácia e custo medidos

Pendente. Nenhuma chamada de API foi feita até agora.

## Provedor e arquitetura

- **Provedor:** Groq (API compatível com OpenAI). A empresa não fornece chave nem
  créditos. O GPT-OSS 20B/120B tem plano gratuito documentado (30 RPM, 1K RPD,
  8K TPM, 200K TPD por modelo, a confirmar no painel da conta) e JSON Schema estrito
  com `enum`.
- **Só a biblioteca padrão** (`urllib`, `unittest`): nada para instalar.
- **Lotes** (padrão 20 itens): o GPT-OSS sempre raciocina (o mínimo é
  `reasoning_effort=low`) e o prompt com o guia tem cerca de 2.100 caracteres. Uma
  chamada por item dificilmente cabe em 400 tokens; em lote, o custo fixo se dilui.
  Ainda é hipótese, a ser confirmada pelo `usage`.
- **Os itens vão numerados 1..N no prompt**, não com o id do arquivo: menos tokens, e o
  modelo não tem como inventar ids. O texto vai como string JSON (aspas e quebras de
  linha do anúncio não se misturam à lista).

## Política de falhas (nenhuma vira rótulo silenciosamente)

| situação | o que acontece |
|---|---|
| texto vazio ou só espaços | `other` por regra explícita do README ("texto vazio"), sem API |
| HTML, lorem ipsum, lixo | vai para o LLM (o prompt reforça a regra do `other`) |
| JSON malformado, label inválido, item ausente ou conflitante | só os itens sem label válido são reenviados; um lote sem nada aproveitável é dividido ao meio; item isolado: 2 tentativas |
| 429 / 408 / 5xx / timeout / erro de rede ou de leitura (SSL, `IncompleteRead`) | o cliente repete até 4 vezes (`retry-after` ou backoff exponencial, teto de 60 s); se esgotar, o lote vira falha, sem multiplicar chamadas |
| `retry-after` maior que 60 s (ex.: cota diária) | desiste na hora, em vez de gastar as tentativas |
| 400 (ex.: validação de JSON) | tratado como resposta ruim: divide o lote e tenta de novo |
| 4 chamadas seguidas com erro de API, sem nenhuma resposta aproveitável | aborta (código 2), em vez de repetir a falha em todos os lotes (circuit breaker) |
| 401 / 403 / 404 | aborta tudo (código 2) |
| entrada inválida (JSON, id ausente/duplicado, sem `text`) | aborta antes da API (código 2) |
| exceção inesperada | aborta (código 2), mas grava o `usage.json` com `aborted: true` |

Se **qualquer** item falhar, o **stdout fica vazio** e o processo termina com código 1.
Assim, um `> predictions.jsonl` incompleto não fica parecendo um entregável válido. As
falhas vão para o stderr e para `--failures`; as predições obtidas, para `--partial`
(para não desperdiçar tokens já pagos ao diagnosticar).

Tokens: somamos `prompt_tokens + completion_tokens` de **todas** as respostas,
inclusive retentativas e respostas 200 malformadas que tragam `usage`. Nada é estimado.
Respostas sem `usage` e falhas de transporte são contadas à parte e deixam
`usage_exact: false` no `usage.json`. A média é calculada sobre todos os itens da
entrada, inclusive os vazios, que custam 0.

## Recomendações do Gemini (revisão independente, `docs/RECOMENDACOES_GEMINI.md`)

O candidato aprovou todas. Situação de cada uma:

| recomendação | situação | como |
|---|---|---|
| Split 80/20 (160/40) em vez de 50/50 | **implementada** | `scripts/make_split.py`, estratificado, seed 42, testado |
| Só stdlib / `urllib` | **implementada** | `classifier/client.py` |
| Não truncar textos longos | **implementada** | o texto vai integral; teste `test_long_text_is_not_truncated` |
| Atalho determinístico só para texto vazio/espaços | **implementada** | `classifier/pipeline.py`; HTML continua indo ao LLM (teste) |
| Reforçar a regra do `other` no prompt | **implementada** | descrição de `other` cita markup, placeholder e caracteres aleatórios, e proíbe usá-lo como "não sei" |
| Testar texto demarcado vs JSON estrito | **implementada como opção** (`--format lines`) | parser próprio, testado; comparação de tokens pendente (E1 vs E2) |
| Few-shot 1 vs 3 por classe | **infraestrutura pronta** (`--examples`, `fewshot_k1/k3`) | experimento pendente (E3/E4) |
| Captura de `other` | **adaptada** (ver conflito 1) | `synthetic/other_sanity.jsonl`; experimento pendente (E5) |
| Experimento de truncamento | **não executado** (ver conflito 3) | — |

### Conflitos encontrados e como foram resolvidos

1. **Enviar os 4 itens anômalos do teste à API e ajustar o prompt conforme o resultado.**
   Isso seria ajustar o prompt usando o teste oculto, o que o contrato do projeto
   proíbe. Substituímos por 8 entradas sintéticas escritas à mão, com perfis
   equivalentes mas textos diferentes, num arquivo separado e marcado como sintético.
2. **Comparar as variantes de few-shot "contra o holdout de 40".** Escolher configuração
   pelo holdout o transforma em conjunto de validação, e a estimativa final fica
   otimista. As variantes são comparadas no `dev_eval` (136 itens, sem nenhum exemplo do
   prompt); o holdout é medido uma vez, no fim.
3. **Truncar os 5 textos mais longos do treino em 100/200 caracteres.** O texto mais
   longo do treino tem 62 caracteres, então o experimento não alteraria nada. Como a
   própria recomendação final é não truncar, seguimos essa decisão sem gastar chamadas.

## Onde a IA ajudou e onde errou

- **Claude Code (implementação):** gerou a estrutura, o cliente, o pipeline e 40 testes
  offline. Erros percebidos e corrigidos antes de qualquer commit:
  - a primeira versão do backoff esperava sempre o mesmo tempo, com um comentário que
    admitia a aproximação. Reescrito como exponencial por tentativa, com teste;
  - numa execução abortada, o `usage.json` informaria "1 item falhou", o que era falso.
    Trocado por `aborted: true` e `items_failed: null`;
  - um teste continha uma asserção sem efeito (expressão condicional sempre falsa),
    corrigida;
  - no Windows, os logs saíam em cp1252 e o stdout com CRLF. A CLI agora força UTF-8 e
    `\n`;
  - ao aplicar as correções da auditoria por script, o `\n` dentro de strings virou
    quebra de linha literal e deixou o arquivo com erro de sintaxe. Detectado na
    releitura, antes de rodar os testes, e corrigido.
- **Subagente `auditor-robustez` (Claude, somente leitura):** auditou a primeira versão e
  apontou problemas reais que os 40 testes não pegavam. Todos foram aceitos e cobertos
  por testes novos (52 no total):
  - `IncompleteRead`/SSL derrubariam o processo sem gravar o usage;
  - o stdout recebia predições parciais mesmo com exit 1;
  - um 400/404 de configuração geraria cerca de 2N chamadas inúteis (agora: 404 fatal
    + circuit breaker);
  - `retry-after: nan` causaria exceção, e um `retry-after` longo gastaria tentativas em
    vão;
  - o `usage` era ignorado em respostas 200 malformadas;
  - a chave não era mascarada nas mensagens de erro.

  Não adotado: registrar "chamadas lógicas" além de `http_attempts`, por ser
  redundante para o requisito.
- **Gemini (revisão do plano):** propôs o split 80/20, não truncar e o formato de texto
  como alternativa ao JSON. Errou ao sugerir usar itens do teste e o holdout para
  calibração, e propôs um experimento de truncamento sem efeito nestes dados (ver
  conflitos).

## Decisões não cobertas pelo enunciado

- Texto vazio vira `other` sem API; qualquer outro texto passa pelo LLM.
- Labels com maiúsculas ou espaços (" Finance ") são normalizados; qualquer outro label
  fora da lista é rejeitado.
- Duas respostas diferentes para o mesmo item no mesmo lote: as duas são descartadas e o
  item é reenviado.

## Com mais tempo

Pendente, a preencher após os experimentos.
