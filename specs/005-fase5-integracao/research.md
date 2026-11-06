# Research: Fase 5

## Mapeamento contra o material da aula (2026-11-05)

| Componente | Peça da aula | Situação |
|---|---|---|
| Auditor | Extração de afirmações com `with_structured_output`; checagem de fatos por função determinística contra uma fonte da verdade com tolerância; verificação de coerência por um LLM juiz que devolve veredito apoia/refuta/neutro, `e_coerente` e falácias. O auditor fica fora do agente e avalia a resposta já pronta | Ensinado (só transcrição e aba; não há notebook) |
| Agente único | `create_agent` + `MemorySaver` / `system_prompt` | Ensinado |
| `create_openai_tools_agent` + `AgentExecutor` | — | Sem equivalente na aula. A rubrica cobra; a constitution V manda mostrar numa célula curta com `langchain-classic` |
| `RunnableWithMessageHistory` | Ensinado em chain da LangChain Expression Language (LCEL), nunca em agente | O projeto já o usa em volta do pipeline (Fase 3) |
| Streamlit | Só citado ("não muda a nota") | Sem equivalente; a constitution X pede |
| LangSmith | Só anunciado (métricas de avaliação e avaliação de trajetória); não há aula 8 no material | Sem equivalente; F5-D2 |
| Trajetória | Callbacks e leitura de `state["messages"]` | Ensinado (base dos avaliadores) |
| Entrega | Relatório organizado, avaliação e trajetória com LangSmith, vídeo (YouTube com link privado é preferível), citar as IAs usadas; prazo citado: dia 13 | Da aula 6 e da aula 7 |

## Decisões

| # | Decisão | Opções | Escolha | Situação |
|---|---|---|---|---|
| F5-D1 | Auditor reprova | A: marca e avisa, sem nova tentativa; B: uma nova tentativa com o motivo; C: bloqueia | A (Jev A 0,91). Fiel à aula: o auditor fica fora do agente | Decidida pelo Rafael em 2026-11-05: A. A resposta reprovada sai com aviso, sem nova tentativa |
| F5-D2 | API do LangSmith | A: SDK oficial (`Client.create_dataset` + `evaluate` com avaliadores próprios); B: A + LLM juiz (openevals); C: só tracing | A (Jev A 0,85) | Decidida pelo Rafael em 2026-11-05: A. SDK oficial com avaliadores próprios |
| — | Agente final | constitution V | `create_agent` como padrão; o clássico numa célula curta | Já decidido |
| — | Streamlit e Docker | constitution X | Duas telas, Dockerfile e compose | Já decidido; corte permitido: só a tela de uso |
| — | Post-mortem | constitution VIII | `.md` por template, só a pedido | Já decidido |

## Calibração do auditor com a chave (2026-11-05, 8 cenários, `gpt-4o-mini`)

1. **Primeira rodada: 4 de 8 aprovados, todas as causas certas.** Os falsos positivos vieram de
   três lugares:
   - O juiz acusou `deploy_posterior_ao_sintoma` em 3 casos com o deploy ANTES do sintoma, por
     exemplo 13:40 contra 14:00.
   - As observações eram cortadas em 2000 caracteres, e contagens como "x338" ficaram de fora.
   - Os horários escritos pelo engenheiro ("9h10") não entravam na fonte da verdade.
2. **Correções, todas determinísticas, com testes:**
   - Uma trava por código descarta `deploy_posterior_ao_sintoma` quando todo deploy citado na
     hipótese principal saiu antes do primeiro erro dos logs. Os horários vêm das próprias
     ferramentas; sem dado, vale o juízo do modelo.
   - A observação guardada vai a 6000 caracteres.
   - A mensagem do engenheiro entra na fonte da verdade.
   - Horários são normalizados ("9h10", "09h10" e "9:10" viram "09:10"), e contagens com "x"
     também ("x338" conta 338).
   - Ações sugeridas e próximos passos saem da extração, porque não são fatos a checar.
   - O prompt do juiz manda comparar os horários numericamente.
