# Feature Specification: Fase 5 — agente integrado, auditor, interface e avaliação

**Feature Branch**: `005-fase5-integracao` (sem branch git dedicada; trabalho local em `main`)

**Created**: 2026-11-05

**Status**: Clarified. As decisões vêm da constitution, das ordens do Rafael de 2026-11-05 e de
duas decisões novas (F5-D1 e F5-D2) tomadas pela recomendação; ver `research.md`.

**Input**: ordem do conductor (2026-11-05): "Ao fechar a Fase 4, siga direto para a Fase 5 no
mesmo ritmo [...] Corte de escopo se faltar tempo, nesta ordem: Streamlit só com a tela de uso;
verificador sem falácias; D6 sem gravar o fato. Não corte LangSmith, relatório nem notebook."
Somam-se a rubrica da Fase 5, a nota `specs/notas/fase5-organizacao-entrega.md` e a constitution
(princípios V, VIII e X).

## Contexto

Seção 5 do notebook. As Fases 1 a 4 entregaram as peças: barreira, Investigador com as
ferramentas (loja, GitHub, estatísticas do banco, SQL, documentação, wiki e ação), memórias de
curto e longo prazo. A Fase 5 junta e verifica o que já existe. Acrescenta:

1. **Agente único integrado**: o Investigador com todas as ferramentas, inclusive `consultar_sql`,
   atrás da barreira, numa sessão `RunnableWithMessageHistory` por `session_id`. A versão clássica
   `create_openai_tools_agent` + `AgentExecutor` aparece numa célula curta, com a justificativa
   (constitution V).
2. **Auditor de verificação cognitiva**, que fica fora do agente e examina a resposta antes de ela
   ser entregue:
   - extrai as afirmações da resposta;
   - checa os fatos de forma determinística, contra as observações das ferramentas;
   - verifica a coerência lógica e as falácias do domínio, como culpar um deploy posterior ao
     sintoma ou tratar o sintoma como causa.
   - Se o auditor reprova, a resposta sai com aviso e motivos, sem nova tentativa (F5-D1).
3. **Post-mortem `.md`**, o único atuador do agente (constitution VIII): é gerado a pedido
   (`gerar_relatorio`) a partir de dados Pydantic, por template.
4. **Interface Streamlit** com duas telas: *uso*, uma conversa por incidente, e *análise*, com o
   registro de cada turno (pergunta, resposta, trajetória, auditoria). Tem Dockerfile e
   `docker compose`.
5. **Avaliação no LangSmith** (F5-D2):
   - um dataset com os 8 cenários e o gabarito;
   - avaliadores de resposta (causa certa), de trajetória (ferramentas esperadas) e de auditoria;
   - um experimento registrado.
6. **Organização da entrega**: seções renomeadas pela capacidade; seção 0 com visão geral,
   agente final e índice da rubrica; relatório PDF.

| Item da rubrica (Fase 5) | Onde |
|---|---|
| Verificação factual e lógica | US2, FR-004 a FR-008 |
| Agente único com RAG, SQL e API | US1, FR-001 |
| `create_openai_tools_agent` e `AgentExecutor` | US1, FR-002 |
| `RunnableWithMessageHistory` | US1, FR-003 |
| Interface Streamlit | US4, FR-011 a FR-013 |
| Avaliação no LangSmith | US5, FR-014 a FR-016 |

## Clarifications

### Session 2026-11-05

- Q: Agente final com `create_openai_tools_agent` + `AgentExecutor` ou com `create_agent`? → A
  (constitution V): `create_agent` é o padrão, porque é o que as aulas usam. A versão clássica
  entra numa célula curta (importada do `langchain-classic`), com a justificativa.
- Q: O que acontece quando o auditor reprova? → A (F5-D1, recomendação; Jev A 0,91; enviada ao
  Rafael): a resposta é entregue com aviso "reprovada pelo auditor" e os motivos, e o veredito
  fica no registro do turno. Não há nova tentativa.
