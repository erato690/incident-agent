# Research: Fase 3 — memória de curto e longo prazo

## Conceito das memórias (correção do Rafael, 2026-11-02)

| Memória | O que é | Nesta fase |
|---|---|---|
| Curto prazo (trabalho) | A conversa atual do incidente | Implementada (checkpointer por sessão, com resumo) |
| Episódica (longo prazo) | Histórico de incidentes (episódios) com a causa confirmada | Implementada (registrar, atualizar, consultar) |
| Semântica (longo prazo) | A wiki: fatos e regras sobre produtos e serviços, com fonte (`documentacao`, `usuario`, `incidente`), data de verificação e validade; pesquisa fora quando falta ou venceu, pergunta ao usuário se não achar | Só a interface (registrar e consultar com fonte, data e validade) |
| Procedural | Regras do prompt e da constitution | Sem escrita pelo agente |

Episódica e semântica não se misturam: schemas (`Episodio`, `FatoSemantico`), nomes e
namespaces do store diferentes (`("episodica", servico)` e `("semantica", assunto)`).

## Decisões de nível 3 (Rafael, 2026-11-02)

Análise do arquiteto (`ruflo-swarm:architect`, Sonnet, sem editar arquivos) e recomendação do
Jev antes da escolha. Verificado no ambiente local: `InMemoryStore` com índice de embeddings,
`SummarizationMiddleware`, `MemorySaver` e `DeterministicFakeEmbedding` existem; `faiss`,
`langchain_community` e `langgraph.checkpoint.sqlite` não estão instalados.

| # | Decisão | Arquiteto | Jev | Escolha do Rafael |
|---|---|---|---|---|
| D1 | Escopo das notas | nenhuma (0,85) | nenhuma (0,98) | Wiki semântica com pesquisa externa e pergunta ao usuário fica fora da Fase 3; nesta fase só a interface semântica. Estatísticas do banco: Fase 4 com contrato 1.1.0 do `incident-shop` (só nota) |
| D2 | Onde mora a memória de longo prazo | `InMemoryStore` + JSON (0,65) | idem (0,74) | `InMemoryStore` do LangGraph salvo em JSON, atrás de interface pequena (registrar/consultar), namespaces separados para episódica e semântica |
| D3 | Busca na episódica | embeddings + decaimento (0,85) | idem (0,86) | Embeddings da OpenAI (`text-embedding-3-small`), cosseno do store, decaimento temporal, filtro por serviço; embedding falso nos testes |
| D4 | Curto prazo no pipeline | grafo fino (0,80) | grafo fino (0,55) | Grafo fino do LangGraph em volta do pipeline LCEL com `MemorySaver`; `thread_id = uuid4` gerado ao abrir a sessão; metadados da sessão (criada_em, servico, cenario, turnos); resumo quando o histórico cresce |

### Em que fase entra a memória semântica completa

A rubrica da Fase 3 pede a memória semântica só como conceito, na tabela de curto e longo prazo
pela arquitetura CoALA. A Fase 4 ("Ferramentas externas e RAG") pede ferramentas semânticas,
APIs conforme o tipo de uso (Web API) e um agente de recuperação. A pesquisa externa e a busca na
wiki são ferramentas desse tipo. Por isso a wiki completa (pesquisar fora quando falta ou venceu,
perguntar ao usuário e gravar) entra na **Fase 4**, que usa a interface `FatoSemantico` entregue
aqui. A nota `specs/notas/proximas-fases-causas-pendentes.md` foi ajustada.

## Decisões de nível 1 e 2

- Consulta à memória episódica por ferramenta só leitura `consultar_memoria` (nível 2; Jev 0,96).
- Causa diferente confirmada no mesmo incidente: substituída pela decisão D5 (episódio antigo
  arquivado, episódio novo ativo); a lista `historico_causas` foi removida.

## R1. Memória de curto prazo: grafo fino com `MemorySaver` (substituída pela D9)