3. **Segunda rodada: 7 de 8 aprovados.** O 8º, `gateway_fora`, foi reprovado por "x338", "x372" e
   "09h10". Os três estão corrigidos pela normalização acima; a confirmação fica para a execução
   final.
4. **Conversa integrada com a chave (`banco_lento_com_deploy`, 4 turnos).** Três defeitos
   apareceram e foram corrigidos, com testes:
   - O juiz julgava a hipótese secundária (deploy) e respondia "refuta". Agora recebe a hipótese
     principal separada e o prompt manda julgar só ela.
   - A falácia `deploy_posterior_ao_sintoma` era apontada mesmo quando a hipótese principal não
     culpa deploy. Agora essa falácia é descartada por código nesses casos.
   - As observações no prompt eram cortadas em bloco e as estatísticas do banco ficavam de fora.
     Agora o orçamento é dividido por ferramenta.
   - O post-mortem usava a última análise mesmo quando ela só consultava o SQL. Agora usa a
     última investigação com ferramentas do incidente.
   - A descrição de `consultar_sql` passou a orientar `GROUP BY categoria` para "causa mais
     comum".
5. **Terceira rodada: auditor aprovou 8 de 8 cenários, com a causa certa em 8 de 8.**

## LangSmith: rastreamento ligado e cota esgotada (2026-11-05)

- O `.env` do Rafael liga o rastreamento (`LANGSMITH_TRACING`), e por isso as execuções do
  notebook com a chave enviaram traces para a conta dele.
- Na execução final, o LangSmith passou a recusar o envio com HTTP 429, "Monthly unique traces
  usage limit exceeded": a cota mensal de traces da conta esgotou.
- **Consequência:** o envio do dataset e do experimento (F5-D2) fica bloqueado até a cota
  renovar ou até o Rafael ampliar o plano. Isso é decisão dele, porque envolve custo.
- **Enquanto isso:** a avaliação roda localmente, com os mesmos avaliadores e a mesma API do
  `evaluate`, e as métricas ficam no notebook.
- A execução final usou `LANGSMITH_TRACING=false` só no comando, para as saídas não ficarem
  cheias de avisos 429. O `.env` não foi alterado.
- **Decisão do Rafael (2026-11-05):** enviar o dataset e o experimento quando a cota renovar,
  sem ampliar o plano. O comando `scripts/avaliar_langsmith.py --enviar` fica pronto, e o
  relatório registra o limite (seção 5.5). O push dos repositórios espera a validação das
  Fases 4 e 5 pelo Rafael.
- O GitHub sem token também esgotou o limite de 60 requisições por hora. `comparar_versoes` caiu
  na gravação de reserva, que já é rotulada na trajetória.

## Execução final do notebook inteiro com a chave (2026-11-05)

- Notebook inteiro em 831 s, com `LANGSMITH_TRACING=false` no comando: 0 erros e 0 chaves nas
  saídas.
- Baterias e conversas:
  - Bateria da Fase 1: 23/23, com as conversas 5/5 e 6/6.
  - Bateria da Fase 2: 12/12, com as conversas 5/5 e 4/4.
  - Bateria da Fase 3: 10/10, com todas as conversas completas.
  - Bateria da Fase 4: 11/11 e causa certa 8/8. Seção 4 em 73 s.
- Seção 5 em 116 s:
  - auditor aprova a resposta certa e reprova a errada roteirizada;
  - a conversa integrada de 4 turnos passa por sintoma, SQL, confirmação e post-mortem;
  - o pedido de REINDEX é recusado;
  - a avaliação local dos 8 cenários tem média 1,0 em causa certa, trajetória e auditor.
- Testes: 510 sem chave.
- Dois defeitos encontrados nas execuções anteriores e corrigidos, com testes:
  1. O NLU classificou "Gera o post-mortem" como `pedido_de_acao` e uma pergunta de histórico
     como `fora_do_escopo`. Entraram regras e exemplos no prompt.
  2. A cadeia da Fase 1 devolvia `None` quando o modelo respondia em prosa imitando o histórico.
     Com temperatura fixa, as novas tentativas repetiam a mesma prosa. Agora, depois das novas
     tentativas, um passo final repete o pedido exigindo só o JSON.