- Q: Que API usar na avaliação no LangSmith, que não foi ensinada? → A (F5-D2, recomendação; Jev
  A 0,85; enviada ao Rafael):
  - SDK oficial: tracing por variável de ambiente, `Client.create_dataset` e `create_examples`;
  - `evaluate()` com avaliadores próprios em Python.
  - A gravação no LangSmith, conta do Rafael, só acontece depois da confirmação dele (ação
    externa).
- Q: Ordem de corte? → A (Rafael): Streamlit só com a tela de uso; verificador sem falácias; D6
  sem gravar o fato. LangSmith, relatório e notebook não são cortados.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agente final numa conversa (Priority: P1)

O engenheiro abre uma sessão para um incidente e conversa em vários turnos. O mesmo agente
investiga com as ferramentas da loja, o GitHub, o SQL, a documentação e a memória, responde com
a análise auditada e as ações sugeridas, e no fim gera o post-mortem.

**Independent Test**: uma conversa de 4 ou mais turnos num cenário, com trajetória, veredito do
auditor e post-mortem impressos; testes sem chave com fakes.

**Acceptance Scenarios**:

1. **Given** uma sessão nova, **When** o engenheiro descreve o sintoma, **Then** o agente
   investiga e responde com análise, veredito do auditor e ações sugeridas.
2. **Given** a mesma sessão, **When** o engenheiro pergunta "quantos incidentes parecidos tivemos
   este ano?", **Then** o agente usa `consultar_sql` e responde com o número.
3. **Given** a causa confirmada, **When** o engenheiro pede o post-mortem, **Then** o arquivo `.md`
   é gerado com o template completo.

### User Story 2 - Auditor aprova a resposta certa e reprova a errada (Priority: P1)

**Independent Test**: uma resposta real certa é aprovada. Uma resposta errada, roteirizada (culpa
o deploy posterior ao sintoma e cita um número que nenhuma ferramenta devolveu), é reprovada com
os motivos.

**Acceptance Scenarios**:

1. **Given** uma análise cujas versões, horários e números aparecem nas observações, **When** o
   auditor verifica, **Then** cada afirmação sai "confirmada" e o veredito é aprovado.
2. **Given** uma análise que cita "deploy v9.9.9" ou "37% de erros" sem lastro, **When** o auditor
   verifica, **Then** a afirmação sai "não verificada" ou "contraditória" e o veredito é
   reprovado.
3. **Given** uma análise que culpa um deploy feito depois do sintoma, **When** o auditor verifica,
   **Then** aponta a falácia `deploy_posterior_ao_sintoma`.

### User Story 3 - Post-mortem (Priority: P3)

**Acceptance Scenarios**: sem causa confirmada, o arquivo sai marcado "causa não confirmada". Com
a causa confirmada, traz a causa, a linha do tempo das ferramentas e as ações sugeridas,
marcadas como não executadas.

### User Story 4 - Interface Streamlit (Priority: P2)

A tela de uso tem a escolha do cenário, a conversa e as respostas formatadas. A tela de análise
tem a tabela dos turnos, com rota, tempo, ferramentas e veredito, e o detalhe de cada um.

**Independent Test**: `streamlit run app/app.py` local e `docker compose up`; teste do módulo de
registro sem chave; prints para o relatório.

### User Story 5 - Avaliação no LangSmith (Priority: P2)

**Independent Test**: os avaliadores rodam localmente sem chave, com fakes. Com a chave e a
confirmação do Rafael, o experimento fica registrado no LangSmith e o notebook mostra as métricas
e a análise.

### User Story 6 - Organização da entrega (Priority: P2)

As seções passam a se chamar "1 Chain, barreira e saída estruturada", "2 Agente com
ferramentas", "3 Memória", "4 Consulta SQL e RAG" e "5 Agente integrado". A seção 0 traz o
diagrama de contexto, 2 ou 3 células com o agente final e o índice da rubrica. O relatório PDF é
`rafael_dias_ai-agents_langchain-agents.pdf`.

### Edge Cases

- O auditor falha (erro do modelo): a resposta sai com o veredito "não auditada" e o motivo.
  Nunca é aprovada em silêncio.
