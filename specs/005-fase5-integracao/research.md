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