## Interface: front próprio no lugar do Streamlit (2026-11-05)

- **Contexto:** o Rafael testou o app Streamlit (`app/app.py`) e achou a tela ruim para uso real:
  sem cara de app de chat, com a caixa de mensagem dentro da aba e a resposta em texto corrido.
  Um redesenho dentro do Streamlit (tema, `st.chat_message`, CSS mínimo) melhorou pouco, porque o
  Streamlit limita o layout (barra lateral de conversas, compositor fixo, passos ao vivo).
- **Opções:**
  - A: manter o Streamlit com tema e CSS (feito no commit `f55b949`, depois substituído);
  - B: interface web própria, FastAPI servindo HTML, CSS e JavaScript sem build;
  - C: front com framework (React ou parecido), com etapa de build.
- **Decisão do Rafael:** B. O Streamlit sai.
- **Motivo:** a B dá a experiência de app de chat (barra lateral com sessões, bolhas, compositor
  fixo, estado vazio com sugestões, tema claro e escuro) sem etapa de build nem dependência de
  front. A C traria build e um ecossistema novo para um entregável que não conta nota.
- **Como ficou:**
  - `app/main.py` expõe a API sobre o mesmo `AgenteIntegrado`: criar, listar e abrir sessão,
    enviar mensagem (JSON ou SSE com os passos), post-mortem a pedido e análise do turno;
  - os passos do turno ("mascarando", "moderação", "entendendo", "investigando", "consultando",
    "auditando") vêm de um `BaseCallbackHandler` do LangChain, ligado a todas as execuções do
    turno por `register_configure_hook`, sem mudar o agente;
  - o front está em `app/static/` (HTML, CSS com tokens claro e escuro, JavaScript puro); a paleta,
    a tipografia (Inter e JetBrains Mono) e as regras de acessibilidade vêm da skill
    `ui-ux-pro-max:ui-ux-pro-max` com `ui-ux-pro-max:design-system`;
  - testes da API com agente falso e sem chave em `tests/test_api.py`;
  - a constitution passou a 2.1.0 (princípio X).

## Respostas "burras": dado faltante indevido e ações de só verificar (2026-11-05)

- **Contexto:** o Rafael testou na tela "O pagamentos-api está com erros desde as 14h. Qual a
  causa provável?" (cenário `rate_limit`). Três defeitos apareceram:
  - o NLU marcou "causa provável dos erros" como dado faltante, e a tela pediu ao engenheiro o que
    o próprio agente tinha de descobrir;
  - os próximos passos e as ações mandavam "verificar os logs" e "consultar o limite
    documentado", embora o agente já tivesse lido os logs (150 respostas 429, X-RateLimit-Limit
    100/min, Retry-After 30) e a wiki (100 requisições por minuto);
  - o mesmo padrão de devolver a tarefa podia aparecer nos outros cenários.
- **Correção (autorizada pelo pedido, sem mudar schema):**
  - prompt do NLU: `dado_faltante` só para o que só o engenheiro sabe (serviço ou horário
    ausentes, limite de provedor sem documentação), nunca a causa, a pergunta ou o que as
    ferramentas alcançam; resumo da conversa é `investigar_erro`, não `gerar_relatorio`;
  - trava em código (`agente/qualidade.py`, ligada ao pipeline depois do NLU): descarta o dado
    faltante que é a causa, repete a pergunta ou cita logs, métricas, deploys, diff, banco, wiki,
    documentação ou histórico;
  - `sugerir_acao`: o prompt exige remediação concreta que cita o número da evidência; ação que só
    manda olhar dados é recusada e o modelo tenta de novo uma vez, com as recusadas no pedido;
  - o diagnóstico enviado a `sugerir_acao` leva a evidência da hipótese principal;
  - prompt do Investigador: próximos passos usam os números lidos e nunca repetem uma consulta já
    feita; trava em código tira da análise o passo que repete consulta feita no turno;
  - na tela, só o dado faltante do NLU e o da hipótese principal sem evidência viram pergunta.
