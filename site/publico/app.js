/* Americana Fiscaliza — site estático. Lê os JSON de dados/ e monta as telas. */
"use strict";

const CONTATO_CORRECAO = { texto: "uma issue no GitHub do projeto", url: "https://github.com/WellingtonFonseca/americanafiscaliza/issues/new" };

// Trocado pelo robô a cada publicação, para o navegador não usar dados velhos guardados.
const VERSAO = "dev";
const app = document.getElementById("app");
const cache = {};
let R = null; // resumo.json

const $ = (s) => s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const data = (iso) => (iso ? iso.split("-").reverse().join("/") : "");
const num = (n) => Number(n).toLocaleString("pt-BR");
const norm = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\s+/g, " ").trim();
function SISCAM_DOC(id) {
  const s = String(id);
  if (s[0] === "s") return `https://americana.siscam.com.br/Sessoes/Documento/${s.slice(1)}`;
  if (s[0] === "p") { // veio da exportação da pesquisa: link para a pesquisa oficial desse número/ano
    const [cod, n, ano] = s.slice(1).split("-");
    return `https://americana.siscam.com.br/Documentos/Pesquisa?Pesquisa=Avancada&id=74&pagina=1&Modulo=DocumentosLista&DocumentosRelacionadosDetalhes=false&NoTexto=false&Documento=${cod}&Numeracao=Documento&NumeroInicial=${n}&AnoInicial=${ano}&Situacao=0&TipoAutor=Todos&AutoriaId=0&Iniciativa=Nenhum`;
  }
  return `https://americana.siscam.com.br/Documentos/Documento/${s}`;
}
const ext = (url, txt) => `<a href="${$(url)}" rel="noopener" target="_blank">${txt}</a>`;

async function carregar(nome) {
  if (window.DADOS_EMBUTIDOS && window.DADOS_EMBUTIDOS[nome]) return window.DADOS_EMBUTIDOS[nome];
  if (!cache[nome]) cache[nome] = fetch("dados/" + nome + "?v=" + VERSAO).then((r) => { if (!r.ok) throw new Error(nome); return r.json(); });
  return cache[nome];
}

const EXPLICA = {
  bairro: "Pedidos para a Prefeitura ou o DAE: tapar buraco, podar árvore, trocar lâmpada. No sistema da Câmara se chamam Indicações.",
  cobranca: "Perguntas e cobranças feitas à Prefeitura e a outros órgãos (Requerimentos, Pedidos de Informação e Moções de apelo ou repúdio).",
  homenagem: "Parabéns, pesar, título de cidadão, medalha, nome de rua e datas comemorativas.",
  lei: "Projetos de lei e outras propostas de regra para a cidade, inclusive emendas a projetos.",
  outros: "Documentos que não são proposta nova: pareceres de comissão, atos da Mesa Diretora, pedidos de retirada, documentos do gabinete e leis já aprovadas.",
};

function vereador(slug) { return R.vereadores.find((v) => v.slug === slug); }

function avisoSessoes() {
  const p = R.periodo_sessoes;
  if (!p) return `<div class="aviso">Ainda não há sessões coletadas.</div>`;
  return `<div class="aviso"><b>Histórico de sessões ainda parcial.</b> Por enquanto o site tem ${R.sessoes.length} sessões, de ${data(p[0])} a ${data(p[1])}. As outras estão sendo baixadas aos poucos, para não sobrecarregar o sistema da Câmara. Presença e votos abaixo valem só para essas sessões.</div>`;
}

// ------------------------------------------------------------------ telas
function telaInicio() {
  const lista = R.vereadores.map((v) => `
    <li><a href="#/v/${v.slug}">
      <img src="${$(fotoLocal(v))}" alt="" loading="lazy" width="56" height="56" onerror="this.style.visibility='hidden'">
      <span><span class="nome">${$(v.apelido)}</span>
      <span class="info">${$(v.partido)}${v.propostas_baixadas ? ` · ${num(v.grupos.bairro)} pedidos de bairro · presente em ${v.presente} de ${v.chamadas} chamadas${v.propostas_parcial ? " · propostas parciais" : ""}` : " · propostas ainda não baixadas"}</span></span>
    </a></li>`).join("");
  return `
    <h1>O que cada vereador de Americana faz</h1>
    <p>Presença nas sessões, propostas e votos dos ${R.vereadores.length} vereadores, só com dados oficiais da Câmara Municipal. Cada número tem link para a fonte. Os vereadores estão em ordem alfabética.</p>
    <p><a class="botao" href="#/busca">Ver o que pediram para o meu bairro</a></p>
    ${avisoSessoes()}
    ${R.vereadores.some((v) => v.propostas_parcial || !v.propostas_baixadas) ? `<div class="aviso">Para ${R.vereadores.filter((v) => v.propostas_parcial || !v.propostas_baixadas).length} vereadores as propostas ainda estão parciais (o sistema da Câmara não abriu a página completa deles). Isso está marcado na ficha de cada um.</div>` : ""}
    <h2>Vereadores</h2>
    <ul class="lista-ver">${lista}</ul>
    <p class="suave">Propostas contadas desde ${data(R.inicio_mandato)}, início do mandato atual, para todos da mesma forma.</p>`;
}

