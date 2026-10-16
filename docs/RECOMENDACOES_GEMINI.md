# Recomendações da revisão técnica — Gemini

Origem: revisão independente realizada com Google Gemini.

Status: recomendações aprovadas pelo desenvolvedor.

> Nota posterior: este é o registro da revisão, feito antes dos experimentos. Nem tudo foi
> aplicado como sugerido: os experimentos de few-shot não foram executados, as variantes
> foram comparadas no `dev_eval` (não no holdout), o teste de `other` usou entradas
> sintéticas em vez de itens do teste e o truncamento foi descartado. O que
> foi feito com cada recomendação está em `DECISIONS.md` e `docs/EXPERIMENTOS.md`.

Objetivo: orientar melhorias na implementação do
classificador de anúncios.

## Recomendações

**3. Hipóteses alternativas que merecem investigação**

* **Hipótese do Split Assimétrico:** Um split de 80/20 (160 itens para *dev/few-shot* e 40 para *holdout*) reterá diversidade suficiente para o modelo aprender as fronteiras das classes sem comprometer totalmente a validação local.
* **Hipótese de Delegação Semântica para Anomalias:** Em vez de usar código para tratar lixo digital (HTML, lorem ipsum), delegar essa identificação ao LLM através de um prompt robusto que reforce a regra explícita do `other` ("texto vazio, ilegível ou que não se encaixa") garantirá maior generalização para anomalias imprevistas.


* **Hipótese de Prompting Estruturado Simples vs JSON Strict:** O uso do modo JSON estrito pode gerar tokens de saída excessivos (chaves, colchetes). Requisitar a saída em um formato de texto demarcado ou CSV pode economizar *output tokens* e viabilizar lotes maiores.

**4. Experimentos pequenos que permitam comparar as alternativas**

* **Experimento de Sensibilidade de Few-Shot:** Construa dois prompts: um com 1 exemplo por classe e outro com 3 exemplos por classe (selecionados dos 160 itens sugeridos). Teste ambos contra o *holdout* de 40 itens e meça o impacto na acurácia e no custo de tokens.
* **Experimento de Captura de 'Other':** Envie os 4 perfis anômalos identificados no teste (HTML, lorem ipsum, texto de teclado e uma frase sem sentido) para o modelo escolhido via API, usando apenas o prompt de sistema com as categorias. Verifique se o LLM prevê `other` naturalmente. Se falhar, adicione 1 exemplo sintético de "lixo digital" no *few-shot* e repita.


* **Experimento de Truncamento:** Processe os 5 exemplos mais longos do conjunto de treinamento em sua forma integral e, em seguida, truncados em 100 e 200 caracteres. Verifique se o rótulo predito muda.



**5. Recomendação final justificada**
Recomendo **rejeitar o split 50/50** e adotar uma divisão 80/20 (160/40), pois a meta de acurácia de 85% é agressiva demais para um modelo avaliado em tão poucos exemplos de fronteira. **Aprove** a arquitetura usando apenas a biblioteca padrão do Python (`urllib`), mas oriente o desenvolvedor a **não truncar textos longos**, visto que 539 caracteres não representam risco de custo substancial. Para a classe `other`, implemente um atalho determinístico (código) *apenas* para strings estritamente vazias ou compostas apenas por espaços (poupando chamadas de API), mas confie na capacidade do LLM para julgar itens ilegíveis (HTML, lorem ipsum), desde que o prompt reforce a regra 9.