- **Testes sem chave:** `tests/test_qualidade.py`, `tests/test_pipeline_qualidade.py` e casos novos
  em `tests/test_acoes.py`.

## Modelo maior só no NLU (2026-11-05)

- **Contexto:** o gpt-4o-mini interpretava mal o "dado faltante" (no `rate_limit`, marcou a causa
  como dado faltante). A trava em código cobre o caso, mas o Rafael pediu também um modelo maior
  só na compreensão da intenção.
- **Decisão do Rafael:** trocar o modelo SÓ do NLU; Investigador, Registrador, auditor,
  `sugerir_acao` e filtros de memória continuam em gpt-4o-mini. Só OpenAI, com a chave existente.
- **Opções de modelo (lista da chave):** gpt-4.1 e gpt-4o, os maiores sem raciocínio; a família
  gpt-5 e o o3 são modelos de raciocínio, mais lentos, e ficaram de fora. Escolhido o **gpt-4.1**
  (segue melhor as instruções e custa menos que o gpt-4o).
- **Como ficou:** `agente/config.py` tem `MODELO_NLU` (padrão `gpt-4.1`) e `llm_do_nlu`, usado por
  `montar_nlu`; com outro provedor, ou com `MODELO_NLU=gpt-4o-mini`, o NLU usa o mesmo modelo dos
  demais.
- **Medição** (notebook inteiro com a chave, as duas execuções em paralelo; tempos com ruído):

| | NLU gpt-4o-mini | NLU gpt-4.1 |
|---|---|---|
| Bateria da Fase 1 | 23/23 | 23/23 |
| Bateria da Fase 2 | 12/12 | 12/12 |
| Bateria da Fase 3 | 10/10 | 10/10 |
| Conversa longa (12 turnos) | 12/12 | 11/12 ("Resume o que sabemos" virou `gerar_relatorio`; corrigido no prompt) |
| Bateria da Fase 4 | 11/11, causa certa 8/8 | 11/11, causa certa 8/8 |
| Avaliação dos 8 cenários (causa certa) | 0,875 | 1,0 |
| Seção 4 / seção 5 | 72 s / 287 s | 71 s / 107 s |
| Notebook inteiro | 988 s | 728 s |
| Custo de um turno `rate_limit` | US$ 0,0052 (21 s) | US$ 0,0062 (17,7 s) |

  Execução final com `gpt-4.1` no NLU (sozinha, depois de todas as correções): notebook inteiro em
  845 s sem erros; seções 1 a 5 em 103, 163, 297, 103 e 128 s; baterias 23/23, 12/12, 10/10 e
  11/11, conversa longa 12/12 (com a regra do resumo da conversa), causa certa 8/8. Nenhum
  acerto piorou e nenhuma seção passou de 300 s, então o `gpt-4.1` ficou como padrão do NLU.

  Custo pelo preço de lista da OpenAI (gpt-4o-mini US$ 0,15 e 0,60 por milhão de tokens de
  entrada e saída; gpt-4.1 US$ 2 e 8). O NLU gasta cerca de 1,4 mil tokens por turno.

## Qualidade das ações sugeridas (2026-11-05)

- **Contexto:** no `pool_esgotado` (pedidos-api, v3.2.0), causa e evidência saíram certas
  (`pool_max` de 20 para 10, 284 timeouts), mas as ações saíram fracas: "aumentar o pool para 15"
  (o diff mostra que antes era 20), "reduzir o tempo máximo das consultas" (os logs mostram espera
  por conexão, não consulta lenta) e "escalar horizontalmente, se o pico for legítimo" (nada na
  evidência fala de pico).
