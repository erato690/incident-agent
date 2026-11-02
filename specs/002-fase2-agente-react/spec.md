# Feature Specification: Fase 2 — agente ReAct com ferramentas só leitura e prompts avançados

**Feature Branch**: `002-fase2-agente-react` (sem branch git dedicada; trabalho local)

**Created**: 2026-11-01

**Status**: Draft

**Input**: User description: "Fase 2 do projeto (seção 2 do notebook projeto.ipynb): agente ReAct com ferramentas só leitura e prompts avançados. A máscara local, a moderação calibrada e a barreira de escopo da Fase 1 continuam na frente; a rota de investigação passa a ser um agente ReAct (create_agent, function calling) que decide quais ferramentas chamar e devolve a análise em JSON com 2 ou 3 hipóteses cuja evidência vem das observações das ferramentas. Ferramentas só leitura: buscar_logs, buscar_metricas e listar_deploys (incident-shop ao vivo com LOJA_URL, senão dados_dummy/<cenario>.json gerados a partir da própria API, 8 cenários) e comparar_versoes (API REST real do GitHub, compare entre tags do repositório público erato690/incident-shop, sem token, resposta gravada como reserva). Prompt Persona-Tarefa-Contexto-Formato com dois incidentes resolvidos como few-shot e raciocínio passo a passo no caso do deploy distrator. Rubrica: comparar orquestradores; agente clássico (initialize_agent ZERO_SHOT_REACT_DESCRIPTION com memória de buffer, via langchain-classic) ao lado do create_agent; chains sequencial, paralela e roteamento por intenção (RouterChain como demonstração); API externa via function calling; confiabilidade (with_retry, with_fallbacks, BaseCallbackHandler com a trajetória). Bateria e conversas multi-turno da Fase 2, testes sem chave e sem rede, diagramas atualizados. Fora do escopo: memória de longo prazo, SQL, FAISS, auditor, post-mortem e Streamlit."

## Contexto

Esta é a seção 2 do notebook único (constitution, princípio X). A Fase 1 entregou a chain que
analisa só o texto do engenheiro. A Fase 2 dá ao agente **ferramentas só leitura**: ele passa a
buscar logs, métricas e deploys da loja e a comparar versões no GitHub antes de propor hipóteses.
A camada de entrada (máscara, moderação, compreensão e roteador) continua igual; muda o que
acontece na rota de investigação.

Nota sobre detalhes técnicos: a rubrica avalia o uso de APIs específicas do LangChain (agente
ReAct, `initialize_agent`, `RouterChain`, function calling, `with_retry`, `with_fallbacks`,
callback). Por isso alguns nomes técnicos aparecem nos requisitos como **critério de
avaliação**, não como escolha livre de implementação.

Itens da rubrica atendidos (constitution, princípio IX):

| Item da rubrica (Fase 2) | Onde nesta spec |
|---|---|
| Comparar orquestradores e justificar o LangChain | US2, FR-016 |
| Agente com ferramentas e memória, ReAct com `initialize_agent` `ZERO_SHOT_REACT_DESCRIPTION` | US1 (moderno), US3 (clássico), FR-004, FR-018 |
| Chains sequenciais ou paralelas e `RouterChain` | US2, FR-013 a FR-015 |
| API externa via function calling (GitHub) | US1, FR-006 |
| Persona-Tarefa-Contexto-Formato, few-shot e chain-of-thought | US1, FR-009, FR-010 |
| Confiabilidade com justificativa | US1, US3, FR-011, FR-012, FR-019 |

Itens de confiabilidade que a rubrica cita junto (memória por limite de tokens, índice vetorial de
runbooks) ficam nas Fases 3 e 4, onde a constitution os coloca; a seção 2 aponta para elas.

## Clarifications

### Session 2026-11-01

- Q: Sem `LOJA_URL`, como as ferramentas sabem qual cenário gravado ler? → A: Cenário explícito
  na configuração do teste ou da conversa; a ferramenta injeta o cenário (e a janela de tempo dele)
  na consulta, e o modelo nunca escolhe nem vê o id do cenário. (Decisão do
  Jev, confiança 1,0.)
