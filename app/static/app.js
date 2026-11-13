// Front do agente de incidentes: JavaScript puro, sem build. Fala com a API em /api.
"use strict";

const $ = (id) => document.getElementById(id);
const estado = { cenarios: [], sessoes: [], atual: null, enviando: false, mensagemAnalise: null };

const SEVERIDADE = { baixa: "baixa", media: "média", alta: "alta", critica: "crítica" };
const RISCO = { baixo: ["baixo", "chip-ok"], medio: ["médio", "chip-medio"], alto: ["alto", "chip-erro"] };
const STATUS_CHECAGEM = { confirmada: "confirmada", contraditoria: "contraditória", nao_verificada: "não verificada" };
const NOME_FERRAMENTA = {
  buscar_logs: "logs da loja", buscar_metricas: "métricas", listar_deploys: "deploys",
  comparar_versoes: "diff entre versões", consultar_estatisticas_banco: "estatísticas do banco",
  consultar_memoria: "incidentes anteriores", gravar_episodio: "registro da causa",
  buscar_documentacao: "documentação indexada", consultar_wiki: "wiki de fatos",
  gravar_fato: "registro de fato", sugerir_acao: "runbooks (ações sugeridas)",
  consultar_sql: "histórico de incidentes (SQL)",
};

// ---------- utilidades de DOM ----------

function el(tag, atributos = {}, ...filhos) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (valor === null || valor === undefined || valor === false) continue;
    if (chave === "classe") no.className = valor;
    else if (chave.startsWith("on")) no.addEventListener(chave.slice(2), valor);
    else no.setAttribute(chave, valor === true ? "" : valor);
  }
  for (const filho of filhos.flat()) {
    if (filho === null || filho === undefined || filho === false) continue;
    no.append(filho instanceof Node ? filho : document.createTextNode(String(filho)));
  }
  return no;
}

function icone(nome) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("aria-hidden", "true");
  const uso = document.createElementNS("http://www.w3.org/2000/svg", "use");
  uso.setAttribute("href", `#i-${nome}`);
  svg.append(uso);
  return svg;
}

function chip(texto, classe = "") {
  return el("span", { classe: `chip ${classe}` }, texto);
}

function anunciar(texto) {
  $("anuncio").textContent = "";
  setTimeout(() => { $("anuncio").textContent = texto; }, 50);
}