- `abrir_sessao(cenario=None, servico=None) -> Sessao` gera `thread_id = str(uuid4())` e os
  metadados. `montar_conversa(pipeline, llm_resumo, limite=8, manter=4)` compila um `StateGraph`
  com estado `{mensagens (add_messages), resumo, sessao}` e `MemorySaver`.
- Nós: `turno` (chama o pipeline com `{mensagem, historico, incidente_id}`, onde `historico` é o
  resumo como mensagem de sistema seguido das mensagens guardadas) → `resumir` (condicional,
  quando `len(mensagens) > limite`: resume as antigas com o resumo anterior, remove com
  `RemoveMessage` e mantém as `manter` últimas; erro do modelo mantém tudo).
- O nó `turno` anexa a mensagem mascarada e o texto da resposta, exceto quando a rota é fixa por
  moderação (camada 1), conteúdo proibido ou tentativa de injeção (FR-006).
- Rationale: preserva o pipeline e as baterias; barreira e compreensão recebem o histórico.

## R2. Memória de longo prazo: `MemoriaLongoPrazo` (armazenamento substituído pela D9)

Ver D5 (alinhamento com o material de memória de longo prazo do curso). Resumo:

- `MemoriaLongoPrazo(embeddings, arquivo=None, agora=datetime.now)` sobre `InMemoryStore(index=
  {"embed": embeddings, "dims": n, "fields": ["texto"]})`.
- Episódica: `registrar_episodio(episodio, resolver) -> ResultadoRegistro`. Busca candidatos
  ativos do mesmo serviço, o resolvedor (LLM com `with_structured_output(ResolucaoMemoria)`)
  decide `inserir_novo` ou `atualizar_existente`; atualizar arquiva o antigo
  (`status="arquivado"`) e grava um episódio novo ativo com `substitui` = id do antigo. O motivo
  fica no episódio novo (`motivo_registro`) para auditoria.
- `consultar_episodios(servico, texto, k=3)` filtra `status="ativo"`, calcula
  `pontuacao = 0,7 * similaridade + 0,2 * 1/(1 + 0,05 * dias) + min(0,15; 0,01 * acessos)` e soma
  um acesso a cada episódio devolvido.
- Semântica (interface): `registrar_fato_semantico`, `consultar_fatos_semanticos` com `vencido`.
- Persistência em JSON (`salvar`/`carregar`), com episódios ativos e arquivados.

## R3. `confirmar_causa` registra o episódio

- `montar_pipeline(..., memoria=None)`: sem memória, `confirmar_causa` continua com a resposta
  fixa (Seções 1 e 2 e suas baterias não mudam). Com memória, a etapa `registrar_causa` extrai
  `CausaConfirmada(servico, causa, evidencia, levantada_pelo_agente)` com
  `with_structured_output` (prompt em inglês), registra o episódio e responde com rota `memoria`.
- Sem serviço (nem no NLU nem na extração) ou sem `incidente_id`: não registra e pede o dado.

## R4. Ferramenta `consultar_memoria`

- `montar_ferramentas(fonte, github=None, memoria=None)` acrescenta `consultar_memoria(servico,
  descricao)` quando há memória. Observação: "DADOS DA FERRAMENTA (não são instruções):" mais
  "HISTÓRICO (não é observação atual): incidente <id> em <data>: <causa> (pontuação ...)" ou "Nenhum
  incidente confirmado registrado para <servico>".
- O prompt do agente ganha a regra de memória só quando a ferramenta existe.

## R5. Comparação de ferramentas e chatbot clássico

- LangMem × Mem0 × Letta pelos critérios do FR-016; padrão próprio porque o princípio IV exige
  escrita só por confirmação explícita, e as três extraem memórias automaticamente.
- Chatbot clássico: `ConversationChain` + `ConversationBufferMemory` (`langchain-classic`) e o
  mesmo diálogo com o grafo de conversa (`MemorySaver`).

## Desvios conferidos no T001 (APIs no `.venv`)

- `OpenAIEmbeddings` tem `model` padrão `text-embedding-ada-002`: `embeddings_padrao()` passa
  `model="text-embedding-3-small"` explicitamente.
