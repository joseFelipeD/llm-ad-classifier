# Contrato compartilhado do projeto — Classificador de anúncios com LLM

## Fonte de verdade
- Leia o enunciado original do desafio antes de tomar decisões sobre requisitos, categorias e regras de desempate: inicialmente `README.md`; na entrega, caso haja um README próprio da solução, o original deve ser preservado em `ENUNCIADO_ORIGINAL.md`.
- Leia `evaluate.py` ao trabalhar com métricas. Não modifique esse arquivo sem justificativa e aprovação explícita.
- Correção oficial comunicada pelo candidato: a empresa **não fornece API key nem US$ 5 de crédito**. Use API gratuita ou credenciais próprias.
- Os arquivos `data/train.jsonl` e `data/test_unlabeled.jsonl` são imutáveis e não devem ter rótulos fabricados.

## Papéis e governança
- Claude Code: implementador principal e executor dos testes.
- Codex: auditor independente; não altera arquivos nem cria commits quando revisa.
- Gemini: questiona hipóteses de classificação; não produz gabarito para os 100 itens de teste.
- Candidato: aprova arquitetura, provedor, custos, mudanças e commits.
- Não acione todos os agentes em paralelo para editar a mesma árvore de trabalho.

## Requisitos não negociáveis
- 9 rótulos válidos conforme README, inclusive `other` (ausente no treino).
- Acurácia-alvo >= 85% no teste oculto; reportar acurácia de validação honestamente e macro-F1.
- Orçamento <= 400 tokens por item em média na execução dos 100 títulos de teste, conforme uso real registrado pela API.
- Chamadas de API reais, não interface de chat ou labels preenchidos manualmente.
- Robustez: JSON inválido, labels inválidos, IDs ausentes/duplicados, timeout, 429 e 5xx.
- Falhas não podem virar `other` ou qualquer outro rótulo silenciosamente.
- `stdout` contém somente JSONL de predições; logs e erros vão para `stderr`.
- Execuções incompletas devem terminar com erro e não ser tratadas como entregáveis válidos.
- Testes automatizados da lógica sem chamadas externas e CLI reproduzível.
- Entradas multilingues. Não codifique exceções com base em `teXXX` nem memorize o teste oculto.

## Método
- Primeiro diagnóstico, depois plano curto, implementação mínima, medição, revisão, correção e entrega.
- Para cada experimento, registre hipótese, alteração, conjunto usado, métricas e custo REAL da API.
- Não use treino/validação vazados para ajustar prompt: separe e identifique as partições usadas; nunca apresente estimativa como teste oculto.
- Verifique documentação oficial do provedor/modelo escolhido e limites vigentes.
- Mantenha dependências mínimas, código que o candidato consiga explicar e commits incrementais.
- Não faça commits, push, instale dependências ou rode comandos destrutivos sem informar e obter aprovação do candidato.
- Não marque testes como aprovados sem executá-los; registre ausência de acesso à API como bloqueio, não como sucesso.

## Segurança
- Configure segredos fora do Git. Nunca imprima, copie para prompts, envie ou versione `.env`, tokens, credenciais ou logs sensíveis.
- Antes de entregar, verifique `git status`, arquivos rastreados e diff para identificar segredos e arquivos não intencionais.