function hora(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function dataHora(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
}

function segundos(ms) {
  return `${(ms / 1000).toFixed(1).replace(".", ",")} s`;
}

// Markdown mínimo e seguro: escapa o HTML antes de aplicar títulos, listas, negrito e código.
function markdown(texto) {
  const escapar = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (t) => escapar(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  const saida = [];
  let lista = null;
  let bloco = null;
  const fecharLista = () => { if (lista) { saida.push(`</${lista}>`); lista = null; } };
  for (const linha of texto.split("\n")) {
    if (linha.startsWith("```")) {
      fecharLista();
      if (bloco === null) { bloco = []; } else { saida.push(`<pre><code>${escapar(bloco.join("\n"))}</code></pre>`); bloco = null; }
      continue;
    }
    if (bloco !== null) { bloco.push(linha); continue; }
    const titulo = linha.match(/^(#{1,4})\s+(.*)$/);
    const item = linha.match(/^\s*[-*]\s+(.*)$/);
    const numerado = linha.match(/^\s*\d+[.)]\s+(.*)$/);
    if (titulo) { fecharLista(); saida.push(`<h3>${inline(titulo[2])}</h3>`); }
    else if (item || numerado) {
      const tipo = item ? "ul" : "ol";
      if (lista !== tipo) { fecharLista(); saida.push(`<${tipo}>`); lista = tipo; }
      saida.push(`<li>${inline((item || numerado)[1])}</li>`);
    } else if (linha.startsWith(">")) { fecharLista(); saida.push(`<blockquote class="evidencia">${inline(linha.replace(/^>\s?/, ""))}</blockquote>`); }
    else if (linha.trim() === "") { fecharLista(); }
    else { fecharLista(); saida.push(`<p>${inline(linha)}</p>`); }
  }
  fecharLista();
  if (bloco !== null) saida.push(`<pre><code>${escapar(bloco.join("\n"))}</code></pre>`);
  const div = el("div", { classe: "markdown" });
  div.innerHTML = saida.join("");
  return div;
}

// ---------- rolagem: ancorada embaixo, sem pular se a pessoa rolou para cima ----------

const rolagem = () => $("rolagem");
function pertoDoFim() {
  const r = rolagem();
  return r.scrollHeight - r.scrollTop - r.clientHeight < 80;
}
function irParaOFim(forcar = false) {
  const r = rolagem();
  if (forcar || estado.colado) r.scrollTop = r.scrollHeight;
}

// ---------- API ----------

async function api(caminho, opcoes = {}) {
  const resposta = await fetch(caminho, {
    headers: { "Content-Type": "application/json" },
    ...opcoes,
  });
  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try {
      const corpo = await resposta.json();
      if (typeof corpo.detail === "string") detalhe = corpo.detail;
      else if (Array.isArray(corpo.detail)) detalhe = "A mensagem está vazia ou é longa demais.";
    } catch (e) { /* corpo sem JSON */ }
    const erro = new Error(detalhe);
    erro.status = resposta.status;
    throw erro;
  }
  return resposta.json();
}

// Envia a mensagem e lê os passos por SSE (fetch + leitor; EventSource não aceita POST).
async function enviarComPassos(sessaoId, texto, aoPasso) {
  const resposta = await fetch(`/api/sessoes/${sessaoId}/mensagens/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
  if (!resposta.ok) {
    let detalhe = `Erro ${resposta.status}`;
    try { const corpo = await resposta.json(); if (typeof corpo.detail === "string") detalhe = corpo.detail; } catch (e) {}
    const erro = new Error(detalhe);
    erro.status = resposta.status;
    throw erro;
  }
  const leitor = resposta.body.getReader();
  const decodificador = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await leitor.read();
    if (done) break;
    buffer += decodificador.decode(value, { stream: true });
    let fim;
    while ((fim = buffer.indexOf("\n\n")) >= 0) {
      const bloco = buffer.slice(0, fim);
      buffer = buffer.slice(fim + 2);
      const campos = {};
      for (const linha of bloco.split("\n")) {
        const i = linha.indexOf(": ");
        if (i > 0) campos[linha.slice(0, i)] = linha.slice(i + 2);
      }
      const dados = JSON.parse(campos.data || "{}");
      if (campos.event === "passo") aoPasso(dados);
      else return dados; // "resposta" ou "erro": a mensagem final do agente
    }
  }
  throw new Error("A conexão terminou antes da resposta.");
}

// ---------- barra lateral ----------

function desenharSessoes() {
  const lista = $("sessoes");
  lista.replaceChildren();
  if (!estado.sessoes.length) {
    lista.append(el("li", { classe: "sessao-meta" }, "Nenhuma conversa ainda."));
    return;
  }
  for (const s of estado.sessoes) {
    const atual = estado.atual && estado.atual.id === s.id;
    const turnos = s.turnos === 1 ? "1 resposta" : `${s.turnos} respostas`;
    lista.append(el("li", {},
      el("button", { type: "button", "aria-current": atual ? "true" : "false", onclick: () => abrirSessao(s.id) },
        el("span", { classe: "sessao-titulo" }, s.titulo),
        el("span", { classe: "sessao-meta" }, `${s.servico || s.titulo_cenario} · ${turnos} · ${hora(s.criada_em)}`))));
  }
}

async function atualizarSessoes() {
  estado.sessoes = await api("/api/sessoes");
  desenharSessoes();
}

function fecharLateralNoCelular() {
  $("lateral").classList.remove("aberta");
  $("cortina").hidden = true;
  $("abrir-lateral").setAttribute("aria-expanded", "false");
}

// ---------- cartão de resposta do agente ----------

function blocoCausa(analise, mensagem) {
  const [principal, ...outras] = analise.hipoteses;
  const pct = Math.round(principal.confianca * 100);
  const secao = el("section", {},
    el("h3", {}, "Causa provável"),
    el("p", { classe: "causa" }, principal.causa),
    el("div", { classe: "confianca" },
      el("span", { classe: "barra", role: "img", "aria-label": `Confiança de ${pct}%` }, el("span", { style: `width:${pct}%` })),
      `Confiança ${pct}%`));
  if (principal.evidencia) {
    secao.append(el("blockquote", { classe: "evidencia" }, el("strong", {}, "Evidência: "), principal.evidencia));
  } else {
    secao.append(el("p", { classe: "fonte" }, "Sem evidência direta nos dados consultados."));
  }
  const fontes = mensagem.fontes && mensagem.fontes.length ? mensagem.fontes.join(", ") : "texto do engenheiro";
  secao.append(el("p", { classe: "fonte" }, `Fonte: ${fontes} · consultado em ${dataHora(mensagem.criada_em)}`));
  if (outras.length) {
    const detalhes = el("details", {}, el("summary", {}, `Outras hipóteses (${outras.length})`));
    const ul = el("ul", {});
    for (const h of outras) {
      ul.append(el("li", {}, el("strong", {}, h.causa), ` · confiança ${Math.round(h.confianca * 100)}%. `,
        el("span", { classe: "sutil" }, `Evidência: ${h.evidencia || "sem evidência direta"}`),
        h.dado_que_falta ? el("span", { classe: "sutil" }, ` Falta: ${h.dado_que_falta}`) : null));
    }
    detalhes.append(ul);
    secao.append(detalhes);
  }
  return secao;
}

function blocoAcoes(analise) {
  if (!analise.acoes_sugeridas || !analise.acoes_sugeridas.length) return null;
  const ul = el("ul", { classe: "acoes-lista" });
  for (const a of analise.acoes_sugeridas) {
    const [risco, classe] = RISCO[a.risco] || [a.risco, ""];
    ul.append(el("li", { classe: "acao" },
      el("div", { classe: "acao-titulo" }, chip("Não executada"), chip(`Risco ${risco}`, classe), el("span", {}, a.acao)),
      el("p", {}, a.motivo, a.runbook ? ` Runbook: ${a.runbook.replace(/^runbook:\s*/i, "")}.` : "")));
  }
  return el("section", {}, el("h3", {}, "Ações sugeridas"), ul);
}

// Pergunta ao engenheiro: a resposta vira mensagem dele na mesma sessão e roda um turno novo.
// "fato" (a wiki não tinha o fato): a resposta é enviada como confirmação e gravada (com trava).
function respondida(mensagem, texto) {
  const mensagens = estado.atual ? estado.atual.mensagens : [];
  const depois = mensagens.slice(mensagens.indexOf(mensagem) + 1);
  return depois.find((m) => m.papel === "engenheiro" && m.texto.includes(`${texto}:`)) || null;
}

function blocoPerguntas(mensagem) {
  const lista = mensagem.perguntas || (mensagem.dados_faltantes || []).map((t) => ({ texto: t, tipo: "dado" }));
  return lista.map(({ texto, tipo }) => {
    const ja = respondida(mensagem, texto);
    const titulo = tipo === "fato" ? "Não achei este fato na wiki nem na documentação: " : "Preciso deste dado para continuar: ";
    const cartao = el("div", { classe: `alerta alerta-pergunta${ja ? " respondida" : ""}` },
      el("div", { classe: "alerta-cabeca" }, icone(ja ? "ok" : "pergunta"), el("p", {}, el("strong", {}, titulo), texto)));
    if (ja) {
      cartao.append(el("p", { classe: "fonte" }, `Respondido: ${ja.texto.slice(ja.texto.indexOf(":") + 1).trim()}`));
      return cartao;
    }
    const campo = el("textarea", { rows: "1", "aria-label": `Resposta: ${texto}`, placeholder: tipo === "fato" ? "Escreva o valor confirmado" : "Escreva o dado aqui" });
    const botao = el("button", { type: "submit", classe: "botao pequeno" }, tipo === "fato" ? "Confirmar e registrar" : "Responder");
    const erro = el("p", { classe: "fonte erro-envio", role: "alert", hidden: true });
    const enviar = async (evento) => {
      evento.preventDefault();
      const valor = campo.value.trim();
      if (!valor) { campo.focus(); return; }
      botao.disabled = true; campo.disabled = true; erro.hidden = true;
      botao.replaceChildren(el("span", { classe: "pontos", "aria-hidden": "true" }, el("span"), el("span"), el("span")), " Enviando");
      const texto_msg = tipo === "fato" ? `Confirmado: ${texto}: ${valor}` : `${texto}: ${valor}`;
      const falha = await enviarMensagem(texto_msg);
      if (falha === null) {
        cartao.classList.add("respondida");
        cartao.querySelector(".alerta-cabeca").firstChild.replaceWith(icone("ok"));
        formulario.replaceWith(el("p", { classe: "fonte" }, `Respondido: ${valor}`));
      } else {
        botao.disabled = false; campo.disabled = false;
        botao.replaceChildren(tipo === "fato" ? "Confirmar e registrar" : "Responder");
        erro.textContent = `Não consegui enviar: ${falha}`; erro.hidden = false;
      }
    };
    campo.addEventListener("input", () => autoajustar(campo));
    campo.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); formulario.requestSubmit(); }
    });
    const formulario = el("form", { classe: "resposta-dado", onsubmit: enviar }, campo, botao);
    cartao.append(formulario, erro);
    return cartao;
  });
}

function blocoLacunas(mensagem) {
  const itens = mensagem.lacunas || [];
  const neutra = mensagem.resposta && mensagem.resposta.auditoria && mensagem.resposta.auditoria.veredito === "neutra";
  if (!itens.length && !neutra) return null;
  const investigado = (mensagem.investigado || []).join(", ") || "nenhuma ferramenta";
  return el("div", { classe: "alerta alerta-info" }, icone("analise"),
    el("div", {},
      el("p", {}, el("strong", {}, "O que investiguei: "), investigado, "."),
      itens.length ? el("p", {}, el("strong", {}, "O que faltou: "), itens.join("; ")) : null,
      neutra ? el("p", {}, "O auditor deu veredito neutra: as evidências encontradas não bastam para confirmar a hipótese principal.") : null));
}

const VEREDITO = {
  apoia: ["apoia", "chip-ok", "as evidências sustentam a hipótese principal"],
  refuta: ["refuta", "chip-erro", "as evidências contradizem a hipótese principal"],
  neutra: ["neutra", "chip-medio", "as evidências não bastam para a hipótese principal"],
};

function chipVeredito(veredito) {
  const [rotulo, classe, explicacao] = VEREDITO[veredito] || [veredito, "", ""];
  return el("span", { classe: `chip ${classe}`, title: explicacao }, `Veredito: ${rotulo}`);
}

function seloAuditor(resposta) {
  const a = resposta.auditoria;
  if (!a) return chip("Não auditada");
  const selo = a.aprovada
    ? el("span", { classe: "chip chip-ok" }, icone("ok"), "Auditor aprovou")
    : el("span", { classe: "chip chip-erro" }, icone("alerta"), "Auditor reprovou");
  return a.veredito ? el("span", { classe: "chips" }, selo, chipVeredito(a.veredito)) : selo;
}

const STATUS_TECNICA = { ok: ["ok", "chip-ok"], falha: ["falhou", "chip-erro"], nao_se_aplica: ["não se aplica", ""] };

// As quatro técnicas do auditor, uma linha cada (trajetória, fatos, NLI, extração com Pydantic).
function blocoTecnicas(tecnicas, recolhido) {
  const lista = el("ul", { classe: "tecnicas" }, tecnicas.map((t) => {
    const [rotulo, classe] = STATUS_TECNICA[t.status] || [t.status, ""];
    return el("li", {}, chip(rotulo, classe), el("strong", {}, t.tecnica), el("span", { classe: "sutil" }, t.detalhe));
  }));
  if (!recolhido) return lista;
  const ok = tecnicas.filter((t) => t.status === "ok").length;
  return el("details", { classe: "tecnicas-auditor" }, el("summary", {}, `Auditoria em 4 técnicas: ${ok} de ${tecnicas.length} ok`), lista);
}

function botaoCopiar(texto) {
  const botao = el("button", { type: "button", classe: "botao pequeno", "aria-label": "Copiar resposta" }, icone("copiar"), "Copiar");
  botao.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(texto);
      botao.lastChild.textContent = "Copiado";
      anunciar("Resposta copiada.");
    } catch (e) {
      botao.lastChild.textContent = "Não foi possível copiar";
    }
    setTimeout(() => { botao.lastChild.textContent = "Copiar"; }, 2000);
  });
  return botao;
}

function botaoBaixar(texto) {
  return el("button", {
    type: "button", classe: "botao pequeno",
    onclick: () => {
      const url = URL.createObjectURL(new Blob([texto], { type: "text/markdown" }));
      const link = el("a", { href: url, download: `postmortem-${estado.atual.id.slice(0, 8)}.md` });
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
  }, icone("baixar"), "Baixar .md");
}

function cartaoAgente(mensagem) {
  const cartao = el("article", { classe: "cartao", "aria-label": "Resposta do agente" });
  const r = mensagem.resposta;
  if (!r) {
    cartao.append(el("div", { classe: "alerta alerta-erro", role: "alert" }, icone("alerta"),
      el("div", {}, el("p", {}, el("strong", {}, "A investigação falhou. "), mensagem.erro || "Erro sem detalhes."),
        el("button", { type: "button", classe: "botao pequeno", style: "margin-top:8px", onclick: tentarDeNovo }, "Tentar de novo"))));
    return cartao;
  }
  if (r.aviso) {
    const motivos = (r.auditoria && r.auditoria.motivos) || [];
    cartao.append(el("div", { classe: "alerta alerta-erro", role: "alert" }, icone("alerta"),
      el("div", {}, el("p", {}, el("strong", {}, "O auditor reprovou esta resposta. "), r.aviso),
        motivos.length ? el("ul", {}, motivos.map((m) => el("li", {}, m))) : null)));
  }
  cartao.append(...blocoPerguntas(mensagem));
  const lacunasNo = blocoLacunas(mensagem);
  if (lacunasNo) cartao.append(lacunasNo);
  let textoPostmortem = null;
  if (r.analise) {
    const a = r.analise;
    cartao.append(el("div", { classe: "chips" },
      chip(`Severidade ${SEVERIDADE[a.severidade] || a.severidade}`, a.severidade === "alta" || a.severidade === "critica" ? "chip-erro" : a.severidade === "media" ? "chip-medio" : ""),
      chip(a.categoria)));
    cartao.append(el("p", {}, a.resumo));
    cartao.append(blocoCausa(a, mensagem));
    if (a.proximos_passos && a.proximos_passos.length) {
      cartao.append(el("section", {}, el("h3", {}, "Próximos passos"), el("ol", {}, a.proximos_passos.map((p) => el("li", {}, p)))));
    }
    const acoes = blocoAcoes(a);
    if (acoes) cartao.append(acoes);
  } else if (r.fixa) {
    cartao.append(markdown(r.fixa.texto));
    if (mensagem.causa_a_confirmar && !respondida(mensagem, "Confirmado")) {
      const botao = el("button", { type: "button", classe: "botao primario" }, icone("ok"), "Confirmar esta causa");
      const erro = el("p", { classe: "fonte erro-envio", role: "alert", hidden: true });
      botao.addEventListener("click", async () => {
        botao.disabled = true;
        const falha = await enviarMensagem(`Confirmado: ${mensagem.causa_a_confirmar}`);
        if (falha === null) botao.replaceWith(el("p", { classe: "fonte" }, "Causa confirmada. Peça o post-mortem de novo para gerá-lo."));
        else { botao.disabled = false; erro.textContent = `Não consegui enviar: ${falha}`; erro.hidden = false; }
      });
      cartao.append(el("div", { classe: "chips" }, botao), erro);
    }
    if (r.fixa.categoria === "gerar_relatorio" && r.fixa.texto.includes("\n")) {
      textoPostmortem = r.fixa.texto.replace(/^Post-mortem gerado em [^\n]*\n+/, "");
    }
  } else if (r.erro) {
    cartao.append(el("div", { classe: "alerta alerta-erro", role: "alert" }, icone("alerta"), el("p", {}, el("strong", {}, "Erro na investigação: "), r.erro)));
  }
  const rodape = el("footer", { classe: "cartao-rodape" }, seloAuditor(r),
    el("span", {}, `${hora(mensagem.criada_em)} · ${segundos(mensagem.duracao_ms || 0)}`),
    el("span", { classe: "espaco" }));
  if (textoPostmortem) rodape.append(botaoBaixar(textoPostmortem));
  if (r.trajetoria && r.trajetoria.length) {
    rodape.append(el("button", { type: "button", classe: "botao pequeno", onclick: () => abrirAnalise(mensagem.id) }, icone("analise"), "Ver análise"));
  }
  rodape.append(botaoCopiar(mensagem.texto || ""));
  if (mensagem.tecnicas && mensagem.tecnicas.length) cartao.append(blocoTecnicas(mensagem.tecnicas, true));
  cartao.append(rodape);
  return cartao;
}

function noMensagem(mensagem) {
  if (mensagem.papel === "engenheiro") {
    return el("div", { classe: "msg msg-eng" }, el("span", { classe: "sr-only" }, "Você disse:"), el("div", { classe: "bolha" }, mensagem.texto));
  }
  return el("div", { classe: "msg msg-agente" }, cartaoAgente(mensagem));
}

// ---------- conversa ----------

function desenharConversa() {
  const s = estado.atual;
  $("titulo").textContent = s ? s.titulo : "Nova conversa";
  $("subtitulo").textContent = s ? `${s.servico || "serviço não informado"} · ${s.titulo_cenario}` : "";
  const mensagens = s ? s.mensagens : [];
  $("mensagens").replaceChildren(...mensagens.map(noMensagem));
  $("vazio").hidden = mensagens.length > 0;
  $("postmortem").disabled = !mensagens.some((m) => m.resposta && m.resposta.analise);
  if (!mensagens.length) desenharSugestoes();
  estado.colado = true;
  irParaOFim(true);
}

function desenharSugestoes() {
  const servico = (estado.atual && estado.atual.servico) || "o serviço";
  const textos = [
    `O ${servico} está com erros desde as 14h. Qual a causa provável?`,
    `Teve deploy do ${servico} antes do erro começar?`,
    "Isso já aconteceu antes? Qual foi a causa?",
    `O que eu confirmo antes de mexer no ${servico}?`,
  ];
  $("sugestoes").replaceChildren(...textos.map((t) =>
    el("button", { type: "button", classe: "sugestao", onclick: () => enviarMensagem(t) }, t)));
}

async function abrirSessao(id) {
  estado.atual = await api(`/api/sessoes/${id}`);
  const seletor = $("cenario");
  if (seletor.value !== estado.atual.cenario) seletor.value = estado.atual.cenario;
  desenharSessoes();
  desenharConversa();
  fecharLateralNoCelular();
  if (!$("analise").hidden) desenharAnalise();
  $("entrada").focus();
}

async function novaConversa() {
  const cenario = $("cenario").value;
  const criada = await api("/api/sessoes", { method: "POST", body: JSON.stringify({ cenario }) });
  estado.atual = criada;
  await atualizarSessoes();
  desenharConversa();
  fecharLateralNoCelular();
  $("entrada").focus();
}

function indicadorDigitando() {
  const passos = el("ol", { classe: "passos", "aria-label": "Passos da investigação" });
  const no = el("div", { classe: "msg msg-agente", "aria-busy": "true" },
    el("div", { classe: "cartao digitando" },
      el("div", { classe: "confianca" }, el("span", { classe: "pontos", "aria-hidden": "true" }, el("span"), el("span"), el("span")), "O agente está trabalhando"),
      passos));
  const adicionar = (texto) => {
    for (const li of passos.querySelectorAll("li.atual")) {
      li.classList.remove("atual");
      li.firstChild.replaceChildren(icone("ok"));
    }
    passos.append(el("li", { classe: "atual" }, el("span", { classe: "passo-marca", "aria-hidden": "true" }, "•"), texto));
    irParaOFim();
  };
  adicionar("Recebendo a mensagem");
  return { no, adicionar };
}

function ultimaPerguntaSemResposta() {
  const mensagens = estado.atual ? estado.atual.mensagens : [];
  for (let i = mensagens.length - 1; i >= 0; i--) if (mensagens[i].papel === "engenheiro") return mensagens[i].texto;
  return null;
}

function tentarDeNovo() {
  const texto = ultimaPerguntaSemResposta();
  if (texto) enviarMensagem(texto);
}

function mostrarAvisoChave(texto) {
  const aviso = $("aviso-chave");
  aviso.replaceChildren(icone("alerta"), el("p", {}, texto));
  aviso.hidden = false;
}

async function enviarMensagem(texto) {
  texto = texto.trim();
  if (!texto) return "mensagem vazia";
  if (estado.enviando) return "aguarde a resposta anterior terminar";
  if (!estado.atual) await novaConversa();
  estado.enviando = true;
  atualizarBotaoEnviar();
  $("vazio").hidden = true;
  const sessaoId = estado.atual.id;
  let resultado = "sem resposta";
  const local = { id: `local-${Date.now()}`, papel: "engenheiro", texto, criada_em: new Date().toISOString() };
  estado.atual.mensagens.push(local);
  $("mensagens").append(noMensagem(local));
  const digitando = indicadorDigitando();
  $("mensagens").append(digitando.no);
  estado.colado = true;
  irParaOFim(true);
  anunciar("Mensagem enviada. O agente está investigando.");
  try {
    const resposta = await enviarComPassos(sessaoId, texto, (passo) => digitando.adicionar(passo.texto));
    estado.atual = await api(`/api/sessoes/${sessaoId}`);
    const ultima = estado.atual.mensagens[estado.atual.mensagens.length - 1] || resposta;
    digitando.no.replaceWith(noMensagem(ultima));
    anunciar(ultima.erro ? "A investigação falhou." : "Resposta do agente pronta.");
    resultado = ultima.erro ? ultima.erro : null;
    $("postmortem").disabled = !estado.atual.mensagens.some((m) => m.resposta && m.resposta.analise);
    $("titulo").textContent = estado.atual.titulo;
    await atualizarSessoes();
    if (!$("analise").hidden) desenharAnalise();
  } catch (erro) {
    estado.atual.mensagens.pop();
    resultado = erro.message;
    if (erro.status === 503) mostrarAvisoChave(erro.message);
    digitando.no.replaceWith(el("div", { classe: "msg msg-agente" },
      el("div", { classe: "cartao" }, el("div", { classe: "alerta alerta-erro", role: "alert" }, icone("alerta"),
        el("p", {}, el("strong", {}, "Não consegui enviar a mensagem. "), erro.message)))));
  } finally {
    estado.enviando = false;
    atualizarBotaoEnviar();
    irParaOFim();
  }
  return resultado;
}

async function pedirPostmortem() {
  if (!estado.atual || estado.enviando) return;
  await enviarMensagem("Gera o post-mortem deste incidente.");
}

// ---------- painel de análise ----------

function abrirAnalise(mensagemId = null) {
  estado.mensagemAnalise = mensagemId;
  $("analise").hidden = false;
  $("abrir-analise").setAttribute("aria-expanded", "true");
  desenharAnalise();
  $("fechar-analise").focus();
}

function fecharAnalise() {
  $("analise").hidden = true;
  $("abrir-analise").setAttribute("aria-expanded", "false");
  $("abrir-analise").focus();
}

function blocoTrajetoria(passos) {
  if (!passos || !passos.length) return el("p", { classe: "sutil" }, "Este turno não chamou ferramentas.");
  return el("ol", { classe: "trajetoria" }, passos.map((p) => el("li", {},
    el("span", {}, NOME_FERRAMENTA[p.ferramenta] || p.ferramenta, " ", el("code", {}, p.ferramenta)),
    el("span", { classe: "sutil" }, `${p.duracao_ms} ms`),
    p.erro ? el("span", { classe: "nota" }, `Falhou: ${p.erro}`) : null,
    p.reserva ? el("span", { classe: "nota" }, `Observação: ${p.motivo_reserva || "resposta de reserva"}`) : null)));
}

function blocoAuditoria(auditoria) {
  if (!auditoria) return el("p", { classe: "sutil" }, "Turno sem auditoria (resposta fixa ou sem investigação).");
  const veredito = auditoria.veredito ? VEREDITO[auditoria.veredito] : null;
  const bloco = el("div", { classe: "veredito-bloco" },
    veredito ? el("p", { classe: `veredito-destaque ${veredito[1]}` },
      el("strong", {}, `Veredito: ${veredito[0]}`), el("span", {}, veredito[2])) : null,
    auditoria.veredito_rebaixado ? el("p", { classe: "fonte" },
      `O juiz disse "${auditoria.coerencia ? auditoria.coerencia.veredito : "?"}"; a checagem de fatos rebaixou o veredito.`) : null,
    auditoria.aprovada
      ? el("span", { classe: "chip chip-ok" }, icone("ok"), "Aprovada")
      : el("span", { classe: "chip chip-erro" }, icone("alerta"), "Reprovada"));
  if (auditoria.motivos && auditoria.motivos.length) bloco.append(el("ul", {}, auditoria.motivos.map((m) => el("li", {}, m))));
  if (auditoria.coerencia) {
    bloco.append(el("p", { classe: "fonte" }, `Coerência: ${auditoria.coerencia.veredito}. ${auditoria.coerencia.justificativa}`));
  }
  if (auditoria.checagens && auditoria.checagens.length) {
    const verificaveis = auditoria.checagens.filter((c) => c.afirmacao.chave !== "outro");
    const confirmadas = verificaveis.filter((c) => c.status === "confirmada").length;
    bloco.append(el("p", { classe: "fonte" }, `Checagem de fatos: ${confirmadas} de ${verificaveis.length} afirmações verificáveis confirmadas.`));
    bloco.append(el("table", { classe: "checagens" },
      el("thead", {}, el("tr", {}, el("th", { scope: "col" }, "Afirmação"), el("th", { scope: "col" }, "Situação"))),
      el("tbody", {}, auditoria.checagens.map((c) => el("tr", {},
        el("td", {}, c.afirmacao.texto),
        el("td", {}, STATUS_CHECAGEM[c.status] || c.status))))));
  }
  return bloco;
}

async function desenharAnalise() {
  const conteudo = $("analise-conteudo");
  if (!estado.atual) { conteudo.replaceChildren(el("p", { classe: "sutil" }, "Abra uma conversa.")); return; }
  const respostas = estado.atual.mensagens.filter((m) => m.papel === "agente" && m.resposta);
  if (!respostas.length) {
    conteudo.replaceChildren(el("p", { classe: "sutil" }, "Nenhuma resposta nesta conversa ainda."));
    return;
  }
  let turnos = [];
  try { turnos = await api(`/api/sessoes/${estado.atual.id}/analise`); } catch (e) { turnos = []; }
  const auditados = turnos.filter((t) => t.auditoria_aprovada !== null);
  const aprovados = auditados.filter((t) => t.auditoria_aprovada).length;
  const media = turnos.length ? turnos.reduce((s, t) => s + t.duracao_ms, 0) / turnos.length : 0;
  const escolhida = respostas.find((m) => m.id === estado.mensagemAnalise) || respostas[respostas.length - 1];
  const indice = respostas.indexOf(escolhida);
  const seletor = el("select", { id: "turno-analise", onchange: (e) => { estado.mensagemAnalise = e.target.value; desenharAnalise(); } },
    respostas.map((m, i) => el("option", { value: m.id, selected: m.id === escolhida.id },
      `${i + 1}. ${perguntaDe(m).slice(0, 60)}`)));
  conteudo.replaceChildren(
    el("div", { classe: "metricas" },
      el("div", { classe: "metrica" }, el("strong", {}, String(turnos.length)), el("span", {}, "turnos")),
      el("div", { classe: "metrica" }, el("strong", {}, `${aprovados}/${auditados.length}`), el("span", {}, "aprovados")),
      el("div", { classe: "metrica" }, el("strong", {}, segundos(media)), el("span", {}, "duração média"))),
    el("div", {}, el("label", { classe: "rotulo", for: "turno-analise" }, "Turno"), seletor),
    el("section", { classe: "bloco" }, el("h3", {}, `Trajetória do turno ${indice + 1}`), blocoTrajetoria(escolhida.resposta.trajetoria)),
    el("section", { classe: "bloco" }, el("h3", {}, "As 4 técnicas do auditor"),
      escolhida.tecnicas && escolhida.tecnicas.length ? blocoTecnicas(escolhida.tecnicas, false) : el("p", { classe: "sutil" }, "Turno sem auditoria.")),
    el("section", { classe: "bloco" }, el("h3", {}, "Veredito do auditor"), blocoAuditoria(escolhida.resposta.auditoria)));
}

function perguntaDe(mensagemAgente) {
  const mensagens = estado.atual.mensagens;
  const i = mensagens.indexOf(mensagemAgente);
  for (let j = i - 1; j >= 0; j--) if (mensagens[j].papel === "engenheiro") return mensagens[j].texto;
  return "turno";
}

// ---------- tema ----------

function temaAtual() {
  const salvo = document.documentElement.dataset.tema;
  if (salvo) return salvo;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "escuro" : "claro";
}

function alternarTema() {
  const novo = temaAtual() === "escuro" ? "claro" : "escuro";
  document.documentElement.dataset.tema = novo;
  try { localStorage.setItem("tema", novo); } catch (e) { /* armazenamento bloqueado */ }
  $("tema").setAttribute("aria-label", novo === "escuro" ? "Mudar para o tema claro" : "Mudar para o tema escuro");
}

// ---------- compositor ----------

function atualizarBotaoEnviar() {
  $("enviar").disabled = estado.enviando || !$("entrada").value.trim();
}

function autoajustar(t, max = 200) {
  const borda = t.offsetHeight - t.clientHeight;
  t.style.height = "auto";
  const total = t.scrollHeight + borda;
  t.style.height = `${Math.min(total, max)}px`;
  t.style.overflowY = total > max ? "auto" : "hidden";
}

function ajustarAltura() { autoajustar($("entrada")); }

function ligarEventos() {
  const entrada = $("entrada");
  entrada.addEventListener("input", () => { ajustarAltura(); atualizarBotaoEnviar(); });
  entrada.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("formulario").requestSubmit();
    }
  });
  $("formulario").addEventListener("submit", (e) => {
    e.preventDefault();
    const texto = entrada.value;
    if (!texto.trim() || estado.enviando) return;
    entrada.value = "";
    ajustarAltura();
    enviarMensagem(texto);
  });
  rolagem().addEventListener("scroll", () => { estado.colado = pertoDoFim(); }, { passive: true });
  $("nova").addEventListener("click", () => novaConversa().catch(mostrarFalha));
  $("cenario").addEventListener("change", () => novaConversa().catch(mostrarFalha));
  $("postmortem").addEventListener("click", pedirPostmortem);
  $("abrir-analise").addEventListener("click", () => ($("analise").hidden ? abrirAnalise() : fecharAnalise()));
  $("fechar-analise").addEventListener("click", fecharAnalise);
  $("tema").addEventListener("click", alternarTema);
  $("abrir-lateral").addEventListener("click", () => {
    $("lateral").classList.add("aberta");
    $("cortina").hidden = false;
    $("abrir-lateral").setAttribute("aria-expanded", "true");
    $("nova").focus();
  });
  $("fechar-lateral").addEventListener("click", fecharLateralNoCelular);
  $("cortina").addEventListener("click", fecharLateralNoCelular);
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!$("analise").hidden) fecharAnalise();
    else if ($("lateral").classList.contains("aberta")) fecharLateralNoCelular();
  });
}

function mostrarFalha(erro) {
  mostrarAvisoChave(`Falha ao falar com o servidor: ${erro.message}`);
}

async function iniciar() {
  ligarEventos();
  try {
    const [situacao, cenarios] = await Promise.all([api("/api/estado"), api("/api/cenarios")]);
    if (!situacao.chave_configurada) {
      mostrarAvisoChave("Chave de API não encontrada. Configure OPENAI_API_KEY no .env e reinicie o servidor.");
    }
    estado.cenarios = cenarios;
    $("cenario").replaceChildren(...cenarios.map((c) => el("option", { value: c.id }, c.titulo)));
    if (situacao.cenario_padrao) $("cenario").value = situacao.cenario_padrao;
    await atualizarSessoes();
    if (estado.sessoes.length) await abrirSessao(estado.sessoes[0].id);
    else await novaConversa();
  } catch (erro) {
    mostrarFalha(erro);
  }
}

iniciar();
