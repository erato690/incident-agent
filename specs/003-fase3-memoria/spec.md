# Feature Specification: Fase 3 — memória de curto e longo prazo

**Feature Branch**: `003-fase3-memoria` (sem branch git dedicada; trabalho local em `main`)

**Created**: 2026-11-02

**Status**: Draft

**Input**: User description: "Fase 3 do projeto (seção 3 do notebook projeto.ipynb): memória de
curto e longo prazo. Memória de curto prazo da conversa: checkpointer (MemorySaver) por
thread_id, um por incidente, com resumo das mensagens antigas quando o histórico crescer (sem
corte por limite de tokens), mantendo as últimas mensagens. Memória de longo prazo: só fatos
confirmados pelo engenheiro (ex.: causa confirmada por serviço/cenário), usados em investigações
futuras ("já aconteceu antes?"). confirmar_causa deixa de ser resposta fixa e passa a registrar a
causa confirmada na memória de longo prazo. Itens da rubrica da Fase 3: curto × longo prazo pela
CoALA em tabela; janela de contexto com busca (filtro de relevância e janela deslizante + busca
na episódica com decaimento temporal); comparar ferramentas de memória (LangMem × Mem0 × Letta) e
justificar o padrão próprio; chatbot com ConversationBufferMemory clássica e depois MemorySaver
como padrão, com justificativa; intenção e entidades com AnaliseNLU em turnos reais; multi-turno
com decomposição impresso. Considerar as notas em specs/notas/proximas-fases-causas-pendentes.md
como opção de escopo a decidir (nível 3). Prompts em inglês; testes sem chave e sem rede; bateria
com a chave no notebook; seção 3 independente das anteriores. Fora do escopo: SQL e FAISS/RAG
(Fase 4), auditor, post-mortem, Streamlit e LangSmith (Fase 5)."

## Contexto

Esta é a seção 3 do notebook único (constitution, princípio X). As Fases 1 e 2 entregaram a
barreira de entrada (máscara, moderação, compreensão e roteador) e o agente com ferramentas só
leitura, que acerta a causa em 7 de 8 cenários. Até aqui, a conversa só existe enquanto quem
chama a função repassa o histórico, e o agente esquece tudo entre um incidente e outro: a
confirmação da causa recebe uma resposta fixa ("chega na Fase 3").

