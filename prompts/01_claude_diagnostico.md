# Primeiro prompt para Claude Code — diagnóstico, sem alterações

Atue como engenheiro de software responsável pela implementação do desafio de classificador de anúncios com LLM. Leia `README.md`, `data/train.jsonl`, `data/test_unlabeled.jsonl`, `evaluate.py`, `AGENTS.md` e `CLAUDE.md` (ajuste caminhos após localizar os arquivos). A correção oficial é que a empresa NÃO fornece chave nem créditos de API.

Antes de codificar, entregue:
1. Inventário dos arquivos e requisitos, separando fatos observados de hipóteses.
2. Estatísticas reais do treino e do teste (contagem, distribuição de labels, duplicatas, JSON válido e exemplos ambíguos); não atribua rótulos ao teste.
3. Comportamento exato do evaluate.py, incluindo limitações de validação e de código de retorno.
4. Riscos prioritários: regras de desempate, `other` ausente no treino, vazamento de validação, custo por item, JSON estrutural, lotes, 429/5xx e entradas vazias.
5. Compare até três opções de API gratuitas/acessíveis; se não tiver navegação ou credenciais, deixe isso claro e proponha critérios de verificação, sem inventar cotas.
6. Plano mínimo em etapas, com proposta de estrutura de arquivos e commits pequenos.
7. Diga quais decisões exigem minha aprovação antes de implementar.

Você pode delegar a leitura crítica ao subagente auditor-dados, se disponível. NÃO altere arquivos, NÃO execute chamadas externas pagas e NÃO crie predições nesta etapa. Espere minha aprovação.
