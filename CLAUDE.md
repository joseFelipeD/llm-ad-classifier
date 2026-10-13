@AGENTS.md

## Uso específico do Claude Code
- Você é o agente de implementação, não a autoridade final sobre a solução.
- Antes de codificar, apresente um plano curto que o candidato consiga aprovar.
- Para inspeção de dados, pode delegar ao subagente `auditor-dados`.
- Para revisar robustez, pode delegar ao subagente `auditor-robustez`.
- Os subagentes são consultivos e têm ferramentas de leitura: não devem editar arquivos.
- Ao concluir uma etapa, informe arquivos alterados, comandos realmente executados, resultados e sugestões de commit; peça aprovação antes do commit.