A Fase 3 dá memória ao agente, seguindo o princípio IV da constitution ("memória só com fato
confirmado"):

- **Curto prazo (memória de trabalho):** cada incidente é uma conversa com identificador próprio.
  O agente lembra os turnos anteriores sem que o chamador os repasse, e resume os turnos antigos
  quando a conversa cresce, mantendo os mais recentes inteiros.
- **Longo prazo, memória episódica:** histórico de incidentes (episódios) com a causa
  confirmada. Quando o engenheiro confirma a causa, o agente registra ou atualiza o episódio do
  incidente. Em incidentes futuros, ele consulta os episódios ("já aconteceu antes?") e cita o
  incidente anterior como evidência.
- **Longo prazo, memória semântica (a wiki):** fatos e regras sobre produtos e serviços (ex.:
  limite de requisições da API do GitHub, limites de um serviço interno), cada um com fonte
  (documentação, usuário ou incidente), data de verificação e validade. Quando falta ou venceu
  um fato, o agente pesquisa fora; se não achar, pergunta ao usuário e grava a resposta. **Nesta
  fase só a interface fica pronta** (registrar e consultar fatos semânticos com fonte, data e
  validade); a pesquisa externa e a pergunta ao usuário ficam para a Fase 4 (decisão D1).

Episódica e semântica são memórias separadas: schemas, nomes e espaços de armazenamento
diferentes, sem mistura.

Nota sobre detalhes técnicos: a rubrica avalia o uso de APIs específicas (checkpointer por
conversa, `ConversationBufferMemory` clássica, busca na memória). Por isso alguns nomes técnicos
aparecem nos requisitos como **critério de avaliação**, não como escolha livre de implementação.

Itens da rubrica atendidos (constitution, princípio IX):

| Item da rubrica (Fase 3) | Onde nesta spec |
|---|---|
| Curto × longo prazo pela arquitetura cognitiva CoALA (trabalho; episódica, semântica, procedural) | US3, FR-015 |
| Janela de contexto com busca: filtro de relevância, janela deslizante e busca na episódica com decaimento temporal | US1, US2, FR-004, FR-008, FR-009 |
| Comparar ferramentas de memória (LangMem, Mem0, Letta) e justificar o padrão próprio | US3, FR-016 |
| Chatbot com `ConversationBufferMemory` clássica e depois `MemorySaver` como padrão, com justificativa | US2, US3, FR-001, FR-017 |
| Intenção e entidades com `AnaliseNLU` em turnos reais | US2, FR-011 |
| Multi-turno com decomposição (sintoma, "foi o deploy?", "e o banco?", "já aconteceu antes?") impresso | US2, FR-012 |

## Clarifications

### Session 2026-11-02

- Q: O que é cada memória? → A (Rafael): semântica = a wiki de fatos e regras sobre produtos e
  serviços, com fonte, data de verificação e validade; episódica = histórico de incidentes com a
  causa confirmada; curto prazo = a conversa atual. Sem misturar semântica e episódica.
- Q: As melhorias das notas entram nesta fase? → A (Rafael, D1): não. A wiki com pesquisa externa
  e pergunta ao usuário vai para a Fase 4; nesta fase a interface semântica fica pronta, sem
  pesquisa. A ferramenta de estatísticas do banco fica para a Fase 4 com o contrato 1.1.0 do
  `incident-shop` (só nota).
- Q: Como o agente consulta a memória de longo prazo durante a investigação? → A: Por uma
  ferramenta só leitura nova (`consultar_memoria`), que aparece na trajetória; o prompt orienta
  chamá-la em "já aconteceu antes?" e no início das investigações. (Nível 2; Jev, confiança 0,96.)
- Q: No mesmo incidente, o engenheiro confirma uma causa diferente da já registrada; o que fazer?
  → A (Rafael, D5): resolução de memória como no material do curso. Um modelo decide inserir um
  episódio novo ou atualizar um existente, com motivo registrado; atualizar arquiva o episódio
  antigo (não apaga) e cria um novo ativo com referência ao anterior; a busca só vê os ativos; a
  resposta avisa a troca.
- Q: Como a memória episódica se alinha ao material do curso? → A (Rafael, D5): episódio com
  resumo do sintoma (indexado com serviço, causa e evidência); metadados data, serviço,
  incidente, sessão de origem e status; relevância por similaridade, idade e número de acessos;
  a seção 3 mostra a decisão com o motivo e o store antes e depois.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Causa confirmada vira episódio e ajuda no próximo incidente (Priority: P1)

O engenheiro investiga um incidente com o agente e, ao final, afirma a causa como fato verificado
("confirmado: foi o deploy v3.2.0, revertemos e normalizou"). Em vez da resposta fixa das fases
anteriores, o agente registra a causa confirmada, ligada ao serviço e ao incidente, e responde
dizendo exatamente o episódio que guardou. Dias depois, num incidente novo no mesmo serviço, o engenheiro
pergunta "isso já aconteceu antes?". O agente consulta a memória episódica, encontra o incidente
anterior e o cita como evidência, com a data, sem tratar o episódio antigo como prova de que a causa
atual é a mesma.

**Why this priority**: é a mudança de comportamento visível da fase (a confirmação deixa de ser
resposta fixa) e o centro do princípio IV. Sem ela não há memória episódica.

**Independent Test**: com a memória episódica vazia, uma conversa termina com a confirmação
da causa; uma segunda conversa, com outro identificador, pergunta se já aconteceu antes no mesmo
serviço e recebe o incidente anterior citado. Roda sem chave com modelo falso.

**Acceptance Scenarios**:

1. **Given** uma conversa em que o engenheiro afirma a causa como fato verificado e o serviço é
   conhecido (dito ou herdado do histórico), **When** o turno é processado, **Then** um episódio
   é registrado com serviço, causa, incidente de origem e data, e a resposta mostra o que foi
   registrado.
2. **Given** uma mensagem que apenas pergunta ou sugere a causa ("será que foi o deploy?"),
   **When** o turno é processado, **Then** nada é registrado e a conversa segue como
   investigação.
3. **Given** uma confirmação sem serviço identificável, **When** o turno é processado, **Then**
   nada é registrado e a resposta pede o serviço.
4. **Given** um episódio registrado para o serviço X, **When** o engenheiro de outro incidente no
   serviço X pergunta "já aconteceu antes?", **Then** a resposta cita o incidente anterior, a causa
   e a data, marcado como histórico, e a análise atual continua apoiada nas ferramentas.
5. **Given** dois episódios do mesmo serviço com datas diferentes, **When** a memória é consultada,
   **Then** o mais recente vem primeiro, a menos que o mais antigo seja claramente mais parecido
   com o incidente atual.
6. **Given** uma confirmação que contém um segredo (ex.: token), **When** o episódio é registrado,
   **Then** o texto guardado já está mascarado.

---

### User Story 2 - Conversa longa por incidente sem repassar histórico (Priority: P2)

O engenheiro conversa sobre um incidente em vários turnos: descreve o sintoma, pergunta "foi o
deploy?", depois "e o banco?", depois "já aconteceu antes?". Cada turno informa só a mensagem e o
identificador do incidente; o agente recupera sozinho o que já foi dito. Quando a conversa passa
de um tamanho combinado, os turnos antigos são condensados num resumo e os mais recentes ficam
inteiros, sem descartar informação por simples corte. Conversas de incidentes diferentes não se
misturam. O notebook imprime, a cada turno, a intenção e as entidades reconhecidas (serviço,
ambiente, janela de tempo, erro, dado faltante) e a decomposição da conversa.

**Why this priority**: entrega os itens de memória de curto prazo e de compreensão multi-turno da
rubrica e é a base em que a US1 se apoia para herdar o serviço do histórico.

**Independent Test**: uma conversa de 4 turnos com um identificador e uma segunda conversa com
outro identificador; o segundo turno da primeira herda o serviço do primeiro sem histórico
repassado, e a segunda conversa não vê nada da primeira. Uma conversa longa gera um resumo e
mantém os últimos turnos inteiros. Roda sem chave.

**Acceptance Scenarios**:

1. **Given** um turno com mensagem e identificador de incidente já usado, **When** o turno é
   processado, **Then** o agente usa os turnos anteriores daquele incidente sem que o chamador os
   envie.
2. **Given** dois incidentes com identificadores diferentes, **When** cada um recebe turnos,
   **Then** nenhum turno de um aparece no contexto do outro.
3. **Given** uma conversa que passa do limite de turnos combinado, **When** o próximo turno é
   processado, **Then** os turnos antigos viram um resumo, os últimos turnos ficam inteiros e o
   resumo preserva serviço, sintoma, hipóteses levantadas e o que já foi descartado.
4. **Given** a conversa de decomposição (sintoma, "foi o deploy?", "e o banco?", "já aconteceu
   antes?"), **When** roda no notebook com a chave, **Then** cada turno imprime intenção,
   entidades e a resposta, e o último turno consulta a memória de longo prazo.
5. **Given** uma mensagem bloqueada pela barreira (moderação ou fora do escopo), **When** é
   processada dentro de uma conversa, **Then** a resposta fixa é dada e a mensagem bloqueada não
   entra no contexto dos turnos seguintes.

---

### User Story 3 - Explicação da memória e evidência da fase (Priority: P3)

Quem avalia o notebook encontra, na seção 3: uma tabela que separa memória de curto e de longo
prazo pela arquitetura cognitiva CoALA (trabalho, episódica, semântica, procedural) e diz o que o
agente guarda em cada uma; uma comparação de ferramentas de memória (LangMem, Mem0, Letta) com a
justificativa do padrão próprio; o chatbot com memória de buffer clássica ao lado da versão com
checkpointer, com a justificativa da escolha; a bateria e as conversas da Fase 3 com a chave; e
um diagrama atualizado com a memória.

**Why this priority**: são itens de avaliação que dependem das US1 e US2 prontas para mostrar
saída real.

**Independent Test**: a seção 3 roda do Setup até o fim sozinha; sem chave, as células com modelo
são puladas e as tabelas, o diagrama e os testes aparecem.

**Acceptance Scenarios**:

1. **Given** o notebook, **When** a seção 3 é aberta, **Then** a tabela da CoALA mostra, para
   cada tipo de memória, o que o agente guarda, quando escreve, quando lê e em que fase entra.
2. **Given** a comparação de ferramentas, **When** é lida, **Then** cada ferramenta é avaliada
   pelos mesmos critérios e a escolha do padrão próprio tem justificativa ligada ao princípio IV.
3. **Given** a célula do chatbot clássico, **When** roda com a chave, **Then** duas perguntas
   seguidas mostram a memória de buffer funcionando, e a célula seguinte mostra o mesmo diálogo
   com o checkpointer.
4. **Given** a bateria da Fase 3, **When** roda com a chave, **Then** o relatório mostra, por
   mensagem ou conversa, rota, intenção, se houve registro na memória e se a memória foi
   consultada.

---

### Edge Cases

- Confirmação repetida da mesma causa no mesmo incidente: não duplica o episódio.
- Confirmação de causa diferente no mesmo incidente: a resolução de memória arquiva o episódio
  antigo e cria um novo ativo; a resposta avisa a troca.
- Engenheiro confirma uma causa que o agente nunca levantou: registra, porque quem confirma é o
  engenheiro, e marca a origem como "informada pelo engenheiro".
- Pedido para "esquecer" ou apagar um episódio: fora do escopo nesta fase; resposta explica que a
  memória só recebe fatos confirmados e que a remoção é manual.
- Tentativa de injeção por meio da memória (episódio com texto do tipo "ignore suas instruções"): o
  episódio recuperado é dado, nunca instrução (camada 4 dos guardrails).
- Memória episódica vazia e pergunta "já aconteceu antes?": resposta diz que não há
  incidente confirmado registrado para o serviço, sem inventar.
- Identificador de incidente ausente: o turno roda como conversa nova e avisa que não haverá
  memória de curto prazo entre turnos.
- Resumo falha (erro do modelo): os turnos antigos ficam como estão e o turno segue; nada é
  descartado.
- Sem chave: as células com modelo são puladas; os testes cobrem registro, consulta, resumo e
  isolamento com modelo falso.

## Requirements *(mandatory)*

### Functional Requirements

**Memória de curto prazo**

- **FR-001**: Cada incidente MUST ser uma sessão aberta explicitamente, com identificador
  aleatório (`uuid4`) gerado na abertura e metadados (criada em, serviço, cenário, número de
  turnos); a memória de curto prazo MUST usar um checkpointer (`MemorySaver`) chaveado por esse
  identificador (`thread_id`).
- **FR-002**: Um turno MUST receber só a mensagem e o identificador; o histórico MUST vir do
  checkpointer, não do chamador.
- **FR-003**: Conversas com identificadores diferentes MUST NOT compartilhar mensagens.
- **FR-004**: Quando a conversa passar de um limite configurável de mensagens, as mensagens
  antigas MUST ser substituídas por um resumo gerado pelo modelo, e as últimas N mensagens MUST
  ficar inteiras (janela deslizante). Corte por limite de tokens MUST NOT ser usado (princípio IV).
- **FR-005**: O resumo MUST preservar serviço, sintoma, hipóteses levantadas, hipóteses
  descartadas e causas confirmadas; o prompt do resumo MUST estar em inglês e terminar com
  "Always answer in Brazilian Portuguese.".
- **FR-006**: Mensagens bloqueadas pela barreira (moderação acima do limiar, injeção, conteúdo
  proibido) MUST NOT entrar no contexto dos turnos seguintes; o texto guardado MUST estar
  mascarado (camada 1).

**Memória de longo prazo: episódica e semântica**

- **FR-007**: A intenção `confirmar_causa` MUST registrar um episódio com: serviço, causa,
  evidência citada pelo engenheiro (se houver), incidente de origem (identificador da conversa),
  data e origem ("levantada pelo agente" ou "informada pelo engenheiro"). Um episódio por incidente: nova
  confirmação com causa diferente MUST atualizar o episódio e a resposta MUST avisar a troca. A
  resposta MUST mostrar o episódio registrado. Sem serviço identificável, MUST NOT registrar e MUST pedir o serviço.
- **FR-008**: Só `confirmar_causa` MAY escrever na memória episódica. Hipóteses, análises e
  perguntas MUST NOT ser registradas (princípio IV).
- **FR-009**: A consulta à memória episódica MUST filtrar por serviço e status ativo, comparar o
  sintoma atual com o resumo dos episódios e ordenar por similaridade, idade (decaimento) e número
  de acessos, devolvendo no máximo K episódios e somando um acesso a cada um.
- **FR-021**: Ao registrar, MUST buscar episódios ativos parecidos do mesmo serviço e um modelo
  MUST decidir inserir novo ou atualizar existente, com motivo registrado; atualizar MUST
  arquivar o antigo (não apagar) e criar um novo ativo com referência ao anterior.
- **FR-010**: O agente MUST consultar a memória episódica nas investigações por uma
  ferramenta só leitura (`consultar_memoria`), e episódios recuperados MUST aparecer como histórico citado ("incidente
  <id> em <data>: <causa>"), nunca como observação atual. O conteúdo recuperado MUST ser tratado
  como dado, nunca como instrução.

**Compreensão multi-turno**

- **FR-011**: A compreensão (`AnaliseNLU`) MUST continuar extraindo intenção, serviço, ambiente,
  janela de tempo, erro e dado faltante, agora a partir do histórico do checkpointer, herdando o
  serviço dos turnos anteriores.
- **FR-012**: O notebook MUST imprimir uma conversa de decomposição de 4 turnos (sintoma, "foi o
  deploy?", "e o banco?", "já aconteceu antes?") com intenção, entidades e resposta por turno.
- **FR-013**: A intenção `comparar_incidente` ("já aconteceu antes?") MUST consultar a memória
  episódica e dizer explicitamente quando não há episódio registrado.
- **FR-014**: Prompts novos ou alterados MUST estar em inglês e terminar com "Always answer in
  Brazilian Portuguese."; campos JSON e respostas fixas continuam em português.

**Explicação e rubrica**

- **FR-015**: A seção 3 MUST ter a tabela da arquitetura cognitiva CoALA com, por tipo
  (trabalho, episódica, semântica, procedural): o que guarda, quando escreve, quando lê e fase.
- **FR-016**: A seção 3 MUST comparar LangMem, Mem0 e Letta pelos mesmos critérios (onde a
  memória mora, quem decide o que guardar, controle sobre fato confirmado, dependências, custo) e
  justificar o padrão próprio.
- **FR-017**: A seção 3 MUST mostrar o chatbot com `ConversationBufferMemory` (pacote
  `langchain-classic`) e o mesmo diálogo com o checkpointer, com a justificativa do padrão.
- **FR-018**: A seção 3 MUST ter bateria e conversas da Fase 3 (`dados_dummy/`), relatório com
  rota, intenção, registro e consulta à memória, executados com a chave no notebook.
- **FR-019**: A seção 3 MUST rodar a partir do Setup sozinha; testes `pytest` MUST rodar sem chave
  e sem rede (modelo falso e memória em processo); `ruff` sem avisos.
- **FR-020**: A memória semântica MUST ter interface pronta nesta fase, separada da episódica:
  registrar e consultar fatos semânticos por assunto (produto ou serviço), cada um com fonte
  (`documentacao`, `usuario` ou `incidente`), data de verificação e validade, e dizer se o fato
  venceu. A pesquisa externa, a pergunta ao usuário e o uso pelo agente MUST NOT ser
  implementados nesta fase (Fase 4, decisão D1).

### Key Entities

- **Conversa de incidente**: identificador, mensagens recentes, resumo dos turnos antigos.
- **Sessão de incidente**: identificador gerado ao abrir (aleatório), criada em, serviço,
  cenário e número de turnos.
- **Episódio**: identificador, incidente, sessão de origem, serviço, resumo do sintoma, causa,
  evidência citada, origem (agente ou engenheiro), data, status (ativo ou arquivado), episódio
  que substitui, motivo do registro e número de acessos. Só nasce por `confirmar_causa`.
- **Fato semântico** (interface; uso na Fase 4): assunto, fato, fonte (documentação, usuário ou
  incidente), verificado em, válido até.
- **Consulta à memória episódica**: serviço, texto do incidente atual, episódios devolvidos com pontuação
  (relevância e decaimento temporal).
- **Resposta do turno**: a da Fase 2 mais o episódio registrado (e a causa anterior, se houve
  troca) e os episódios consultados (se houve).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Nas conversas da Fase 3 com a chave, 100% das confirmações explícitas com serviço
  conhecido geram ou atualizam exatamente um episódio, e 0 perguntas ou sugestões geram episódio.
- **SC-002**: Na conversa "já aconteceu antes?" após uma confirmação, a resposta cita o incidente
  anterior em 100% das execuções da bateria.
- **SC-003**: Uma conversa de 12 turnos roda sem erro de contexto, com resumo gerado e os últimos
  turnos inteiros; o resumo mantém o serviço e a causa confirmada.
- **SC-004**: 0 mensagens de uma conversa aparecem no contexto de outra (teste de isolamento).
- **SC-005**: A bateria da Fase 1 e a da Fase 2 continuam com os mesmos resultados de rota (23/23
  e 12/12) depois da mudança em `confirmar_causa`, ajustado só o caso esperado de confirmação.
- **SC-006**: Seção 3 completa com a chave em menos de 5 minutos; testes sem chave passam.

## Assumptions

- A memória de curto prazo fica em processo (dura enquanto o kernel do notebook está vivo),
  como o `MemorySaver` previsto na constitution.
- O limite de mensagens para resumir e o N de mensagens mantidas são configuráveis, com padrão
  pequeno o bastante para a demonstração mostrar o resumo (ex.: resumir acima de 8 mensagens,
  manter as 4 últimas).
- A memória semântica (a wiki de fatos sobre produtos e serviços) ganha só a interface nesta fase;
  a pesquisa externa e a pergunta ao usuário entram na Fase 4, junto com as ferramentas externas e
  a busca em runbooks (FAISS). A memória procedural é o conjunto de
  regras do prompt e da constitution, sem escrita pelo agente.
- O cenário da loja continua configurado fora do modelo (Fase 2); um episódio guarda o serviço,
  não o id do cenário.
- `gerar_relatorio` continua resposta fixa até a Fase 5 (post-mortem).
- Modelo: o mesmo `gpt-4o-mini` das fases anteriores.