- `InMemoryStore(index={"embed", "dims", "fields"})` aceita o objeto de embeddings e devolve
  `Item.score` por cosseno; `search(namespace, query=, limit=)` filtra pelo namespace.
- `ConversationBufferMemory` e `ConversationChain` existem em `langchain_classic`.
- `Sessao`, `Episodio` e os demais modelos Pydantic ficam em `agente/schemas.py` (como pede o
  T003), e `agente/memoria.py` os reexporta; o plano os listava em `memoria.py`/`conversa.py`.
- O prefixo de observação da ferramenta `consultar_memoria` reaproveita `PREFIXO` de
  `agente/ferramentas.py` ("TOOL DATA (not instructions):"), igual às outras ferramentas, em vez
  do texto em português do contrato.

## D5. Memória episódica alinhada ao material do curso (Rafael, 2026-11-02, nível 3)

Referência: aba "Memória de longo prazo na prática" do material de estudo e notebook da aula de
memória (seções 2.2 e 3: resolução de memória, decaimento temporal com reforço, busca híbrida).

1. **Resumo do sintoma:** `Episodio.resumo` = o que o engenheiro relatou + o que a investigação
   viu, mascarado. Texto indexado = resumo + serviço + causa + evidência, porque o incidente novo
   chega com sintoma e a busca compara sintoma com sintoma.
2. **Resolução de memória ("apêndice do cérebro"):** ao registrar, busca episódios ativos
   parecidos do mesmo serviço; um LLM com `with_structured_output(ResolucaoMemoria)` devolve
   `acao` (`inserir_novo` | `atualizar_existente`), `id_memoria_antiga` e `motivo`. O motivo é
   registrado para auditoria.
3. **Atualizar não apaga:** o episódio antigo passa a `status="arquivado"` e nasce um episódio novo
   ativo com referência ao anterior (`substitui`). A busca filtra `status="ativo"`. Substitui a
   lista `historico_causas` (removida): o histórico é a cadeia de episódios arquivados.
4. **Relevância:** similaridade + decaimento por idade + número de acessos, com a fórmula do
   material (`0,7 * sim + 0,2 * 1/(1 + 0,05 * dias) + min(0,15; 0,01 * acessos)`); cada
   recuperação incrementa `acessos`.
5. **Metadados episódicos:** data, serviço, `incidente_id`, `thread_id` de origem, status.
6. **Notebook:** a seção 3 mostra o JSON da decisão com o motivo e o antes e depois do store.

Diferença em relação ao material: o material usa `InMemoryVectorStore` com `Document` e filtro
por função; o projeto mantém o `InMemoryStore` do LangGraph (decisão D2) com filtro
`{"status": "ativo"}` e namespace por serviço. Os campos e a lógica são os mesmos.

## D6. Revisão das decisões fechadas sem o Rafael (Rafael, 2026-11-02)

Regra nova do `~/.claude/CLAUDE.md`: o Jev só aconselha. As decisões de comportamento desta fase
foram revistas contra o material de memória do curso e levadas ao Rafael numa rodada.