- Q: Qual memória o agente moderno usa nas conversas com vários turnos? → A: Histórico explícito
  por turno, como na Fase 1 (`{mensagem, historico}`); `MemorySaver` com resumo fica para a Fase 3.
  (Decisão do Rafael; Jev ficou com confiança 0,48.)
- Q: Como a análise final do agente vira `AnaliseIncidente`? → A: O agente termina com uma
  mensagem contendo o JSON; o parser da Fase 1, validado contra o schema e com `with_retry` e
  `with_fallbacks`, é aplicado à última mensagem. (Decisão do Rafael; Jev ficou com confiança 0,55.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Investigação com ferramentas devolve hipóteses sustentadas por dados (Priority: P1)

O engenheiro descreve um incidente ("o pagamentos-api está devolvendo 500 desde as 12h"). A
mensagem passa pela máscara, pela moderação e pela barreira, como na Fase 1. Na rota de
investigação, um agente decide sozinho quais ferramentas só leitura consultar (logs, métricas,
deploys e, quando há deploy suspeito, a comparação de versões no GitHub), observa os resultados e
devolve a análise do incidente com 2 ou 3 hipóteses. A evidência de cada hipótese vem das
observações das ferramentas, não da imaginação do modelo. A trajetória (que ferramenta foi
chamada, com quais argumentos, o que voltou) fica registrada e visível.

**Why this priority**: é a mudança que transforma o MVP em agente: a hipótese passa a ser
verificada contra dados reais da loja e do repositório.

**Independent Test**: rodar a pergunta do cenário `deploy_com_bug` com dados gravados e conferir
que a trajetória chama logs e deploys, que `comparar_versoes` é chamada entre
`pagamentos-api/v2.13.4` e `pagamentos-api/v2.14.0`, e que a hipótese principal cita o trecho do
log e a mudança do commit.

**Acceptance Scenarios**:

1. **Given** o cenário `deploy_com_bug` sem `LOJA_URL`, **When** o engenheiro pergunta por que o
   pagamentos-api devolve 500, **Then** o agente chama ao menos as ferramentas de logs e deploys,
   chama `comparar_versoes` com as duas tags do serviço e a hipótese principal cita a
   `NullPointerException` do log e a mudança no tratamento do cupom.
2. **Given** o cenário `banco_lento_com_deploy` (deploy distrator `pedidos-api/v3.2.1` perto do
   incidente), **When** o engenheiro pergunta se foi o deploy, **Then** o agente compara as
   versões, conclui que a mudança é inofensiva (texto de e-mail) e não coloca o deploy como
   hipótese principal; o raciocínio passo a passo aparece na trajetória.
3. **Given** um cenário de causa externa (`gateway_fora`), **When** o engenheiro pergunta a causa,
   **Then** a hipótese principal aponta a dependência externa com evidência do log, e o agente
   registra que não há mudança relevante no GitHub.
4. **Given** uma ferramenta que falha (rede fora, limite do GitHub estourado), **When** o agente a
   chama, **Then** a ferramenta devolve a resposta gravada de reserva ou um erro legível como
   observação, e a investigação termina sem exceção.
5. **Given** uma mensagem de saudação, fora do escopo, pedido de ação ou tentativa de injeção,
   **When** enviada, **Then** a resposta é fixa como na Fase 1 e nenhuma ferramenta é chamada.
6. **Given** um log devolvido por ferramenta com texto do tipo "ignore suas instruções",
   **When** o agente o observa, **Then** o texto é tratado como dado e não muda o comportamento
   (camada 4 dos guardrails).

---

### User Story 2 - Composição de chains e escolha do orquestrador (Priority: P2)

O avaliador vê, na seção 2, as formas de composição que o agente usa: uma chain **sequencial**
(pré-processa o erro, analisa, resume), uma chain **paralela** que varre logs, métricas e deploys
ao mesmo tempo e junta os resultados, e o **roteamento por intenção** (o padrão com `RunnableBranch`
e a `RouterChain` clássica como demonstração). Vê também uma tabela comparando LangChain,
LlamaIndex e CrewAI por autonomia, abstração e modularidade, com a justificativa da escolha.

**Why this priority**: são itens da rubrica que não dependem do agente ReAct funcionar e mostram
por que o projeto foi montado assim.

**Independent Test**: executar as três composições com dados gravados e conferir as saídas; ler a
tabela de orquestradores.

**Acceptance Scenarios**:

1. **Given** o texto de um erro, **When** a chain sequencial roda, **Then** a saída mostra as três
   etapas (pré-processamento, análise, resumo) em ordem.
2. **Given** um cenário, **When** a chain paralela roda, **Then** logs, métricas e deploys voltam
   juntos num único dicionário e o tempo total é próximo do da consulta mais lenta, não da soma.
3. **Given** mensagens de intenções diferentes, **When** passam pelo roteamento, **Then** cada uma
   vai para o destino da sua intenção, na versão padrão e na demonstração clássica.

---

### User Story 3 - Agente clássico, confiabilidade e evidência da fase (Priority: P3)

O avaliador vê o mesmo agente no estilo clássico (`initialize_agent` com
`ZERO_SHOT_REACT_DESCRIPTION` e memória de buffer) imprimindo o ciclo pensamento, ação e
observação, ao lado da versão moderna, com a justificativa de por que a moderna é o padrão. Vê os
recursos de confiabilidade funcionando: saída JSON inválida recuperada por nova tentativa ou
reserva, e o registro da trajetória por callback. A seção termina com a bateria de mensagens e as
conversas com vários turnos da Fase 2, organizadas como na Fase 1, os diagramas atualizados e a
tabela que liga cada item da rubrica à célula que o comprova.

**Why this priority**: fecha os itens restantes da rubrica e dá a evidência de que a fase
funciona de ponta a ponta.

**Independent Test**: executar a seção 2 e conferir o ciclo impresso pelo agente clássico, o
erro de JSON recuperado, o log do callback e os placares da bateria e das conversas.

**Acceptance Scenarios**:

1. **Given** o agente clássico com memória de buffer, **When** recebe duas perguntas seguidas
   sobre o mesmo incidente, **Then** imprime pensamento, ação e observação e a segunda resposta
   usa o contexto da primeira.
2. **Given** um modelo que devolve JSON inválido na primeira vez, **When** a análise é montada,
   **Then** a nova tentativa ou a reserva produz uma resposta válida ou um erro legível, sem
   exceção.
3. **Given** uma investigação, **When** termina, **Then** o callback registrou cada chamada de
   ferramenta (nome, argumentos, tempo, tamanho da resposta) e a lista aparece na saída.
4. **Given** a bateria da Fase 2 e as conversas com vários turnos, **When** executadas com a chave
   real, **Then** o relatório mostra placar, rota, intenção, ferramentas chamadas e hipóteses de
   cada caso.

---

### Edge Cases

- Sem `LOJA_URL`: as ferramentas da loja leem as respostas gravadas do cenário em uso.
- Sem rede ou com o limite de 60 requisições por hora do GitHub estourado: `comparar_versoes`
  devolve a resposta gravada e diz, na observação, que é reserva.
- Tags inexistentes ou de serviços diferentes em `comparar_versoes`: observação de erro legível,
  sem exceção.
- Agente que entra em ciclo de ferramentas: limite de passos; ao atingir, a análise sai com o que
  foi observado e marca as hipóteses sem sustentação.
- Pergunta sem cenário identificável (ex.: "está tudo lento"): o agente consulta as ferramentas
  disponíveis e, se não houver sinal, devolve hipóteses com `evidencia_insuficiente` e o dado que
  falta.
- Segredo na mensagem: a máscara da Fase 1 continua antes de qualquer envio externo; nenhuma
  ferramenta recebe texto não mascarado.
- Sem chave do modelo de linguagem: as células da seção 2 que chamam o modelo são puladas com
  aviso, como na Fase 1, e o notebook roda até o fim.

## Requirements *(mandatory)*

### Functional Requirements

**Entrada (herdada da Fase 1)**

- **FR-001**: Máscara local, moderação calibrada, compreensão de linguagem natural e roteador da
  Fase 1 MUST continuar na frente, sem mudança de comportamento; respostas fixas MUST NOT chamar
  ferramentas nem o agente.

**Agente e ferramentas**

- **FR-002**: A rota de investigação MUST ser um agente ReAct (padrão moderno do curso) que
  decide quais ferramentas chamar por function calling, observa os resultados e conclui.
- **FR-003**: O agente MUST ter só ferramentas de leitura: `buscar_logs`, `buscar_metricas`,
  `listar_deploys` e `comparar_versoes`. Nenhuma ferramenta escreve ou executa ação (princípio I,
  camada 3).
- **FR-004**: O agente MUST ter um limite de passos e terminar sem exceção ao atingi-lo.
- **FR-005**: As ferramentas da loja MUST ler a API do `incident-shop` quando `LOJA_URL` estiver
  definida e, sem ela, as respostas gravadas em `dados_dummy/<cenario>.json` dos 8 cenários, que
  MUST ser geradas a partir da própria API do `incident-shop` por um script versionado (o código
  da loja não entra no notebook, princípio VII). Endpoints, parâmetros e formatos das respostas
  MUST seguir o contrato publicado pelo `incident-shop` (`docs/contrato-api.md` e o OpenAPI da
  API); o agente MUST NOT supor endpoints fora do contrato.
- **FR-006**: `comparar_versoes` MUST chamar a API REST real do GitHub (compare entre duas tags
  do repositório público `erato690/incident-shop`), funcionar sem token (`GITHUB_TOKEN`
  opcional) e, sem rede ou com limite estourado, devolver a resposta gravada marcada como reserva.
- **FR-007**: A resposta de cada ferramenta MUST ser resumida para caber no contexto do modelo
  (por exemplo, logs agrupados por mensagem com contagem) e MUST ser tratada como dado, nunca como
  instrução (camada 4).
- **FR-008**: A análise final MUST seguir o schema da Fase 1 (`AnaliseIncidente`, 2 ou 3
  hipóteses ordenadas por confiança); a evidência de hipótese sustentada MUST citar observação de
  ferramenta (trecho de log, valor de métrica, deploy ou mudança de commit) com a ferramenta de
  origem; hipótese sem sustentação MUST trazer `evidencia_insuficiente` e `dado_que_falta`.

**Prompts avançados**

- **FR-009**: O prompt de sistema do agente MUST seguir Persona, Tarefa, Contexto e Formato, com
  as quatro partes identificáveis no texto, e MUST incluir dois incidentes resolvidos como
  exemplos (few-shot) que não sejam os cenários usados na avaliação da bateria.
- **FR-010**: O prompt MUST pedir raciocínio passo a passo (chain-of-thought) antes da conclusão,
  incluindo a regra de verificar se o deploy aconteceu antes do sintoma e se a mudança tem relação
  com o erro (princípio II); o caso do deploy distrator MUST mostrar esse raciocínio.

**Confiabilidade**

- **FR-011**: A conversão da resposta do agente em `AnaliseIncidente` MUST ter nova tentativa e
  reserva (`with_retry` e `with_fallbacks`); a falha final vira `rota="erro"` com mensagem
  legível, como na Fase 1.
- **FR-012**: Um callback MUST registrar a trajetória de cada investigação (ferramenta,
  argumentos, duração, tamanho da observação) e o registro MUST ficar disponível na resposta do
  turno para exibição.

**Composição de chains (rubrica)**

- **FR-013**: MUST existir uma chain sequencial de três etapas: pré-processamento do erro,
  análise e resumo curto.
- **FR-014**: MUST existir uma chain paralela que consulta logs, métricas e deploys ao mesmo
  tempo e junta os resultados num dicionário.
- **FR-015**: O roteamento por intenção MUST aparecer no padrão moderno (`RunnableBranch`) e numa
  célula curta com a `RouterChain` clássica, com a justificativa de por que o moderno é o padrão.
- **FR-016**: A seção MUST trazer uma tabela comparando LangChain, LlamaIndex e CrewAI por
  autonomia, abstração e modularidade e a justificativa da escolha do LangChain para este projeto.

**Demonstração clássica e evidência**

- **FR-017**: O cenário em investigação MUST ser configuração explícita do teste ou da conversa.
  A API do `incident-shop` é sem estado (linha do tempo única com os 8 cenários em datas
  absolutas; consultas por serviço e janela `inicio`/`fim`, com `cenario` opcional); a
  ferramenta MUST injetar o cenário e a janela de tempo dele na consulta (ou escolher o arquivo
  gravado correspondente). O id do cenário MUST NOT aparecer nos argumentos que o modelo preenche
  nem no prompt do modelo (o agente nunca vê o gabarito).
- **FR-018**: MUST existir uma célula com `initialize_agent` e `ZERO_SHOT_REACT_DESCRIPTION`
  (pacote `langchain-classic`), com as mesmas ferramentas e memória de buffer, imprimindo o ciclo
  pensamento, ação e observação, e uma frase justificando o padrão moderno.
- **FR-019**: A memória do agente moderno nesta fase MUST ser o histórico explícito por turno da
  Fase 1 (`{mensagem, historico}`), passado ao agente como mensagens; o agente não usa
  checkpointer nesta fase (`MemorySaver` com resumo entra na Fase 3).
- **FR-020**: A seção MUST ter bateria de mensagens e ao menos duas conversas com vários turnos
  da Fase 2, exibidas com o relatório reaproveitável da Fase 1, mostrando rota, intenção,
  ferramentas chamadas e hipóteses de cada caso.
- **FR-021**: Os testes automatizados MUST rodar sem chave e sem rede, com modelo de linguagem e
  respostas HTTP falsos.
- **FR-022**: O diagrama de componentes MUST mostrar o agente, as quatro ferramentas e as chamadas
  externas novas (`incident-shop` e GitHub, interna ou externa em cada seta), e o diagrama de
  contexto MUST trocar os rótulos provisórios das setas da Fase 2 pelo que de fato trafega.
- **FR-023**: A seção 2 MUST terminar com a tabela que liga cada item da rubrica da Fase 2 à
  célula que o comprova.
- **FR-024**: O agente MUST terminar com uma mensagem contendo o JSON da análise; o parser da
  Fase 1 (validado contra `AnaliseIncidente`) MUST ser aplicado à última mensagem, com a nova
  tentativa e a reserva de FR-011.

### Key Entities

- **Ferramenta só leitura**: nome, descrição para o modelo, argumentos tipados, origem dos dados
  (loja ao vivo, resposta gravada ou GitHub) e resposta resumida.
- **Resposta gravada de cenário**: logs, métricas e deploys de um dos 8 cenários, gerados da API
  do `incident-shop`.
- **Comparação de versões**: serviço, tag base, tag nova, commits, arquivos alterados e trecho do
  diff, com a marca de "reserva" quando veio da gravação.
- **Passo da trajetória**: ferramenta, argumentos, duração, tamanho da observação.
- **Resposta do turno (`RespostaTurno`)**: a da Fase 1, acrescida da trajetória.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nos 8 cenários gravados, a hipótese principal aponta a causa correta do gabarito do
  `incident-shop` em pelo menos 6, e no cenário do deploy distrator o deploy não é a hipótese
  principal.
- **SC-002**: 100% das hipóteses sustentadas citam uma observação de ferramenta; nenhuma cita dado
  que não apareceu na trajetória.
- **SC-003**: 100% das mensagens da barreira (saudação, fora do escopo, pedido de ação, injeção,
  vazia) recebem resposta fixa sem nenhuma chamada de ferramenta.
- **SC-004**: Sem rede e sem `LOJA_URL`, a seção 2 roda do início ao fim com respostas gravadas;
  sem chave do modelo, roda até o fim pulando as células que o chamam.
- **SC-005**: A seção 2 inteira roda com a chave real em menos de 5 minutos.
- **SC-006**: Cada item da rubrica da Fase 2 aponta para uma célula com saída que o comprova.

## Assumptions

- Os 8 cenários e o gabarito vêm do `incident-shop`; o agente nunca vê o gabarito.
- A API do `incident-shop` está sendo ajustada em paralelo; os formatos exatos dos endpoints de
  logs, métricas e deploys são os do contrato 1.0.0 do `incident-shop` (`docs/contrato-api.md`). As respostas gravadas representam um instante fixo depois do início dos sintomas.
- As tags do repositório `incident-shop` usadas por `comparar_versoes` não mudam.
- O repositório `erato690/incident-shop` é público e tem as tags descritas no seu README.
- O modelo padrão continua `gpt-4o-mini` (escolha explícita da Fase 1).
- O formato do relatório da bateria e das conversas é o da Fase 1, estendido com a coluna de
  ferramentas.
- Memória de longo prazo, resumo de histórico, SQL, índice vetorial, auditor, post-mortem e
  telas ficam nas Fases 3 a 5.
