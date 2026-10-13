---
name: auditar-entrega
description: Checa a prontidão de entrega do classificador de anúncios, formatos, testes, métricas, segredos e integridade; use antes de finalizar.
---
# Auditoria final do desafio

1. Leia as seções de requisitos e entregáveis do enunciado original (`ENUNCIADO_ORIGINAL.md`, se renomeado; caso contrário `README.md`).
2. Verifique os arquivos existentes e os comandos documentados, sem inventar resultados.
3. Execute testes unitários offline se possível; registre comando, retorno e falhas.
4. Sem executar chamadas de API sem aprovação, verifique se o `predictions.jsonl` existente tem exatamente os IDs do teste, um por linha, labels válidos e nenhum extra.
5. Verifique que `usage.json` contém items, input_tokens, output_tokens, avg_tokens_per_item e model, e que a média bate com os totais; não substitua uso medido por estimativa.
6. Verifique que o README da solução explica instalar, definir variáveis de ambiente e executar. Se o README de desafio original foi preservado, explique como distinguir ambos.
7. Verifique DECISIONS.md: experimentos reais, acurácia e custo medidos na validação, erros de IA realmente ocorridos, decisões humanas e limitações.
8. Execute inspeção de Git para segredos, arquivos indesejados e histórico de commits.
9. Entregue um checklist PASSOU/FALHOU/NÃO VERIFICADO, justificando cada item; não faça commits, push ou modificações sem autorização.
