# Segundo prompt para Claude Code — implementar baseline controlado

Plano aprovado: [COLE AQUI AS DECISÕES QUE VOCÊ APROVOU NA ETAPA 01].

Implemente apenas um baseline funcional, mínimo e reproduzível em Python, seguindo o README original e AGENTS.md. Use uma API real configurável por variável de ambiente e SDK oficial ou biblioteca justificada. Não inclua front-end, deploy, fine-tuning nem frameworks desnecessários.

Obrigatório:
- O esquema de saída permite somente os nove labels do desafio; validar também todo ID recebido.
- `other` deve ser tratado por regras genéricas e critérios explícitos, não memorizando títulos/IDs do teste.
- Suportar stdout puro JSONL; mensagens de erro apenas em stderr; exit code não zero em falha irrecuperável.
- Usar lotes pequenos apenas se facilitar custo/velocidade e preservar correspondência por ID; tamanho do lote configurável.
- Retries limitados e robustez: JSON malformado, IDs faltantes, resposta parcial, timeout, 429 e 5xx; nunca imputar rótulos silenciosamente.
- Medir input_tokens/output_tokens de acordo com metadados oficiais, incluindo chamadas extras/retries quando fornecidos; não fabricar metadados.
- Testes unitários offline com mocks de API e mensagens inválidas.
- Prover `.env.example` sem segredos, `.gitignore`, documentação executável e registro inicial de decisões.
- Preservar evaluate.py e dados originais. Nunca alterar conteúdo para aumentar pontuação.

Faça mudanças pequenas, execute `pytest` ou equivalente e mostre comandos/resultados reais. Apresente um diff/resumo e sugira mensagens de commit, mas não execute commits antes de eu aprovar. Não processe os 100 testes finais antes de validarmos o baseline.