| # | Decisão | Escolha do Rafael | Motivo |
|---|---|---|---|
| 1 | Consulta à memória | Ferramenta `consultar_memoria` | Igual ao `consultar_historico` do material (ferramenta-sensor) |
| 2 | Gravação do episódio | Ferramenta `gravar_episodio` chamada pelo modelo, orientada pelo prompt de procedimento, como `gravar_experiencia` do material, **com trava no código**: só grava se o turno atual for confirmação explícita (intenção `confirmar_causa` da compreensão, com serviço e incidente); fora disso devolve observação "só gravo causa confirmada" e nada é gravado | Segue o material (memória se escreve por ferramenta, o modelo decide) sem abrir mão do princípio IV (só fato confirmado) |
| 3 | Resolvedor de memória | O modelo decide entre os episódios ativos do serviço, como no material; o prompt diz que incidente diferente é `inserir_novo`. **Trava no código**: atualizar episódio de outro `incidente_id` vira inserção, com a correção registrada no motivo e no log | Mantém o padrão do material e protege a recorrência entre incidentes |
| 4 | Filtro de relevância no curto prazo | Como na seção 2.1 do material: modelo classifica cada mensagem (`baixa`, `alta`, `critica`); `baixa` sai do contexto, além da janela deslizante e do resumo; mostrado no notebook | Item da rubrica ("filtro de relevância e janela deslizante") e padrão do material |
| 5 | Turnos bloqueados fora da conversa | Aprovado | Camada 1 dos guardrails |
| 6 | Sem memória, `confirmar_causa` fixa | Aprovado | Seções 1 e 2 inalteradas |
| 7 | Sem serviço ou incidente | Aprovado: resposta fixa pedindo o dado | Não grava fato incompleto |
| 8 | Erro na extração | Aprovado: rota `erro` legível, nada gravado | Confiabilidade |
| 9 | Mesma causa com evidência nova | Aprovado: segue D5 (resolvedor decide; nada muda no lugar além de `acessos`) | Coerência com "atualizar não apaga" |
| 10 | Resultado semântico achatado | Aprovado | Fonte, data e validade visíveis na consulta |
| 11 | Extração de resumo e origem | Aprovado: `with_structured_output` a partir do histórico da sessão | Resumo do sintoma alimenta a busca (D5) |

Consequência para o desenho: a gravação deixa de ser uma etapa do pipeline. Com memória, a
intenção `confirmar_causa` vai para o agente (rota de investigação), que tem `gravar_episodio`
e `consultar_memoria`; a trava lê do estado do turno (intenção, serviço, `incidente_id`), passado
à fábrica das ferramentas por turno, nunca pelo modelo.

## Execução com a chave (T016, 2026-11-02)

- Notebook inteiro: 513 s; seção 3: 315 s (SC-006 pede menos de 300 s). 0 erros, 0 chaves nos
  outputs.
- Bateria da Fase 3: 10/10. Conversas da Fase 3: todos os turnos com a rota esperada; sessão B e
  turno 4 da decomposição chamam `consultar_memoria` e citam o incidente anterior como histórico
  (depois do reforço da regra no prompt); troca de causa arquiva o episódio anterior
  (`atualizar_existente`); agente tentou gravar hipótese e a trava recusou.
- Seções 1 e 2: bateria 23/23 e 12/12; conversas da Fase 2 iguais. Uma conversa da Fase 1
  (`escopo_externo`, turno 2) deu "JSON inválido" nessa execução; rodada de novo 3 vezes fora do
  notebook, passou nas 3 (instabilidade do modelo, sem relação com a memória). Os outputs das
  seções 1 e 2 no notebook são os da execução anterior.
- Achado: no turno 4 da decomposição (`banco_lento_com_deploy`), o episódio de outro incidente
  (pool esgotado no deploy v3.2.0) levou o agente a dar 0,70 ao deploy distrator v3.2.1. Na Fase
  2, sem memória, o agente não culpava esse deploy. Levado ao Rafael.

## D7. Pontos em aberto da implementação (Rafael, 2026-11-02)

| # | Ponto | Escolha | Motivo |
|---|---|---|---|
| 1 | Erro do modelo no resolvedor | Não gravar; resposta de erro legível | Não grava episódio que o resolvedor não avaliou |
| 2 | Mensagens `baixa` no resumo | Excluídas também do resumo | O filtro de relevância vale para toda a memória de curto prazo |
| 3 | Rastro do agente de registro | Agente de registro grava a trajetória | Auditoria da memória; coluna "memória consultada" completa |
| 4 | Turno sem `thread_id` | Recusa gravar e pede a sessão | Todo episódio tem sessão de origem (metadado do D5) |
| 5 | Persistência | Salva o JSON automaticamente a cada gravação quando há arquivo; o notebook usa arquivo temporário | Memória de longo prazo dura entre execuções |
| 6 | Aviso do checkpointer | `Sessao` e `RespostaTurno` registrados como tipos permitidos | Remove o aviso e prepara para versões que bloqueiam tipos não registrados |
| 7 | Demonstrações sem chave | Mantidas ao lado das versões com chave | Seção roda sem chave e mostra o código real das travas e da memória |

