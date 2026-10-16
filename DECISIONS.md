# Decisões de desenvolvimento

Detalhes dos experimentos: docs/EXPERIMENTOS.md. Instruções de execução: README.md.

## Como avaliei a solução

Comecei analisando os 200 anúncios rotulados e as regras do desafio. Para conciliar acurácia e custo, escolhi o `openai/gpt-oss-20b` na API gratuita da Groq, com um prompt zero-shot, JSON Schema e lotes de 20 anúncios. Assim, o custo das instruções é dividido entre vários itens.

Separei os dados de forma estratificada (seed 42), reservando um conjunto para comparar alternativas e outro para a avaliação final. No `dev_eval` (136 anúncios), obtive 98,5% de acurácia, macro-F1 de 0,985 e 70,6 tokens por item. Depois de escolher a configuração, executei o holdout (40 anúncios) uma única vez: 97,5%, macro-F1 de 0,975 e 69,5 tokens por item, medidos com o `evaluate.py` fornecido.

Na execução final, todos os 100 anúncios receberam um rótulo. Foram contabilizados 7.562 tokens (75,6 por item). Uma requisição retornou HTTP 400 sem informar `usage`; o lote foi dividido e reprocessado com sucesso. Por isso, `usage_exact=false`: o valor informado é o consumo conhecido, não o total comprovado. A acurácia do teste permanece desconhecida, pois não tenho o gabarito.

## O que comparei e descartei

Comparei JSON estruturado e texto simples. O texto consumiu cerca de 16% menos tokens, mas acertou 133/136 anúncios, contra 134/136 do JSON. Como ambos ficaram bem abaixo do orçamento, mantive o JSON pela validação mais previsível. Descartei chamadas individuais sem testá-las, pois repetiriam as instruções para cada item.

Considerei few-shot, maior esforço de raciocínio e o modelo 120B, mas preferi não executar esses experimentos: o baseline já funcionava bem, e escolher exemplos para corrigir erros específicos do `dev_eval` poderia enviesar a comparação. Também testei oito exemplos sintéticos de `other`, ausente no treino: os oito foram reconhecidos, mas isso não mede o desempenho com casos reais.

## Onde a IA ajudou — e onde errou

Usei o Claude Code na implementação, o Gemini para revisar o planejamento e o Codex e um subagente do Claude para auditorias. Eu defini prioridades, aprovei experimentos e custos de API e decidi quais recomendações aplicar.

O Gemini sugeriu ajustar o prompt com itens do teste oculto e escolher variantes pelo holdout. Rejeitei essas sugestões para preservar uma avaliação independente. O Claude inicialmente gerou um backoff fixo onde deveria ser exponencial. Seu auditor encontrou falhas de conexão capazes de interromper o processo e deixar predições parciais no stdout. O Codex identificou outros erros que os testes não haviam detectado: o circuit breaker aceitava respostas sem labels válidos como sucesso, e tokens de respostas HTTP com erro eram ignorados. As correções deram origem a novos testes; a suíte terminou com 78 testes offline aprovados.

## Decisões que tomei

Como a empresa não forneceria chave de API, optei pelo plano gratuito da Groq. Também defini que textos vazios seriam classificados como `other` sem chamada ao modelo, enquanto os demais seguiriam para o LLM. Uma falha definitiva nunca vira um rótulo inventado: o processo sinaliza o erro e não publica um JSONL incompleto como válido. Dentro dos lotes, numerei os anúncios em vez de enviar seus IDs originais, reduzindo tokens e simplificando a associação das respostas.

Preferi sinalizar consumo desconhecido a inventar medições. Outra limitação conhecida é o tratamento de prazos longos de reset da API, que decidi documentar, sem ampliar a implementação para um cenário pouco relevante neste volume de dados.