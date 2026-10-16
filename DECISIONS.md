# DECISIONS

Detalhes e comandos de cada experimento: [`docs/EXPERIMENTOS.md`](docs/EXPERIMENTOS.md).
Como rodar e o que acontece em cada falha: [`README.md`](README.md).

## Acurácia e custo medidos

Groq `openai/gpt-oss-20b`, JSON Schema estrito, zero-shot, `reasoning_effort=low`, lotes
de 20. Medido com o `evaluate.py` original em partições do treino (split estratificado,
seed 42), uma execução por configuração:

| conjunto | n | acurácia | macro-F1 | tokens/item |
|---|---|---|---|---|
| `dev_eval` (escolha da configuração) | 136 | 98,5% | 0,985 | 70,6 |
| `holdout` (uso único, configuração já congelada) | 40 | **97,5%** | **0,975** | 69,5 |
| sintético de `other` (sanidade, não é medição) | 8 | 8/8 | — | 103,4 |

- **Custo:** soma do `usage` real de todas as respostas da API, inclusive retentativas
  (`prompt_tokens + completion_tokens`). Os `reasoning_tokens` já vêm dentro de
  `completion_tokens` (no E0: 364 − 177 = tamanho do JSON visível) e não são somados de
  novo.
- **O que não foi medido:** o `other` real, que não existe no treino. Os erros observados
  foram ambiguidades ("Película automotiva", que em espanhol significa filme; slogan sem
  produto) e uma exceção do guia ignorada ("Health insurance plans" → finance, quando a
  regra 1 diz `health`).

## Abordagens tentadas e descartadas

- **Uma chamada por item:** descartada antes de medir. O GPT-OSS sempre raciocina e o
  prompt com o guia é grande (o E5, com 7 itens curtos, usou 737 tokens de entrada).
  Uma chamada por item mal caberia em 400 tokens; em lote de 20, o custo fixo se dilui
  (~70/item medido).
- **Formato texto `<n>|<label>` (E2):** 97,8% e −16% de tokens, mas a diferença de
  acurácia foi de 1 item (ruído) e o orçamento já tinha folga de ~6×. Ficamos com o
  JSON Schema estrito, cujo `enum` impede labels inválidos no próprio servidor.
- **Few-shot com 1 ou 3 exemplos por classe (E3/E4):** infraestrutura pronta, mas não
  executados. Com 134/136, o ganho possível era indistinguível do ruído; e escolher
  exemplos para os erros observados seria ajustar o prompt pelo conjunto de validação.
- **`reasoning_effort` medium e o modelo 120B:** não testados; nada indicava falta de
  raciocínio (nenhuma resposta cortada; os erros eram de ambiguidade).
- **Truncar textos longos:** não; o maior item tem 539 caracteres, custo irrelevante.

## Onde a IA ajudou e onde errou

Fluxo: Claude Code implementou e rodou os testes; o Gemini revisou o plano; o Codex e
um subagente do Claude (`auditor-robustez`) auditaram o código sem editá-lo; eu aprovei
cada etapa, cada gasto de API e cada commit.

- **Ajudou:** diagnóstico dos dados, estrutura com stdlib, 78 testes offline, controle
  de consumo e registro de cada experimento.
- **Claude errou, e o erro foi corrigido antes do commit:**
  - backoff fixo em vez de exponencial;
  - `usage.json` dizendo "1 item falhou" num abort;
  - uma asserção de teste sem efeito;
  - CRLF/cp1252 no Windows;
  - um script de edição que inseriu quebras de linha literais em strings.
- **Erros que só as auditorias pegaram:**
  - `auditor-robustez`: `IncompleteRead`/SSL derrubariam o processo; predições parciais
    iam para o stdout com exit 1; um erro de configuração geraria ~2N chamadas inúteis;
    `retry-after: nan` causava exceção.
  - Codex: o circuit breaker tratava uma resposta 200 sem label válido como sucesso; o
    prazo de reset dos headers era descartado cedo demais; `True` e valores negativos
    passavam como contagem de tokens; o `usage` de erros HTTP era ignorado.
- **Erro que só a execução real revelou:** o controle de ritmo por processo não via o
  consumo da execução anterior. O servidor chegou a informar só 206 tokens restantes no
  minuto. Corrigido usando os headers de rate limit.
- **Gemini:** acertou o split 80/20 e a ideia de comparar texto vs JSON. Errou ao sugerir
  calibrar o prompt com itens do teste oculto e escolher variantes pelo holdout, e
  propôs um experimento de truncamento sem efeito nestes dados (máx. 62 caracteres no
  treino). As três sugestões foram adaptadas ou descartadas.

## Decisões que tomei sem o enunciado cobrir

- **Provedor:** a empresa não forneceu chave. Usei o plano gratuito do Groq (1.000
  req/dia, 8.000 tokens/min confirmados nos headers da conta).
- **Texto vazio ou só espaços → `other` sem chamar a API** (regra literal do enunciado).
  HTML, lorem ipsum e lixo vão para o LLM, com a regra de `other` reforçada no prompt.
- **Falha nunca vira rótulo.** Se qualquer item ficar sem label, o stdout fica vazio e o
  exit é 1, para que um `> predictions.jsonl` incompleto não pareça entregável; as
  predições parciais vão para `--partial`.
- **Consumo desconhecido nunca é estimado:** fica marcado com `usage_exact: false`.
  Limitação: se um timeout ocorrer depois de o servidor processar o pedido, esses tokens
  não aparecem na soma. A flag sinaliza isso, mas não o corrige.
- **Os itens vão numerados 1..N no prompt, não com o id:** menos tokens, e o modelo não
  inventa ids.
- **Labels com maiúsculas ou espaços são normalizados;** duas respostas diferentes para
  o mesmo item são descartadas e o item é reenviado.

## Com mais tempo

- Medir a variância (várias execuções) e um conjunto maior com casos-limite do guia,
  como seguro implícito, financiamento de produto, carro alugado em viagem e
  suplemento vs alimento.
- Construir um conjunto de `other` realista, misturado a anúncios normais, para medir
  recall e falsos positivos.
- Avaliar o reforço das exceções do guia no prompt (o erro do holdout), validando num
  conjunto novo para não contaminar a estimativa atual.

## Nota sobre o histórico

A primeira implementação foi escrita antes de qualquer commit e registrada depois em 7
commits por responsabilidade (`ee4f230`..`513ce4a`), não em etapas separadas no tempo.
Os commits seguintes são incrementais e acompanham cada experimento e correção.