Pendente: ponto 8 (episódio de outro incidente reforçando o deploy distrator).

## D8. Episódio de outro incidente reforçando o deploy distrator (Rafael, 2026-11-02)

Decisão: combinar similaridade mínima no código e regra no prompt.

1. `consultar_memoria` só devolve episódios com similaridade acima de um limiar.
2. Regra no prompt: um episódio só reforça uma hipótese quando o sintoma e a causa batem com as
   observações atuais; senão é só contexto e não aumenta a confiança. Mais um exemplo resolvido
   com a conversa de decomposição.

Calibração com `text-embedding-3-small` contra o episódio de pool esgotado do `pedidos-api`
(`dados_dummy/memoria_longo_prazo.json`), similaridade do store:

| Consulta | Grupo | Similaridade |
|---|---|---|
| pedidos-api devolve 500, HikariPool sem conexões disponíveis | mesmo incidente | 0,805 |
| pool de conexões esgotado no pedidos-api | mesmo incidente | 0,706 |
| O pedidos-api voltou a devolver 500 | mesmo, vago | 0,598 |
| pedidos-api devolve 500 | mesmo, vago | 0,521 |
| pedidos-api lento com timeout desde 15h47 após deploy v3.2.1 | banco lento | 0,614 |
| Os pedidos estão com timeout desde as 15h47 | banco lento | 0,546 |
| banco de dados lento, reindexação | banco lento | 0,451 |
| timeout em consultas ao banco, canceling statement due to statement timeout | banco lento | 0,390 |
| pedidos-api com OOMKilled e memória crescendo | outro | 0,543 |
| variável de ambiente faltando no pedidos-api | outro | 0,435 |
| certificado TLS expirado no pedidos-api | outro | 0,375 |

Consultas vagas ("devolve 500") não separam os grupos. Com o sinal de erro dos logs na consulta,
os grupos se separam: o mesmo incidente fica em 0,70 ou mais, os diferentes em 0,61 ou menos.
Primeiro limiar: 0,65, com o prompt mandando chamar `consultar_memoria` com o sinal principal
dos logs.

**Recalibração (execução com a chave):** o agente passou a consultar com a linha de log crua, em
inglês, e a similaridade com o episódio em português caiu. Medido com a mensagem de ERROR mais
frequente de cada cenário contra o episódio de pool esgotado do `pedidos-api`:

| Cenário da linha de log | Similaridade |
|---|---|
| pool_esgotado (mesmo incidente) | 0,609 |
| vazamento_memoria (OOMKilled) | 0,490 |
| gateway_fora (SocketTimeoutException) | 0,446 |
| banco_lento_com_deploy (statement timeout) | 0,323 |
| deploy_com_bug (NullPointerException) | 0,322 |
| certificado_expirado (SSLError) | 0,289 |
| env_var_faltando (Traceback de config) | 0,276 |

Limiar final: **0,55** (margem de 0,06 para cada lado). O de 0,65 barrava o próprio incidente
repetido na sessão B.

### Execução com a chave depois do D8 (limiar 0,55)

- Notebook inteiro 421 s; seção 3 220 s (SC-006 cumprido; as conversas da 3.8 rodam em
  paralelo, respeitando `depende_de`). 0 erros, 0 chaves.
- Seção 1: bateria 23/23, conversas 11/11. Seção 2: bateria 12/12, conversas 9/9; o cenário
  `banco_lento_com_deploy` dá a mesma análise da Fase 2 (causa no banco, deploy não culpado).
