# Research: Fase 1 — chain executável

Fontes: constitution v1.1.1, spec 001, notebooks das aulas 2, 3 e 4
(`agentes-cognitivos/aulaN/*.ipynb`), cenários do `incident-shop` (`api/cenarios.py`).

## R1. Modelo de chat no setup

- **Decision** (revisada em 01/11, constitution 1.2.0): escolha explícita entre `deepseek`
  (`ChatDeepSeek(model="deepseek-v4-flash")`) e `openai` (`ChatOpenAI(model="gpt-4o-mini")`),
  temperatura 0, por `escolher_llm(provedor)` ou `LLM_PROVEDOR`; padrão `openai`. Sem troca
  automática. A célula imprime provedor e modelo.
- **Rationale**: mesmo nome de modelo usado pelo professor na aula 2; escolha explícita conforme o princípio
  VI.
- **Alternatives**: troca automática em tempo de execução (rejeitada pela constitution 1.1.0).

## R2. Saída estruturada do NLU

- **Decision**: `ChatPromptTemplate` com `MessagesPlaceholder("historico")` encadeado em
  `llm.with_structured_output(AnaliseNLU)`.
- **Rationale**: padrão da aula 5 (seção 4.1) citado no artefato do Projeto; o histórico entra
  como lista de mensagens explícita (o `MemorySaver` é da Fase 3).
- **Risk**: o DeepSeek pode falhar em function calling estruturado. Mitigação: o mesmo código
  roda com `escolher_llm("openai")`; a bateria da seção mostra qual modelo foi usado.

## R3. Saída JSON da investigação e `stream`

- **Decision**: `ChatPromptTemplate | llm | JsonOutputParser(pydantic_object=AnaliseIncidente)`
  seguido de validação Pydantic (`AnaliseIncidente.model_validate`) e `.with_retry(
  stop_after_attempt=2)` na chain de investigação.
- **Rationale**: `JsonOutputParser` faz streaming de JSON parcial, o que cumpre FR-011 de forma
  visível; o `format_instructions` do parser entra no prompt; a validação garante o schema
  (FR-008). Uma nova tentativa, conforme a clarificação.
- **Alternatives**: `with_structured_output` também na investigação (não mostra o JSON sendo
  montado no `stream`); `PydanticOutputParser` da aula 4 (não faz streaming parcial).

## R4. Moderação

- **Decision**: cliente `openai` (`OpenAI().moderations.create(model="omni-moderation-latest",
  input=texto_mascarado)`) dentro de uma função comum composta no pipe. Sem `OPENAI_API_KEY` ou
  com qualquer exceção: devolve `ResultadoModeracao(status="pulada", motivo=...)` e imprime o
  aviso uma vez por sessão.
- **Rationale**: endpoint gratuito; falha nunca quebra o notebook (princípio VII).
- **Alternatives**: classificar conteúdo só pelo NLU (já existe como camada 2; a moderação é a
  camada 1 decidida em 01/11).

## R5. Máscara local de segredos e dados pessoais

- **Decision**: função determinística com expressões regulares, sem LLM, aplicada antes da
  moderação. Padrões: `senha|password|pwd|secret|token|api[_-]?key` seguidos de `=` ou `:`;
  `Bearer <token>`; chaves no formato `sk-...`, `ghp_...`, `AKIA...`; JWT (`eyJ...`); e-mail;
  CPF (`000.000.000-00` ou 11 dígitos); cartão (13 a 19 dígitos, com ou sem separadores). Cada
  ocorrência vira `[SEGREDO]`, `[EMAIL]`, `[CPF]` ou `[CARTAO]`.
- **Rationale**: testável com pytest; cumpre FR-000 e SC-004.
- **Alternatives**: bibliotecas de PII (Presidio): dependência pesada para o prazo.

## R6. Pré-processamento e impressão digital

- **Decision**: função comum que (a) remove frames repetidos de bibliotecas (`java.`, `sun.`,
  `org.springframework`, `site-packages`, `node_modules`), mantendo a primeira linha da exceção,
  o primeiro frame da aplicação e as linhas `Caused by`; (b) corta o texto em 4.000 caracteres;
  (c) extrai `ImpressaoDigital(excecao, primeiro_frame, servico)`, com o serviço vindo do NLU ou
  de nomes conhecidos (`pedidos-api`, `pagamentos-api`, `estoque-worker`, `auth-api`).
- **Pipeline**: entra no pipe LCEL como função comum (`RunnableLambda`). A célula de
  demonstração aplica `@chain` à mesma função e compara as saídas (`==`), como o quadro
  imperativo × declarativo da aula 2.

## R7. Roteamento

- **Decision**: `RunnableBranch` sobre `analise_nlu.intencao`: guardrails e saudação/fora do
  escopo vão para resposta fixa; `gerar_relatorio` e `confirmar_causa` vão para resposta fixa
  "chega na Fase N"; o resto vai para a investigação. Moderação sinalizada sai antes, por um
  segundo `RunnableBranch` no topo.
- **Rationale**: o artefato do Projeto e o princípio III fixam `RunnableBranch`; a aula 3 mostra
  o mesmo papel com `RunnableLambda(rotear_execucao)`, citado na justificativa LCEL.

## R8. Onde o código mora

- **Decision**: schemas, funções determinísticas, templates e a composição LCEL no pacote
  `agente/` (testados com pytest); a seção 1 exibe o código dos templates e da composição com
  `inspect.getsource` e escreve em células as demonstrações (`invoke`/`batch`/`stream`, `@chain`,
  bateria, justificativas), porque são a evidência da rubrica. A primeira célula do
  notebook coloca a raiz do repositório no `sys.path`; se o notebook rodar isolado (ex.: Colab),
  clona o repositório público `erato690/incident-agent`.
- **Rationale**: o código reaproveitado pelas fases seguintes e pelo `app/` não é duplicado, e
  o professor vê o que é avaliado na própria célula.
- **Alternatives**: tudo no notebook (sem testes unitários e com duplicação no `app/`); tudo no
  pacote (rubrica fica escondida).

## R9. Dependências e testes

- **Decision**: Python 3.11+; `langchain`, `langchain-core`, `langchain-openai`,
  `langchain-deepseek`, `openai`, `pydantic>=2`, `python-dotenv`, `jupyter`; testes com
  `pytest` só para o determinístico (máscara, pré-processamento, schemas, roteamento com NLU
  falso). O comportamento com LLM é verificado pela bateria da seção (FR-016).
- **Rationale**: TDD onde o resultado é determinístico; LLM verificado por bateria visível ao
  professor.

## R10. Mensagens de teste

- **Decision**: `dados_dummy/fase1_mensagens.json` com ~16 mensagens: uma por cenário do
  `incident-shop` (texto de erro de cada `cenarios.py`), mais saudação, fora do escopo, pedido
  de ação, injeção, sintoma sem erro, OOMKilled, mensagem mista, mensagem vazia e uma com
  segredos. Cada item traz `rota_esperada`.
- **Rationale**: FR-016 e SC-002/003/004.
