# Quarto prompt para Claude Code — finalizar após revisão

A implementação, resultados e correções da revisão foram aprovados. Se ainda houver apenas o README original do enunciado, preserve-o como `ENUNCIADO_ORIGINAL.md` (usando Git) e prepare um novo README de execução da solução. Faça uma checagem final antes de processar o teste oculto: formato dos arquivos, README de execução, `.env.example`, testes offline, compatibilidade da CLI e tratamento de falhas. Não mude regras ou prompt usando inferências sobre labels do teste.

Somente depois que eu aprovar explicitamente o consumo de API: execute o classificador nos 100 itens de teste. Gere `predictions.jsonl` sem duplicatas, extras ou faltantes. Gere `usage.json` com uso real reportado pelo provedor e média consistente. Contabilize chamadas adicionais de recuperação/retry onde houver metadados. Não simule as chamadas nem as respostas.

Rode a skill `/auditar-entrega`, se disponível. Apresente checklist PASSOU/FALHOU/NÃO VERIFICADO, comandos executados, contagem de predições, uso de tokens, resultados dos testes, diff final e oportunidades de melhoria. Atualize `DECISIONS.md` sem inventar erros que não aconteceram. Antes de commitar, apresente os arquivos staged e peça minha aprovação. Não faça push sem autorização.