function fotoLocal(v) { return `fotos/${v.slug}.jpg`; }

function cartao(slugV, g, itens, fonte, parcial) {
  const n = itens.length;
  let det = EXPLICA[g];
  if (parcial && g === "outros") return `<div class="numero"><b>—</b><span>${$(R.grupos[g])}</span><small>Ainda não baixados para este vereador.</small><small>${ext(fonte, "Ver na Câmara")}</small></div>`;
  if (parcial && g === "lei") det += " Sem as emendas (dados parciais).";
  if (parcial && g === "cobranca") det += " Sem os pedidos de informação (dados parciais).";
  if (g === "outros" && n) {
    const t = {}; itens.forEach((d) => { t[d[2]] = (t[d[2]] || 0) + 1; });
    det = "Os tipos mais comuns: " + Object.entries(t).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, c]) => `${k} (${num(c)})`).join(", ") + ".";
  }
  return `<div class="numero">
    <a href="#/v/${slugV}/${g}" style="text-decoration:none;color:inherit"><b>${num(n)}</b><span>${$(R.grupos[g])}</span></a>
    <small>${$(det)}</small>
    <small>${ext(fonte, "Conferir na Câmara")}</small></div>`;
}

const ABAS = [["gastos", "Gastos"], ["propostas", "Propostas"], ["presenca", "Presença"], ["votos", "Votos"]];

