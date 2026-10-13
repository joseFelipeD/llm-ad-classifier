# Terceiro prompt para Claude Code — medir e comparar

Agora precisamos de evidências. Antes de executar chamadas de API, apresente os comandos, modelos, limite máximo de requisições e uma estimativa *não oficial* de custo somente para aprovação. Confirme a disponibilidade da chave em ambiente sem imprimi-la.

Prepare uma avaliação honesta dos 200 exemplos rotulados, com separação estratificada e seed fixa. Preserve uma partição de validação fora da seleção de few-shots e ajustes do prompt. Não apresente a acurácia de treino após otimização no mesmo conjunto como validação independente. Se houver poucos exemplos, explique incerteza.

Compare no máximo duas variantes justificadas de prompt/lote/modelo, evitando varrer dezenas de combinações no mesmo conjunto de validação. Registre, para cada experimento: data, modelo, configurações, tamanho do lote, número de itens, acurácia, macro-F1, input/output tokens retornados pela API, erros de classificação, retries e custo financeiro se conhecido.

Use evaluate.py como avaliação complementar, mas crie verificações explícitas de validade e de código de retorno. Analise erros por regra de desempate, sobretudo seguro/plano de saúde, financiamento específico/genérico, tecnologia/dispositivo médico, vestuário esportivo e objetos de viagem.

Ao final, recomende uma opção única para a execução final e relate trade-offs. Não execute o teste oculto ainda e não fabrique rótulos, métricas nem logs.