- **Decisão do Rafael:** ajustar o prompt de `sugerir_acao` e travar em código, sem mudar schema.
- **Como ficou:**
  - prompt: primeiro a ação que desfaz a causa (rollback do deploy culpado, valor anterior do
    diff), depois a de menor risco, depois contenção; cada ação ataca o mecanismo observado e cita o
    dado que a sustenta; nada condicional;
  - trava (`ordenar_e_filtrar_acoes` em `agente/qualidade.py`, na ferramenta e na análise): tira ação
    condicional ("se necessário", "se o pico for legítimo"), ação sem nenhum dado da evidência da
    hipótese principal e risco alto sem evidência direta; com causa interna e sem ação de desfazer,
    o código inclui "Restaurar <chave> para <valor anterior>" ou "Fazer rollback da <versão>";
    ações quase iguais ficam na mais específica; se nenhuma cita dado, fica a de menor risco;
  - a ferramenta tenta de novo uma vez quando recusa alguma ação, com as recusadas no pedido.
- **Resultado com a chave (8 cenários, 2026-11-05):** causa certa 8/8, auditor aprovando 8/8,
  nenhum dado faltante indevido, nenhuma ação de consulta ou condicional. Rollback ou valor anterior
  em primeiro nos cenários com deploy culpado; contenção da dependência nos externos. No
  `pool_esgotado`: "Restaurar o pool_max para 20" em primeiro.

## Veredito explícito do auditor (NLI) e avaliadores por técnica (2026-11-05)

- **Contexto:** o Rafael pediu o veredito explícito, no estilo da auditoria de inferência lógica
  (NLI) vista em aula, e uma métrica por técnica de verificação. É mudança de schema e de saída,
  autorizada por ele.
- **Schema:** `VereditoCoerencia.veredito` passa a `apoia`, `refuta` ou `neutra` (o antigo
  `neutro` é aceito e convertido). `Auditoria` ganha `veredito` (final, depois das travas) e
  `veredito_rebaixado`; `RegistroTurno` ganha `veredito`.
- **Regra:** aprovada só com veredito final `apoia`, sem afirmação contraditória e sem falácia
  confirmada. Trava: afirmação contraditória rebaixa para `refuta`; `apoia` com mais da metade das
  afirmações verificáveis sem prova vira `neutra`.
- **Avaliação:** `fato_deterministico` (fração das afirmações verificáveis confirmadas) e
  `veredito_nli` (1 quando o veredito é o esperado; padrão `apoia`, a resposta errada roteirizada
  espera `refuta`) entram ao lado de `causa_certa`, `trajetoria_ferramentas` e `auditor_aprovou`,
  com a assinatura `(inputs, outputs, reference_outputs)` do `evaluate()` do LangSmith.
- **Exibição:** texto copiado ("auditada: aprovada (veredito: apoia)"), cartão do chat, painel de
  análise e seção 5.1 do notebook.

## Post-mortem só com causa confirmada (2026-11-06)

- **Contexto:** o arquivo gerado sem confirmação saía como rascunho "causa não confirmada", e o
  arquivo tinha defeitos: linha do tempo com horários das consultas (00:00, 03:00, 00:25) em vez
  dos eventos do incidente, entradas "sem horário" das ferramentas, aviso técnico em inglês do
  GitHub como evento, rodapé "não auditada" com a análise auditada e ações repetidas entre a
  correção e as preventivas.
- **Decisão do Rafael (muda o atuador, a spec e o princípio VIII da constitution, agora 2.2.0):**
  sem causa confirmada na sessão, não há arquivo. A resposta diz que falta confirmar a causa,
  mostra a hipótese principal e pergunta se o engenheiro a confirma; a confirmação grava o
  episódio pelo Registrador (com a trava), e só então o post-mortem sai, com as lições aprendidas.
  Trava em código (`agente/integrado.py`; `gerar_postmortem` recusa dados sem episódio).
- **Correções do arquivo:** linha do tempo só com eventos do incidente, em ordem e com data
  (deploys, primeiro e último erro dos logs, reindexação em andamento); seção "Investigação
  realizada" com as consultas e nota em português quando usou dados gravados; rodapé com o
  veredito e a hora da auditoria; ações preventivas sem repetir a correção.
- **Tela:** o pedido sem confirmação mostra o botão "Confirmar esta causa".

## Tela: resposta à pergunta de dado e pedido de logs ao engenheiro (2026-11-06)