async function telaVereador(slug, aba, mes) {
  if (!ABAS.some(([k]) => k === aba)) aba = "gastos";
  const v = vereador(slug);
  if (!v) return `<p>Vereador não encontrado. <a href="#/">Voltar</a></p>`;
  const f = await carregar(`vereador-${slug}.json`);
  const contato = [f.telefone_gabinete && `Telefone do gabinete: ${$(f.telefone_gabinete)}`, f.email_gabinete && `E-mail: <a href="mailto:${$(f.email_gabinete)}">${$(f.email_gabinete)}</a>`].filter(Boolean).join("<br>");

  let propostas;
  if (!f.propostas_baixadas) {
    propostas = `<div class="aviso">As propostas deste vereador ainda não foram baixadas. Veja direto ${ext(f.fonte_propostas, "no sistema da Câmara")}.</div>`;
  } else {
    const total = Object.values(f.grupos).reduce((a, l) => a + l.length, 0);
    propostas = `<p>${num(total)} documentos com o nome de ${$(f.apelido)} desde ${data(R.inicio_mandato)}. Toque num grupo para ler um por um.</p>
      ${f.propostas_parcial ? `<div class="aviso"><b>Dados parciais.</b> A página completa de propostas deste vereador é muito grande e o sistema da Câmara não conseguiu abri-la. Por isso usamos a exportação oficial da pesquisa da Câmara, que traz indicações, moções, requerimentos e projetos, mas <b>não traz emendas, pedidos de informação nem os outros documentos</b>. Esses números podem estar abaixo do real e não devem ser comparados com os de outros vereadores nesses grupos. Vamos tentar de novo nas próximas atualizações.</div>` : ""}
      <div class="numeros">${Object.keys(R.grupos).map((g) => cartao(slug, g, f.grupos[g], f.fonte_propostas, f.propostas_parcial)).join("")}</div>
      <p class="suave">Quando um documento tem mais de um autor, ele conta para cada um deles. A separação em grupos segue <a href="#/sobre#grupos">uma regra única</a>, igual para todos.</p>`;
  }

  // presença
  const reg = f.presenca.filter((p) => p.situacao !== "sem registro");
  const pres = f.presenca.filter((p) => p.situacao === "presente").length;
  const aus = f.presenca.filter((p) => p.situacao === "ausente").length;
  const linhasP = f.presenca.slice().reverse().map((p) => `<li>
      <span class="tag ${p.situacao === "presente" ? "sim" : p.situacao === "ausente" ? "nao" : ""}">${p.situacao === "presente" ? "Presente" : p.situacao === "ausente" ? "Ausente" : "Sem registro"}</span>
      ${ext(p.url, `${$(p.titulo)}`)} <span class="meta">· ${$(p.chamada)}</span></li>`).join("");

  // votos
  const cont = {};
  f.votos.forEach((x) => { cont[x.voto] = (cont[x.voto] || 0) + 1; });
  const resumoVotos = Object.entries(cont).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<span class="tag neutro">${$(k)}: ${num(n)}</span>`).join(" ");
  const votos = f.votos.slice().reverse();

  return `
    <a class="voltar" href="#/">← Todos os vereadores</a>
    <div class="cabeca-ver"><img class="foto" src="${$(fotoLocal(f))}" alt="" width="84" height="84" onerror="this.style.visibility='hidden'">
      <div><h1>${$(f.apelido)}</h1><p class="suave">${$(f.nome)} · ${$(f.partido)}</p></div></div>
    <div class="caixa suave">${contato}<br>${ext(f.perfil_url, "Perfil oficial no site da Câmara")}</div>

    <div class="abas" role="tablist">
      ${ABAS.map(([k, t]) => `<button role="tab" data-aba="${k}" aria-selected="${k === aba}">${t}</button>`).join("")}
    </div>

    <section class="painel" data-painel="gastos"${aba === "gastos" ? "" : " hidden"}>
    <h2>Anual</h2>
    <h3>Emendas impositivas</h3>
    ${secaoEmendas(f)}

    <h2>Mensal</h2>
    ${seletorMes(f, mes)}
    </section>

    <section class="painel" data-painel="propostas"${aba === "propostas" ? "" : " hidden"}>
    <h2>Propostas</h2>
    ${propostas}

    </section>

    <section class="painel" data-painel="presenca"${aba === "presenca" ? "" : " hidden"}>
    <h2>Presença nas sessões</h2>
    ${avisoSessoes()}
    <div class="numeros">
      <div class="numero"><b>${pres} de ${reg.length}</b><span>chamadas em que aparece como presente</span><small>${ext("https://americana.siscam.com.br/sessoes", "Conferir na Câmara")} (link de cada sessão na lista abaixo)</small></div>
      <div class="numero"><b>${aus}</b><span>chamadas em que aparece como ausente</span><small>O sistema da Câmara não diz se a ausência foi justificada.</small></div>
    </div>
    <p class="suave">“Chamada” é a lista de presença feita no começo da sessão. Ausência registrada não quer dizer falta sem motivo: pode haver licença, atestado ou missão oficial.</p>
    <ul class="itens">${linhasP}</ul>

    </section>

    <section class="painel" data-painel="votos"${aba === "votos" ? "" : " hidden"}>
    <h2>Votos</h2>
    <p>${num(votos.length)} votações nas sessões já coletadas. ${resumoVotos}</p>
    <p class="suave">“Não vota” costuma aparecer para quem preside a sessão, que pelo regimento só vota em alguns casos. “Ausente” aqui é ausente no momento daquela votação.</p>
    <ul class="itens" id="votos">${votos.slice(0, 20).map(itemVoto).join("")}</ul>
    ${votos.length > 20 ? `<p class="mais"><button class="botao claro" id="mais-votos">Mostrar todas as ${num(votos.length)} votações</button></p>` : ""}
    </section>`;
}

const MESES_PT = { JANEIRO: "janeiro", FEVEREIRO: "fevereiro", MARCO: "março", ABRIL: "abril", MAIO: "maio", JUNHO: "junho", JULHO: "julho", AGOSTO: "agosto", SETEMBRO: "setembro", OUTUBRO: "outubro", NOVEMBRO: "novembro", DEZEMBRO: "dezembro" };
const reais = (x) => Number(x).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

const MESES_NOMES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const nomeMes = (k) => `${MESES_NOMES[+k.slice(5) - 1]}/${k.slice(0, 4)}`;

function seletorMes(f, mes) {
  const meses = (R.meses_folha || []).slice().reverse();
  if (!meses.length) return `<p class="suave">A folha de pagamento ainda não foi baixada.</p>`;
  if (!meses.includes(mes)) mes = meses[0];
  return `<label class="seletor">Mês <select id="mes-gasto">${meses.map((k) => `<option value="${k}"${k === mes ? " selected" : ""}>${nomeMes(k)}</option>`).join("")}</select></label>
    <div id="painel-mes">${secaoMes(f, mes)}</div>`;
}

function secaoMes(f, k) {
  const mes = nomeMes(k);
  const fonte = (f.folha_info || {}).fonte;
  const d = (f.folha_meses || {})[k] || { vereador: null, equipe: [], total_equipe: 0 };
  const ver = d.vereador
    ? `<div class="numero"><b>${reais(d.vereador.bruto)}</b><span>salário bruto do vereador em ${mes}</span><small>Líquido: ${reais(d.vereador.liquido)}. Nome na folha: ${$(d.vereador.nome)}${d.vereador.ligacao_fraca ? " (ligado a este vereador só pelo primeiro nome; confira no portal)" : ""}.</small><small>${ext(fonte, "Conferir no Portal da Transparência")}</small></div>`
    : `<div class="numero"><b>—</b><span>salário do vereador em ${mes}</span><small>Não encontramos o pagamento deste vereador na folha desse mês. Pode ter havido licença ou mudança; confira no portal.</small><small>${ext(fonte, "Portal da Transparência")}</small></div>`;
  const eq = `<div class="numero"><b>${reais(d.total_equipe)}</b><span>pagos em ${mes} à equipe do gabinete (${d.equipe.length} ${d.equipe.length === 1 ? "pessoa" : "pessoas"})</span><small>Soma dos salários brutos de quem está lotado no gabinete.</small><small>${ext(fonte, "Conferir no Portal da Transparência")}</small></div>`;
  const linhas = d.equipe.map((r) => `<tr><td>${$(r.nome)}</td><td>${$(r.cargo)}</td><td style="white-space:nowrap">${reais(r.bruto)}</td></tr>`).join("");
  return `<h3>Salário e equipe do gabinete</h3>
    <div class="numeros um">${ver}${eq}</div>
    ${d.equipe.length ? `<h3>Quem trabalha no gabinete</h3><table><tr><th>Nome</th><th>Cargo</th><th>Bruto</th></tr>${linhas}</table>` : ""}
    <p class="suave">Folha de pagamento publicada pela Câmara no Portal da Transparência. O valor bruto é o do portal e pode incluir férias, 13º ou outras verbas do mês. A lotação no gabinete é a informada pela Câmara.</p>
    <h3>Gastos do gabinete</h3>
    ${secaoGabineteMes(f, k)}`;
}

function secaoEmendas(f) {
  const infos = f.emendas_info || [];
  if (!infos.length) return `<p class="suave">As emendas impositivas ainda não foram baixadas.</p>`;
  return infos.slice().reverse().map((i) => {
    const lista = (f.emendas || {})[i.ano] || [];
    const total = lista.reduce((a, e) => a + e.valor, 0);
    const itens = lista.map((e) => `<li><b>${reais(e.valor)}</b> <span class="tag">${e.cota === "saúde" ? "cota saúde" : e.cota === "geral" ? "cota geral" : "cota não informada"}</span>
      <div>${$(e.destino)}</div><div class="meta">Emenda nº ${e.numero} · ${$(e.secretaria)}</div></li>`).join("");
    return `<p>Todo ano cada vereador indica para onde vai uma parte do orçamento da Prefeitura. Em regra, a Prefeitura é obrigada a executar essas indicações (salvo impedimento técnico), por isso se chamam emendas <b>impositivas</b>.</p>
      <div class="numeros um"><div class="numero"><b>${reais(total)}</b><span>indicados por ${$(f.apelido)} no orçamento de ${i.ano} (${lista.length} ${lista.length === 1 ? "emenda" : "emendas"})</span><small>${ext(i.documento, "Conferir na lei aprovada (" + $(i.lei) + ")")}</small></div></div>
      <ul class="itens">${itens || "<li>Nenhuma emenda encontrada.</li>"}</ul>
      <p class="suave">É o valor previsto na lei do orçamento. O site ainda não acompanha se a Prefeitura já gastou esse dinheiro. Todos os vereadores têm a mesma cota.</p>`;
  }).join("");
}

function secaoGabineteMes(f, k) {
  const g = f.gabinete;
  if (!g) return `<p class="suave">O relatório de gastos de gabinete deste vereador não foi encontrado no site da Câmara.</p>`;
  if (g.ano !== k.slice(0, 4)) return `<p class="suave">A Câmara só publica no site o relatório do ano corrente (${$(g.ano)}). Para ${nomeMes(k)} não há relatório disponível. ${ext(g.fonte, "Ver a lista de relatórios")}</p>`;
  const m = +k.slice(5) - 1;
  const fmt = (x) => Number(x).toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  const linhas = g.itens.map((i) => {
    const v = i.meses ? i.meses[m] : null;
    return `<tr><th>${$(i.item)}</th><td>${v == null ? "não foi possível ler" : v ? fmt(v) + " " + $(i.unidade) : "nada registrado"}</td><td class="suave">${i.limite_mensal ? "até " + fmt(i.limite_mensal) : ""}</td><td class="suave">${fmt(i.total)}${i.soma_difere ? "*" : ""}</td></tr>`;
  }).join("");
  const difere = g.itens.some((i) => i.soma_difere);
  return `<table><tr><th>Item</th><th>Em ${nomeMes(k)}</th><th>Limite por mês</th><th>No ano</th></tr>${linhas}</table>
    ${difere ? `<p class="suave">* Neste item, o total do ano impresso no relatório da Câmara não é igual à soma dos meses do próprio relatório. Mostramos os números como a Câmara publicou. Confira no PDF.</p>` : ""}
    <p class="suave">Desde 2019 (Ato da Mesa 254/2019) a Câmara publica esse relatório em quantidades (cópias, minutos, litros), e não em reais. Um mês sem número pode ainda não ter sido lançado. ${ext(g.pdf, "Ver o relatório (PDF)")}</p>`;
}

function itemVoto(x) {
  const t = x.voto === "A favor" ? "sim" : x.voto === "Contra" ? "nao" : "";
  return `<li><span class="tag ${t}">${$(x.voto)}</span> ${ext(x.url, $(x.materia))}
    <div>${$(x.assunto).slice(0, 220)}${x.assunto.length > 220 ? "…" : ""}</div>
    <div class="meta">${data(x.data)}${x.fase && x.fase !== "Não informado" ? " · " + $(x.fase) : ""}${x.autoria ? " · Autoria: " + $(x.autoria) : ""} · Resultado: ${$(x.resultado || "não informado na página")} · ${ext(x.sessao_url, "sessão")}</div></li>`;
}

async function telaGrupo(slug, g) {
  const f = await carregar(`vereador-${slug}.json`);
  const itens = f.grupos[g] || [];
  const tipos = {};
  itens.forEach((d) => { tipos[d[2]] = (tipos[d[2]] || 0) + 1; });
  setTimeout(() => ligarFiltro(itens), 0);
  return `
    <a class="voltar" href="#/v/${slug}?aba=propostas">← ${$(f.apelido)}</a>
    <h1>${$(R.grupos[g])}</h1>
    <p>${$(f.apelido)} · ${num(itens.length)} documentos desde ${data(R.inicio_mandato)}. ${$(EXPLICA[g])}</p>
    <p class="suave">Tipos no sistema da Câmara: ${Object.entries(tipos).map(([k, n]) => `${$(k)} (${num(n)})`).join(", ") || "nenhum"}. Fonte: ${ext(f.fonte_propostas, "página de proposituras do vereador")}.</p>
    <div class="busca"><input id="filtro" type="search" placeholder="Filtrar por palavra, rua ou bairro" aria-label="Filtrar"></div>
    <p class="suave" id="contagem"></p>
    <ul class="itens" id="lista"></ul>
    <p class="mais"><button class="botao claro" id="mais" hidden>Mostrar mais</button></p>`;
}

function ligarFiltro(itens) {
  const inp = document.getElementById("filtro"), ul = document.getElementById("lista"), mais = document.getElementById("mais"), cnt = document.getElementById("contagem");
  if (!inp) return;
  let vis = 50, atual = itens;
  const desenhar = () => {
    ul.innerHTML = atual.slice(0, vis).map((d) => `<li>${ext(SISCAM_DOC(d[0]), $(d[3]))}<div>${$(d[4])}</div><div class="meta">${data(d[1])} · ${$(d[2])}</div></li>`).join("");
    mais.hidden = atual.length <= vis;
    cnt.textContent = inp.value ? `${num(atual.length)} encontrados` : "";
  };
  inp.addEventListener("input", () => {
    const q = norm(inp.value);
    atual = q ? itens.filter((d) => norm(d[4] + " " + d[3]).includes(q)) : itens;
    vis = 50; desenhar();
  });
  mais.addEventListener("click", () => { vis += 100; desenhar(); });
  desenhar();
}

// ------------------------------------------------------------------ busca por bairro/rua
async function telaBusca(q) {
  const ped = await carregar("pedidos.json");
  setTimeout(() => ligarBusca(ped, q), 0);
  return `
    <h1>O que pediram para o meu bairro</h1>
    <p>Digite o nome do bairro ou da rua. Aparece tudo o que os vereadores pediram para lá desde ${data(R.inicio_mandato)}, e quem pediu.</p>
    <form class="busca" id="fbusca"><input id="q" type="search" placeholder="Ex.: Jardim Brasil ou Rua Capivari" aria-label="Bairro ou rua" value="${$(q || "")}" autocomplete="off"><button>Buscar</button></form>
    <div id="sugestoes"></div>
    <div id="resultado"></div>
    ${R.propostas_completas ? "" : `<div class="aviso">Atenção: os pedidos de alguns vereadores ainda não foram baixados, então a busca ainda não está completa.</div>`}`;
}

function nomeVer(i) { const v = vereador(R.slugs[i]); return v ? v.apelido : R.slugs[i]; }

function ligarBusca(ped, q0) {
  const f = document.getElementById("fbusca"), inp = document.getElementById("q"), out = document.getElementById("resultado"), sug = document.getElementById("sugestoes");
  if (!f) return;
  // bairros mais citados como atalho
  const cb = {};
  ped.forEach((p) => { if (p[5]) cb[p[5]] = (cb[p[5]] || 0) + 1; });
  const top = Object.entries(cb).sort((a, b) => b[1] - a[1]).slice(0, 12);
  sug.innerHTML = `<p class="suave">Bairros com mais pedidos:</p><div class="chips">${top.map(([b]) => `<button type="button" data-b="${$(b)}">${$(b)}</button>`).join("")}</div>`;
  sug.addEventListener("click", (e) => { const b = e.target.dataset.b; if (b) { inp.value = b; buscar(); } });
  f.addEventListener("submit", (e) => { e.preventDefault(); buscar(); });

  function buscar() {
    const q = norm(inp.value);
    history.replaceState(null, "", "#/busca?q=" + encodeURIComponent(inp.value));
    sug.hidden = q.length >= 3;
    if (q.length < 3) { out.innerHTML = `<p class="suave">Digite pelo menos 3 letras.</p>`; return; }
    const achados = ped.filter((p) => norm(p[5]).includes(q) || norm(p[4]).includes(q) || norm(p[3]).includes(q));
    if (!achados.length) { out.innerHTML = `<p>Nenhum pedido encontrado com “${$(inp.value)}”. Tente só uma parte do nome, sem “Jardim” ou “Vila”.</p>`; return; }
    // repetidos: mesma rua + mesmo assunto
    const grupos = {};
    achados.forEach((p) => { if (!p[4]) return; const k = norm(p[4]) + "|" + p[6]; (grupos[k] = grupos[k] || []).push(p); });
    const rep = Object.values(grupos).filter((g) => g.length >= 2).sort((a, b) => b.length - a.length);
    const porVer = {};
    achados.forEach((p) => p[7].forEach((i) => { porVer[i] = (porVer[i] || 0) + 1; }));
    out.innerHTML = `
      <h2>${num(achados.length)} pedidos encontrados</h2>
      <p class="suave">Quem pediu: ${Object.entries(porVer).sort((a, b) => b[1] - a[1]).map(([i, n]) => `<a href="#/v/${R.slugs[i]}">${$(nomeVer(i))}</a> (${num(n)})`).join(", ")}.</p>
      ${rep.length ? `<h2>Pedidos que se repetem</h2>
      <div class="aviso">Pedido repetido <b>não prova</b> que a Prefeitura ignorou o problema. O serviço pode ter sido feito e o problema ter voltado, o pedido pode ser para outro trecho da mesma rua, ou vereadores diferentes podem ter pedido a mesma coisa. Rua e assunto foram lidos do texto do pedido por um programa, e podem ter erros.</div>
      ${rep.slice(0, 30).map(itemRepetido).join("")}
      ${rep.length > 30 ? `<p class="suave">E mais ${num(rep.length - 30)} casos de repetição. Refine a busca para ver.</p>` : ""}` : ""}
      <h2>Todos os pedidos</h2>
      <ul class="itens">${achados.slice().reverse().slice(0, 200).map(itemPedido).join("")}</ul>
      ${achados.length > 200 ? `<p class="suave">Mostrando os 200 mais recentes. Refine a busca para ver os outros.</p>` : ""}
      <p><button type="button" class="botao claro" id="outra">Buscar outro bairro</button></p>`;
    document.getElementById("outra").onclick = () => { inp.value = ""; sug.hidden = false; out.innerHTML = ""; window.scrollTo(0, 0); inp.focus(); };
  }
  if (q0) buscar();
}

function itemRepetido(g) {
  const p0 = g[0];
  return `<details class="repetido"><summary>${$(p0[4])}${p0[5] ? " – " + $(p0[5]) : ""}: <b>${g.length} pedidos</b> de “${$(p0[6])}”</summary>
    <p class="suave">Datas: ${g.map((p) => data(p[1])).join(", ")}</p>
    <ul class="itens">${g.slice().reverse().map(itemPedido).join("")}</ul></details>`;
}

function itemPedido(p) {
  return `<li>${ext(SISCAM_DOC(p[0]), "Indicação " + $(p[2]))} <span class="tag">${$(p[6])}</span>
    <div>${$(p[3])}</div>
    <div class="meta">${data(p[1])} · ${p[7].map((i) => `<a href="#/v/${R.slugs[i]}">${$(nomeVer(i))}</a>`).join(", ")}</div></li>`;
}

// ------------------------------------------------------------------ gastos (todos os vereadores)
function telaGastos() {
  const i = R.folha_info, e = (R.emendas_info || []).slice(-1)[0];
  const mes = i ? `${MESES_PT[i.mes] || i.mes}/${i.ano}` : "";
  const fmt = (x) => (x == null ? "—" : Number(x).toLocaleString("pt-BR", { maximumFractionDigits: 1 }));
  const cards = R.vereadores.map((v) => {
    const d = v.dinheiro || {};
    return `<div class="caixa"><a href="#/v/${v.slug}"><b>${$(v.apelido)}</b></a> <span class="suave">${$(v.partido)}</span>
      <table>
        <tr><td>Salário bruto (${mes})</td><td style="text-align:right">${d.salario ? reais(d.salario) : "não encontrado"}</td></tr>
        <tr><td>Equipe do gabinete (${mes}), ${d.equipe_pessoas || 0} pessoas</td><td style="text-align:right">${reais(d.equipe_total || 0)}</td></tr>
        <tr><td>Emendas no orçamento de ${e ? e.ano : ""}</td><td style="text-align:right">${e && d.emendas ? reais(d.emendas[e.ano] || 0) : "—"}</td></tr>
        <tr><td>Gabinete em ${$(R.gabinete_ano)}: cópias e combustível</td><td style="text-align:right">${fmt(d.copias)} cópias<br>${fmt(d.combustivel)} litros</td></tr>
      </table><p class="suave"><a href="#/v/${v.slug}">Ver nomes da equipe, destino das emendas e fontes</a></p></div>`;
  }).join("");
  return `<h1>Gastos de cada vereador</h1>
    <p>Quanto cada vereador recebe, quanto custa a equipe do gabinete, quanto indicou em emendas do orçamento e o que o gabinete usou. Ordem alfabética.</p>
    ${cards}
    <p class="suave">Fontes: folha de pagamento no ${i ? ext(i.fonte, "Portal da Transparência") : "Portal da Transparência"}; emendas na ${e ? ext(e.documento, "lei do orçamento aprovada") : "lei do orçamento"}; cópias e combustível nos relatórios ${ext("https://www.camara-americana.sp.gov.br/Download/Listar/46", "Gastos com Gabinete")}, que a Câmara publica em quantidades, não em reais. Emenda é valor previsto no orçamento, não o que já foi gasto.</p>`;
}

// ------------------------------------------------------------------ sessões e sobre
function telaSessoes() {
  return `<h1>Sessões coletadas</h1>
    ${avisoSessoes()}
    <ul class="itens">${R.sessoes.slice().reverse().map((s) => `<li>${ext(s.url, $(s.titulo))}<div class="meta">${data(s.data)} · ${s.chamadas.length} chamada(s) de presença · ${s.votacoes} votações</div></li>`).join("")}</ul>
    <p class="suave">A lista completa de sessões está no ${ext("https://americana.siscam.com.br/sessoes", "sistema da Câmara")}. Os vídeos ficam no ${ext("https://www.youtube.com/user/cmamericana/videos", "canal da Câmara no YouTube")}.</p>`;
}

async function telaSobre() {
  let ver = "";
  try {
    const v = await carregar("verificacao.json");
    const ok = v.checagens.filter((c) => c.ok).length;
    ver = `<p>Na última atualização, ${ok} de ${v.checagens.length} conferências automáticas bateram.</p>
      <details><summary>Ver as conferências</summary><ul>${v.checagens.map((c) => `<li>${c.ok ? "✔" : "✘"} ${$(c.texto)}</li>`).join("")}</ul></details>
      ${v.avisos.length ? `<details><summary>Avisos (${v.avisos.length})</summary><ul>${v.avisos.map((a) => `<li>${$(a)}</li>`).join("")}</ul></details>` : ""}`;
  } catch (e) { ver = ""; }
  const corr = CONTATO_CORRECAO.url ? ext(CONTATO_CORRECAO.url, $(CONTATO_CORRECAO.texto)) : $(CONTATO_CORRECAO.texto);
  return `<h1>Como funciona</h1>
    <p>Este site junta, num lugar só e em linguagem simples, o que já é público no sistema da Câmara Municipal de Americana. Não damos nota, não fazemos ranking e não opinamos. Só mostramos o dado e o link para a fonte.</p>

    <h2>De onde vêm os dados</h2>
    <ul>
      <li><b>Vereadores, partido e contato do gabinete:</b> ${ext("https://www.camara-americana.sp.gov.br/Vereador", "site da Câmara")}.</li>
      <li><b>Propostas:</b> a página de proposituras de cada vereador no ${ext("https://americana.siscam.com.br/", "SISCAM")}, o sistema oficial da Câmara. Quando essa página é grande demais e não abre, usamos a exportação em planilha da pesquisa oficial do próprio SISCAM, que traz só os tipos principais; a ficha do vereador avisa quando isso acontece.</li>
      <li><b>Emendas impositivas:</b> o “Anexo Especial de Emendas Individuais Impositivas” da lei do orçamento aprovada (para 2026, o Autógrafo nº 125/2025), no SISCAM. Mostramos o valor previsto, não o que já foi gasto.</li>
      <li><b>Salário e equipe do gabinete:</b> a folha de pagamento do ${ext("https://transparencia-cmamericana.smarapd.com.br/#/dinamico/restoapagar/pagamentosaservidores", "Portal da Transparência da Câmara")} (último mês fechado). Usamos só as linhas de vereadores e de quem está lotado em gabinete de vereador. O “Gabinete da Presidência” é da Mesa Diretora e não entra na conta de nenhum vereador.</li>
      <li><b>Gastos do gabinete:</b> os relatórios “Gastos com Gabinete” publicados em PDF no ${ext("https://www.camara-americana.sp.gov.br/Download/Listar/46", "site da Câmara")}, um por vereador, em quantidades (não em reais).</li>
      <li><b>Presença e votos:</b> a página de cada sessão no SISCAM, que traz a chamada nominal e o voto de cada vereador em cada votação.</li>
    </ul>
    <p>Um robô identificado como “AmericanaFiscaliza” baixa poucas páginas por vez, com pausa entre elas, para não pesar no sistema da Câmara. Se a Câmara pedir, ele para.</p>

    <h2 id="grupos">Como as propostas são separadas</h2>
    <p>A mesma regra vale para todos os vereadores. Ela olha o tipo do documento no sistema da Câmara e, em alguns casos, palavras do assunto:</p>
    <table>${R.regras.map(([g, r]) => `<tr><th>${$(g)}</th><td>${$(r)}</td></tr>`).join("")}</table>
    <p class="suave">Contamos só documentos com data a partir de ${data(R.inicio_mandato)}, início do mandato atual. Documento com vários autores conta para cada um.</p>

    <h2>O que é conta nossa ou leitura automática</h2>
    <ul>
      <li>A separação em grupos (acima) é nossa. Os tipos originais aparecem dentro de cada grupo.</li>
      <li>Na busca por bairro, a rua, o bairro e o assunto do pedido (buraco, árvore, iluminação…) são lidos do texto por um programa. Pode haver erro de leitura, nome de rua escrito de jeitos diferentes, ou pedido sem bairro.</li>
      <li>“Pedidos que se repetem” junta pedidos da mesma rua e do mesmo assunto. Não sabemos se é o mesmo trecho nem se o serviço foi feito.</li>
      <li>Presença é contada pela chamada registrada no sistema. Se uma sessão não tiver registro de chamada, ninguém aparece como ausente nela.</li>
    </ul>

    <h2>Cuidados</h2>
    <ul>
      <li>Só dado oficial. Nada de reportagem, boato ou print.</li>
      <li>Ausência registrada não é falta sem motivo. O sistema não mostra justificativas.</li>
      <li>Ter muitos documentos não quer dizer trabalho melhor, e ter poucos não quer dizer pior. Uma lei pode valer mais que mil pedidos, e vice-versa.</li>
      <li>Só contatos públicos do gabinete, como estão no site da Câmara.</li>
    </ul>

    <h2>Conferência dos números</h2>
    ${ver}

    <h2 id="correcao">Achou um erro?</h2>
    <p>Avise por ${corr}. Diga a página e o número que está errado; se puder, mande o link oficial certo. Corrigimos o quanto antes e registramos a correção.</p>`;
}

// ------------------------------------------------------------------ rotas
async function rota() {
  const h = location.hash.replace(/^#\/?/, "").split("#")[0];
  const [caminho, qs] = h.split("?");
  const partes = caminho.split("/").filter(Boolean);
  document.querySelectorAll(".topo nav a").forEach((a) => {
    const alvo = a.getAttribute("href").replace(/^#\/?/, "");
    a.classList.toggle("ativo", alvo === (partes[0] || "") || (alvo === "" && partes[0] === "v"));
  });
  try {
    if (!R) R = await carregar("resumo.json");
    let html;
    if (partes[0] === "v" && partes[2]) html = await telaGrupo(partes[1], partes[2]);
    else if (partes[0] === "v") html = await telaVereador(partes[1], new URLSearchParams(qs || "").get("aba"), new URLSearchParams(qs || "").get("mes"));
    else if (partes[0] === "busca") html = await telaBusca(new URLSearchParams(qs || "").get("q"));
    else if (partes[0] === "sessoes") html = telaSessoes();
    else if (partes[0] === "gastos") html = telaGastos();
    else if (partes[0] === "sobre") html = await telaSobre();
    else html = telaInicio();
    app.innerHTML = html;
    document.querySelectorAll(".abas button").forEach((t) => t.onclick = () => {
      document.querySelectorAll(".abas button").forEach((x) => x.setAttribute("aria-selected", x === t));
      document.querySelectorAll(".painel").forEach((p) => { p.hidden = p.dataset.painel !== t.dataset.aba; });
      history.replaceState(null, "", `#/v/${partes[1]}?aba=${t.dataset.aba}`);
    });
    const sel = document.getElementById("mes-gasto");
    if (sel) sel.onchange = async () => {
      const f = await carregar(`vereador-${partes[1]}.json`);
      document.getElementById("painel-mes").innerHTML = secaoMes(f, sel.value);
      history.replaceState(null, "", `#/v/${partes[1]}?aba=gastos&mes=${sel.value}`);
    };
    const b = document.getElementById("mais-votos");
    if (b) b.onclick = async () => { const f = await carregar(`vereador-${partes[1]}.json`); document.getElementById("votos").innerHTML = f.votos.slice().reverse().map(itemVoto).join(""); b.remove(); };
    document.getElementById("atualizado").textContent = `Dados atualizados em ${new Date(R.gerado_em).toLocaleDateString("pt-BR")}.`;
    const ancora = location.hash.split("#")[2];
    if (ancora && document.getElementById(ancora)) document.getElementById(ancora).scrollIntoView();
    else window.scrollTo(0, 0);
  } catch (e) {
    app.innerHTML = `<p>Não foi possível carregar os dados agora. Tente recarregar a página.</p>`;
    console.error(e);
  }
}
window.addEventListener("hashchange", rota);
rota();