- Seção 3: bateria 10/10, conversas 24/24 turnos. O agente busca os logs antes da memória e
  consulta com a linha de log. Sessão B e "já aconteceu antes?" da bateria acham o episódio e o
  resumo diz que já aconteceu antes; nesta execução a evidência não trouxe o id do incidente no
  formato do FR-010 (na execução anterior trouxe). Decomposição: a memória não devolve o episódio
  de pool (similaridade abaixo do limiar) e o deploy distrator fica em 0,05 a 0,10.

## D9. Só peças do LangChain/LangGraph ensinadas no curso (Rafael, 2026-11-02, nível 3)

**Contexto:** o `StateGraph` (R1) e o `InMemoryStore` do LangGraph (R2) nunca apareceram no
material do curso. O professor avalia pelos padrões do curso.

**Decisão do Rafael:** usar só as peças ensinadas; virou princípio da constituição (2.0.0,
princípios IV e V). Substitui R1 e a parte de armazenamento de R2.

- **Curto prazo:** o pipeline LCEL é embrulhado em `RunnableWithMessageHistory`, com um
  dicionário de sessões (`obter_historico_sessao(session_id)` devolve um
  `InMemoryChatMessageHistory`). O histórico que chega ao pipeline passa pelo filtro de
  relevância (`baixa` sai) e por `trim_messages` (janela deslizante por tokens, contagem
  aproximada para rodar sem rede). Acima de `limite` mensagens, o resumo híbrido: uma chain
  resumidora condensa as antigas, o histórico é limpo e recebe uma mensagem de sistema com o
  resumo mais as `manter` mensagens recentes. Metadados da sessão (`session_id` uuid4,
  criada_em, serviço, cenário, turnos) continuam; turnos bloqueados continuam fora do histórico.
  O nome `thread_id` virou `session_id`, o nome que o `RunnableWithMessageHistory` usa.
- **Longo prazo:** `InMemoryVectorStore` com `Document`: `page_content` = resumo + serviço +
  causa + evidência; `metadata` = tipo (episodica/semantica), id_memoria, incidente_id, serviço,
  data, session_id de origem, status, acessos, substitui. Busca com
  `similarity_search_with_score` e filtro por metadado (tipo, serviço, status ativo), mais a
  fórmula de relevância. Resolvedor, travas, limiar 0,55, arquivamento e JSON continuam.
- **Agente:** o `create_agent` não usa checkpointer (o histórico chega pelo pipeline). O
  `MemorySaver` aparece só na demonstração do notebook, com `get_state`.
- **Constituição:** o princípio IV proibia corte por limite de tokens; com a D9 o
  `trim_messages` entra como janela deslizante depois do filtro de relevância e junto do resumo.

## D9b. Depreciação das classes de histórico (Rafael, 2026-11-02, nível 3)

**Contexto:** no langchain-core 1.7.4 instalado, as duas peças da memória de curto prazo da D9
emitem `LangChainDeprecationWarning`:

- `RunnableWithMessageHistory is deprecated. Use LangGraph's built-in persistence instead.`
- `The class `InMemoryChatMessageHistory` was deprecated in LangChain 1.6.4 and will be removed
  in 2.0.0 See the short-term memory documentation for recommended alternatives:
  https://docs.langchain.com/oss/python/langchain/short-term-memory`

**Opções:** A) manter as duas classes como padrão e registrar a depreciação; B) conversa via
`create_agent(checkpointer=MemorySaver)`, exigindo middleware (não visto no curso) ou reescrita
do pipeline, 1 a 2 dias de retrabalho; C) A com histórico próprio no lugar do
`InMemoryChatMessageHistory`. Jev: A (confiança 0,49; A 0,66, B 0,28, C 0,06).

**Decisão do Rafael:** A. As duas classes são as peças ensinadas no curso para a memória de
conversa, e nenhuma peça ensinada cobre o pipeline inteiro (máscara, moderação, compreensão,
roteador e agente); o `MemorySaver` ensinado é o checkpointer do `create_agent`, que é só uma
etapa do pipeline. O aviso é silenciado só nas duas chamadas que criam essas classes
(`agente/conversa.py`, `_sem_aviso_de_depreciacao`, filtro pela mensagem), com teste. A seção 3.3
do notebook mostra as três peças: `ConversationBufferMemory` clássica,
`RunnableWithMessageHistory` com `get_session_history` (padrão do projeto) e `create_agent` com
`checkpointer=MemorySaver` e `get_state`.