- **Bug 1 (front):** responder no cartão "Preciso deste dado" não dava retorno claro. Agora a
  resposta vira mensagem do engenheiro na mesma sessão e roda um turno novo com os passos ao
  vivo; o cartão fica verde só quando a resposta chega ao agente; enquanto envia, o botão fica
  desabilitado com indicador; erro aparece legível e o cartão continua amarelo. Pergunta de fato
  da wiki (D7) usa "Confirmar e registrar" e envia como confirmação. O front passou a ser servido
  sem cache, para o navegador não rodar um `app.js` antigo.
- **Bug 2 (agente):** o agente pedia ao engenheiro "logs ou métricas que confirmem o uso do
  disco". A trava passou a valer para o dado que falta da hipótese principal: pedido de logs,
  métricas, deploys, uso de recurso ou "confirmar" algo ao alcance das ferramentas vira lacuna,
  mostrada como "O que investiguei / O que faltou", nunca como pergunta. O prompt manda dizer
  que nenhuma ferramenta cobre a métrica e investigar com o que há.
- **Robustez:** `sugerir_acao` degenerou uma vez (16 mil tokens de saída, 178 s, sem ações).
  A saída das ações tem limite de 1.200 tokens e uma nova tentativa; se as duas falharem, fica a
  ação determinística de desfazer a causa.

## Quatro técnicas do auditor separadas e auditoria de trajetória (2026-11-06)

- **Contexto:** o Rafael apontou que a validação mostrava um único resultado agregado. O auditor
  já combinava a extração com Pydantic (`ListaAfirmacoes`), a checagem de fatos (`checar_fatos`)
  e o NLI (`VereditoCoerencia` com falácias), mas a trajetória só entrava como fonte das
  observações e na avaliação (`trajetoria_ferramentas`), não como critério do auditor.
- **Decisão do Rafael (muda o schema de `Auditoria`):**
  - quarta checagem em código, `auditar_trajetoria` → `ChecagemTrajetoria` (itens com critério,
    status e detalhe): ferramentas citadas chamadas; argumentos coerentes (serviço, versões e tags
    contra os deploys listados); ferramentas mínimas (logs sempre; deploys e diff quando a causa
    culpa uma mudança; sem chamada repetida à toa); nenhuma ferramenta de escrita. Reprova só
    com critério grave;
  - checagem de fatos com tolerância de 5% em contagens, durações e percentuais (números a partir
    de 10), além do casamento exato; versões e horários continuam exatos;
  - as quatro técnicas separadas no notebook (uma célula por técnica na seção 5.1, sobre a
    resposta certa e a errada roteirizada), na resposta, no cartão e na análise da tela, no
    post-mortem e no relatório;
  - avaliadores: `trajetoria_ferramentas`, `fato_deterministico`, `veredito_nli` e o agregado
    `auditor_aprovou`, todos com `(inputs, outputs, reference_outputs)`.
- **Resultado com a chave (8 cenários):** as quatro técnicas passaram nos 8, com causa certa 8/8
  e veredito `apoia` 8/8.
- **Post-mortem na seção 5.2:** fluxo em três passos visíveis: pedido sem confirmação (recusa e
  pergunta), confirmação (grava o episódio) e post-mortem gerado, renderizado como Markdown.

## Laboratório com Docker Compose (2026-11-06)

- **Decisão do Rafael:** pasta `laboratorios/` no workspace, um laboratório por subpasta; o
  primeiro, `laboratorios/incident-lab/`, sobe a loja (`incident-shop`, contrato 1.1.0) e o
  agente já conectados (`LOJA_URL=http://shop:8000`, healthcheck em `/saude`, portas só em
  127.0.0.1, `CENARIO` como cenário padrão do chat). A chave vem do shell ou do `.env` do
  incident-agent, nunca da imagem. O deploy no Railway ficou fora.
- **Validação:** `docker compose up --build`, `/saude` com o contrato 1.1.0, uma pergunta do
  `rate_limit` no chat com as requisições `GET /logs`, `/metricas` e `/deploys` nos logs da loja,
  e `docker compose down`. Fora do compose, o padrão continua gravado (`dados_dummy/`).

