# Desafio técnico — Classificador de anúncios com LLM

Obrigado por participar do nosso processo. Este desafio é assíncrono e deve levar
em torno de **4 a 6 horas**. Não existe resposta única: queremos ver como você
investiga, decide e documenta — não só o código final.

Você pode (e deve) usar ferramentas de IA (Claude, ChatGPT, Copilot, Cursor, etc.)
para programar. Parte do que estamos avaliando é exatamente **como** você usa essas
ferramentas.

---

## O problema

Recebemos milhares de títulos de anúncios por dia e precisamos classificá-los em
categorias para análise. Você vai construir um classificador que usa um LLM
(via API) para fazer isso.

### Dados

- `data/train.jsonl` — 200 títulos **rotulados**. Use para desenvolver e medir.
- `data/test_unlabeled.jsonl` — 100 títulos **sem rótulo**. Você deve gerar
  predições para eles e enviar junto com a solução. Nós temos o gabarito.

Formato de cada linha:

```json
{"id": "tr001", "text": "Cartão sem anuidade com cashback de 2%", "label": "finance"}
```

### Categorias

| label | cobre |
|---|---|
| `finance` | bancos, cartões, empréstimos, investimentos, impostos, **seguros** |
| `automotive` | veículos, peças, serviços automotivos, aluguel/assinatura de carros |
| `health` | saúde física e mental, suplementos, academias, planos de saúde/odontológicos |
| `travel` | passagens, hotéis, pacotes, acessórios e conectividade para viagem |
| `technology` | eletrônicos, software, internet, gadgets |
| `food_beverage` | comida, bebida, delivery, restaurantes |
| `fashion` | roupas, calçados, acessórios, joias, perfumaria e maquiagem |
| `entertainment` | filmes, séries, música, jogos, livros, eventos, cursos de arte |
| `other` | texto vazio, ilegível ou que não se encaixa em nenhuma categoria |

> **Atenção:** o conjunto de treino **não contém** exemplos de `other`. Isso é
> proposital. O conjunto de teste pode conter.

### Guia de rotulagem (desempates)

Vários títulos poderiam cair em duas categorias. Use estas regras:

1. **Seguros** (auto, vida, residencial, viagem, pet) → `finance`.
   Exceção: planos de saúde e odontológicos → `health`.
2. **Financiamento de um produto** (carro, imóvel, viagem parcelada) →
   categoria do produto, não `finance`. Ex.: "0% financing on trucks" → `automotive`.
   Mas um **cartão** ou **empréstimo** genérico → `finance`, mesmo que mencione
   viagem ou carro como benefício.
3. **Eletrônicos** → `technology`, incluindo smartwatches e fitness trackers.
   Exceção: dispositivos médicos (medidor de pressão, balança corporal,
   aparelho auditivo, escova de dente elétrica) → `health`.
4. **Roupas e calçados** → `fashion`, mesmo com apelo esportivo ou de saúde.
   Produtos ortopédicos (palmilhas, corretor postural) → `health`.
5. **Beleza**: perfume e maquiagem → `fashion`; protetor solar, tratamento de
   acne, cuidados dermatológicos → `health`.
6. **Cursos e aulas** → categoria do tema (violão → `entertainment`,
   Python → `technology`, yoga → `health`).
7. **Pet**: ração → `food_beverage`; seguro pet → `finance`; hotel pet-friendly → `travel`.
8. Produtos cujo uso principal é **viajar** (mala, mochila de viagem, eSIM,
   chip internacional) → `travel`. Mochila do dia a dia → `fashion`.

Os rótulos do treino seguem este guia. Se encontrar algo que pareça inconsistente,
anote no `DECISIONS.md`.

---

## Requisitos

1. **Acurácia ≥ 85%** no conjunto de teste oculto (nós medimos). Reportamos também
   macro-F1, então errar sistematicamente uma categoria pequena custa caro.
2. **Custo médio ≤ 400 tokens por item** (input + output somados, média sobre os
   100 itens de teste). Você deve medir isso a partir do `usage` retornado pela API
   e reportar em `usage.json`.
3. **Saída estruturada**: o LLM pode devolver JSON malformado, um label fora da
   lista, texto extra, ou simplesmente falhar (timeout, 429, 5xx). Seu código precisa
   lidar com isso **sem derrubar o processo** e sem inventar rótulo silenciosamente.
   Decida e documente o que acontece nesses casos.
4. **Reprodutível**: `python classify.py data/test_unlabeled.jsonl > predictions.jsonl`
   (ou equivalente documentado) tem que funcionar do zero seguindo o seu README.
5. **Testes automatizados** para a parte do código que não depende da API
   (parsing da resposta, validação de labels, montagem de lotes, etc.).

Qualquer provedor de LLM serve. Vamos fornecer uma chave de API com limite de
US$ 5 — se precisar de mais, é sinal para repensar a abordagem.

### O que **não** é requisito

- Fine-tuning. Prompting bem feito resolve.
- Interface gráfica.
- Deploy.

---

## Entregáveis

Um repositório Git (público ou nos envie o `.zip` com o `.git` dentro) contendo:

| arquivo | conteúdo |
|---|---|
| código-fonte | linguagem à sua escolha |
| `README.md` | como rodar, como configurar a chave, como rodar os testes |
| `predictions.jsonl` | uma linha por item de teste: `{"id": "te001", "label": "finance"}` |
| `usage.json` | `{"items": 100, "input_tokens": N, "output_tokens": N, "avg_tokens_per_item": N, "model": "..."}` |
| `DECISIONS.md` | ver abaixo |
| histórico de commits | **não faça squash**. Queremos ver o processo. |

### `DECISIONS.md`

Uma página, informal, respondendo:

- Qual acurácia e custo você mediu no treino, e como mediu?
- Que abordagens tentou e descartou? Por quê?
- **Onde a ferramenta de IA te ajudou e onde ela errou?** Seja específico:
  o que ela gerou de errado, como você percebeu, o que fez a respeito.
- Que decisões você tomou sozinho que o enunciado não cobria?
- O que faria diferente com mais tempo?

Pode usar `evaluate.py` para medir no treino:

```
python evaluate.py data/train.jsonl minhas_predicoes_treino.jsonl [usage.json]
```

---

## Como avaliamos

Em ordem de peso:

1. **Raciocínio e processo** — `DECISIONS.md` e commits. Um candidato com 82% de
   acurácia e um relato claro de como chegou lá vale mais que 92% sem explicação.
2. **Robustez** — o que acontece quando a API falha ou devolve lixo.
3. **Cumprimento dos requisitos numéricos** — acurácia, custo.
4. **Qualidade do código** — legibilidade, testes, estrutura.

Depois da entrega, faremos uma conversa de ~30 minutos onde pediremos para você
explicar partes do código e fazer uma pequena alteração ao vivo.

Dúvidas sobre o enunciado? Pode perguntar — perguntar é parte do trabalho.
Mas se algo estiver ambíguo e você preferir decidir sozinho, tudo bem: documente.

Boa sorte!