### Execução com a chave depois da D9 (2026-11-02)

- **Limiar 0,55 com o `InMemoryVectorStore`:** o score é o mesmo cosseno do store anterior.
  Mensagem de ERROR mais frequente de cada cenário contra o episódio de pool do `pedidos-api`:
  pool_esgotado 0,714 (a linha `HikariPool-1 ... request timed out`; outra linha do mesmo
  incidente dava 0,609), vazamento_memoria 0,490, gateway_fora 0,446, deploy_com_bug 0,341,
  banco_lento_com_deploy 0,323, certificado_expirado 0,315, env_var_faltando 0,267. O limiar
  0,55 continua separando os casos; sem recalibração.
- Notebook inteiro 535 s; seção 3 289 s (SC-006 cumprido, mais perto do limite que os 220 s
  anteriores; o tempo extra está nas células com modelo real: 3.8 conversas 122 s, bateria 64 s,
  3.7 decomposição 50 s). 0 erros, 0 chaves.
- Seção 1: bateria 23/23, conversas 11/11. Seção 2: bateria 12/12, conversas 9/9;
  `banco_lento_com_deploy` com a mesma análise da execução anterior (causa no banco; o deploy
  aparece só como "não alterou a lógica de acesso ao banco").
- Seção 3: bateria 10/10, conversas 24/24 turnos. A 3.3 mostra o mesmo diálogo no buffer
  clássico, no `RunnableWithMessageHistory` e num `create_agent` com `MemorySaver` + `get_state`
  (o agente lembra o serviço no terceiro turno). Sessão B e "já aconteceu antes?" consultam a
  memória depois dos logs, com a linha de log. Decomposição: o episódio de pool fica abaixo do
  limiar e a resposta diz que não há incidente parecido confirmado.

## D10. Fechamento da Fase 3 (Rafael, 2026-11-03)

1. **Id na evidência (SC-002), no código:** `consultar_memoria` guarda no contexto do turno os
   episódios que devolveu acima do limiar; depois do Investigador, o pipeline
   (`citar_episodios`) acrescenta à evidência da hipótese com mais palavras em comum com a causa
   do episódio a citação "consultar_memoria: incidente <id> em <data>: <causa> (histórico, não é
   observação atual)". Sem palavra em comum, nada é acrescentado (D8: o episódio só reforça a
   hipótese que bate); id já citado pelo modelo não se repete. Determinístico, com testes sem
   chave.
2. **Nomes:** Investigador (`montar_investigador`, antes `montar_investigacao_agente`) e
   Registrador (`montar_registrador`, antes `montar_agente_registro`); os nomes antigos ficam como
   apelidos. Notebook, diagramas e página do projeto usam os dois nomes.
3. **Tempo:** conferir a seção 3 na execução final (limite de 300 s do SC-006).
4. **Push autorizado** depois de tudo verde: varredura de segredos, squash num commit
   "feat: Fase 3 - memória de curto e longo prazo", push sem force.

### Execução final com a chave (2026-11-03)

- Notebook inteiro 535 s; seção 3 290 s (SC-006 cumprido, margem de 10 s; nenhuma célula
  precisou ir para paralelo). 0 erros, 0 chaves.
- Seção 1: bateria 23/23, conversas 11/11. Seção 2: bateria 12/12, conversas 9/9;
  `banco_lento_com_deploy` igual às execuções anteriores (causa no banco; o deploy aparece só como
  "não alterou a lógica de acesso ao banco").
- Seção 3: bateria 10/10, conversas 24/24 turnos. **SC-002 cumprido:** na sessão B e no
  "já aconteceu antes?" da bateria, a evidência da hipótese principal traz "consultar_memoria:
  incidente inc-2026-09-03-pedidos em 2026-09-03: ... (histórico, não é observação atual)".