- Pedido de post-mortem sem investigação na sessão: a resposta diz que falta investigação.
- LangSmith sem chave: as células de avaliação são puladas com aviso. Os avaliadores locais rodam
  mesmo assim.
- Streamlit sem chave: modo de demonstração rotulado, ou aviso para configurar.

## Requirements *(mandatory)*

- **FR-001**: O agente único reúne as ferramentas das Fases 2 a 4 mais `consultar_sql`, atrás da
  barreira, e entrega uma única resposta por turno.
- **FR-002**: Uma célula curta com `create_openai_tools_agent` + `AgentExecutor` (do
  `langchain-classic`), com as mesmas ferramentas e a justificativa do padrão moderno.
- **FR-003**: A sessão usa `RunnableWithMessageHistory` por `session_id`, igual ao incidente (Fase
  3), e envolve o pipeline.
- **FR-004**: O auditor extrai as afirmações da análise com `with_structured_output`: texto,
  chave canônica e valor.
- **FR-005**: A checagem de fatos é determinística, contra as observações das ferramentas na
  trajetória (versões, horários, números, tabelas). Status por afirmação: confirmada,
  contraditória ou não verificada.
- **FR-006**: A verificação de coerência lógica (inferência em linguagem natural) devolve
  veredito apoia/refuta/neutro, `e_coerente` e falácias do domínio:
  `deploy_posterior_ao_sintoma`, `sintoma_como_causa`, `contradicao_premissa_conclusao`,
  `erro_de_calculo`, `violacao_de_escopo`, `nenhuma`.
- **FR-007**: Veredito final aprovado/reprovado em `RespostaTurno.auditoria`. Se reprovado, a
  resposta ganha um aviso com os motivos.
- **FR-008**: A trajetória passa a guardar o texto mascarado de cada observação, truncado, para a
  checagem de fatos.
- **FR-009**: Post-mortem `.md` por template: resumo; impacto e severidade; linha do tempo; causa
  raiz e evidência; ações sugeridas (não executadas); próximos passos. Sem causa confirmada, sai
  marcado "causa não confirmada".
- **FR-010**: `RegistroTurno` (Pydantic) com pergunta, rota, resposta, trajetória, auditoria e
  duração, para a tela de análise.
- **FR-011**: Streamlit, tela de uso.
- **FR-012**: Streamlit, tela de análise.
- **FR-013**: Dockerfile e `docker-compose.yml`, com `PORT` vinda do ambiente.
- **FR-014**: Dataset dos 8 cenários (mensagem, cenário, palavras da causa, ferramentas
  esperadas).
- **FR-015**: Avaliadores: causa certa, trajetória (ferramentas esperadas chamadas, sem chamada
  proibida) e auditor aprovou.
- **FR-016**: Experimento no LangSmith, depois da confirmação, com o resultado e a análise no
  notebook.
- **FR-017**: Seções renomeadas, seção 0 e índice da rubrica.
- **FR-018**: Relatório PDF: problema, arquitetura, decisões por fase, avaliação, limitações,
  evidências, processo de desenvolvimento com o spec-kit, e as IAs usadas, citadas
  explicitamente.

## Success Criteria *(mandatory)*

- **SC-001**: Conversa integrada de 4 ou mais turnos com a chave, sem erro.
- **SC-002**: O auditor aprova as respostas certas da bateria e reprova 100% das respostas
  erradas roteirizadas.
- **SC-003**: Experimento no LangSmith com causa certa em 8 de 8 e trajetória ok em 7 ou mais
  de 8.
- **SC-004**: Streamlit roda local e em `docker compose`; prints das duas telas.
- **SC-005**: Seção 5 com a chave em até 300 s; testes sem chave passando; ruff limpo.
- **SC-006**: O PDF é gerado a partir do repositório, com o nome do padrão.

## Assumptions

- O professor citou na aula a entrega no dia 13/11, mas o alvo continua 09/11, a confirmar no
  Moodle.
- O vídeo é feito pelo Rafael. Segundo o professor, o YouTube com link privado é preferível ao
  Drive.
- O Streamlit não foi ensinado e o professor disse que a interface não muda a nota. Ela entra
  porque a constitution e a rubrica a pedem.
