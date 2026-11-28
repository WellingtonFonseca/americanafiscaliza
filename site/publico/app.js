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
const ICONE_SAIR = `<svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6"/><path d="M20 4l-9 9"/><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>`;
const ext = (url, txt) => `<a href="${$(url)}" rel="noopener" target="_blank">${txt}</a>`;

// Mandato escolhido no topo. O atual fica em dados/; um mandato antigo ficaria em dados/<id>/.
let MANDATO = null;
let MANDATOS = null;
function lerEscolha() { try { return localStorage.getItem("mandato"); } catch (e) { return null; } }
function guardarEscolha(id) { try { localStorage.setItem("mandato", id); } catch (e) { /* sem armazenamento: vale só nesta visita */ } }
const pastaDados = () => (!MANDATOS || !MANDATO || MANDATO === MANDATOS[0].id ? "dados/" : `dados/${MANDATO}/`);

async function carregar(nome) {
  if (window.DADOS_EMBUTIDOS && window.DADOS_EMBUTIDOS[nome]) return window.DADOS_EMBUTIDOS[nome];
  const chave = pastaDados() + nome;
  if (!cache[chave]) cache[chave] = fetch(chave + "?v=" + VERSAO).then((r) => { if (!r.ok) throw new Error(nome); return r.json(); });
  return cache[chave];
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
  if (R.sessoes_completas) return "";
  return `<div class="aviso"><b>Histórico de sessões ainda parcial.</b> Por enquanto o site tem ${R.sessoes.length} sessões, de ${data(p[0])} a ${data(p[1])}. As outras estão sendo baixadas aos poucos (até 10 por atualização), para não sobrecarregar o sistema da Câmara. Presença e votos valem só para essas sessões. Este aviso some quando todas as sessões do mandato estiverem no site.</div>`;
}

// ------------------------------------------------------------------ telas
const ORDENS = [
  ["nome", "Nome (A a Z)", null],
  ["faltas", "Quem mais faltou", (v) => v.ausente],
  ["lei", "Mais propostas de lei", (v) => v.grupos.lei],
  ["homenagem", "Mais homenagens", (v) => v.grupos.homenagem],
  ["bairro", "Mais pedidos para os bairros", (v) => v.grupos.bairro],
  ["cobranca", "Mais cobranças à Prefeitura", (v) => v.grupos.cobranca],
  ["contra", "Quem mais votou contra", (v) => v.votos_contra],
  ["gabinete", "Maior custo de gabinete (último mês)", (v) => (v.dinheiro || {}).equipe_total],
];

function itemLista(v, ordem, pos) {
  // número principal do cartão: o da ordem escolhida, ou pedidos de bairro na ordem por nome
  const d = v.dinheiro || {};
  const principal = {
    faltas: [num(v.ausente), `ausências em ${num(v.chamadas)} chamadas`],
    lei: [num(v.grupos.lei), "propostas de lei"], homenagem: [num(v.grupos.homenagem), "homenagens"],
    bairro: [num(v.grupos.bairro), "pedidos de bairro"], cobranca: [num(v.grupos.cobranca), "cobranças à Prefeitura"],
    contra: [num(v.votos_contra), `votos contra em ${num(v.votacoes)} votações`],
    gabinete: [reais(d.equipe_total || 0), "equipe do gabinete no mês"],
  }[ordem] || (v.propostas_baixadas ? [num(v.grupos.bairro), "pedidos de bairro"] : ["—", "propostas ainda não baixadas"]);
  const extra = ordem === "faltas" || ordem === "contra" ? "" : `Presença: ${v.presente} de ${v.chamadas}`;
  const parcial = v.propostas_parcial && ["nome", "lei", "homenagem", "bairro", "cobranca"].includes(ordem);
  return `<li><a href="#/v/${v.slug}">
      <img src="${$(fotoLocal(v))}" alt="" loading="lazy" width="64" height="64" onerror="this.style.visibility='hidden'">
      <span class="corpo">
        <span class="linha-nome"><span class="nome">${$(v.apelido)}</span> <span class="partido">${$(v.partido)}</span></span>
        <span class="principal"><b>${principal[0]}</b> ${principal[1]}</span>
        ${extra ? `<span class="extra">${extra}</span>` : ""}
        ${parcial ? `<span class="parcial">Propostas parciais</span>` : ""}
      </span>
      <svg class="seta" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
    </a></li>`;
}

function desenharLista() {
  const q = chave((document.getElementById("f-nome") || {}).value || "");
  const partido = (document.getElementById("f-partido") || {}).value || "";
  const ordem = (document.getElementById("f-ordem") || {}).value || "nome";
  const o = ORDENS.find((x) => x[0] === ordem);
  let vs = R.vereadores.filter((v) => (!partido || v.partido === partido) && (!q || chave(v.apelido + " " + v.nome).includes(q)));
  vs = vs.slice().sort((a, b) => (o[2] ? (o[2](b) || 0) - (o[2](a) || 0) : 0) || a.apelido.localeCompare(b.apelido, "pt-BR"));
  const el = document.getElementById("lista-ver");
  if (el) el.innerHTML = vs.length ? vs.map((v, i) => itemLista(v, ordem, i + 1)).join("") : `<li class="suave" style="padding:12px 0">Nenhum vereador encontrado.</li>`;
  const nota = document.getElementById("nota-ordem");
  if (nota) nota.innerHTML = {
    faltas: "Ausência registrada não quer dizer falta sem motivo: pode haver licença, atestado ou missão oficial. Vale só para as sessões já coletadas.",
    contra: "Vale só para as sessões já coletadas. Votar contra não é bom nem ruim por si só.",
    lei: "Quantidade não mede qualidade: uma lei pode valer mais que muitas.", homenagem: "Homenagens incluem moções de aplauso, de pesar, títulos e nomes de ruas.",
    bairro: "Pedido não é obra feita: o sistema da Câmara não diz se a Prefeitura atendeu.", cobranca: "Requerimentos, pedidos de informação e moções de apelo.",
    gabinete: "Soma dos salários brutos da equipe no último mês fechado da folha.",
  }[ordem] || "";
}

const chave = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

function telaInicio() {
  const partidos = [...new Set(R.vereadores.map((v) => v.partido))].sort();
  const pt = R.pago_total;
  const milhoes = (x) => (x / 1e6).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " milhões";
  const contador = pt && pt.de ? `<div class="destaque">
      <span class="etiqueta">Folha oficial</span>
      <b>R$ ${milhoes(pt.vereadores + pt.equipes)}</b>
      <span>pagos aos vereadores e às equipes dos gabinetes de ${nomeMes(pt.de)} a ${nomeMes(pt.ate)}</span>
      <ul class="arvore">
        <li><span>Vereadores</span><strong>${reais(pt.vereadores)}</strong></li>
        <li><span>Equipes dos gabinetes</span><strong>${reais(pt.equipes)}</strong></li>
      </ul>
      <small>Soma dos salários brutos na folha oficial, mês a mês. ${ext(R.folha_info.fonte, "Portal da Transparência")} · <a href="#/gastos">Ver por vereador</a></small>
    </div>` : "";
  return `
    <h1 class="so-leitor">O que o prefeito e cada vereador de Americana fazem</h1>
    ${contador}
    <div class="entradas">
      <a href="#/busca"><span class="icone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg></span><span><b>O que pediram pelo seu bairro?</b><span>Digite o bairro ou a rua e veja os pedidos de melhoria, quem pediu e o que se repete.</span></span></a>
      <a href="#/repetidos"><span class="icone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 15.5-6.2L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15.5 6.2L3 16"/><path d="M3 21v-5h5"/></svg></span><span><b>O problema que não some</b><span>Ruas onde o mesmo pedido voltou várias vezes desde 2025.</span></span></a>
      <a href="#/comparar"><span class="icone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg></span><span><b>Homenagem ou trabalho?</b><span>As propostas de cada vereador lado a lado: pedidos de bairro, cobranças, homenagens e leis.</span></span></a>
      <a href="#/gastos"><span class="icone"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M15 9.5c-.5-1-1.6-1.5-3-1.5-1.7 0-3 .8-3 2s1.3 1.7 3 2 3 .8 3 2-1.3 2-3 2c-1.4 0-2.5-.5-3-1.5M12 6.5V8m0 8v1.5"/></svg></span><span><b>Quanto custa cada gabinete?</b><span>Salário, equipe com nomes, emendas e o que o gabinete usou.</span></span></a>
    </div>
    ${avisoSessoes()}
    ${R.vereadores.some((v) => v.propostas_parcial || !v.propostas_baixadas) ? `<div class="aviso">Para ${R.vereadores.filter((v) => v.propostas_parcial || !v.propostas_baixadas).length} vereadores as propostas ainda estão parciais (o sistema da Câmara não abriu a página completa deles). Isso está marcado na ficha de cada um.</div>` : ""}
    ${cartaoPrefeitoLista()}
    <h2>Vereadores</h2>
    <div class="filtros">
      <input id="f-nome" type="search" placeholder="Procurar pelo nome" aria-label="Procurar vereador pelo nome">
      <select id="f-partido" aria-label="Partido"><option value="">Todos os partidos</option>${partidos.map((p) => `<option>${$(p)}</option>`).join("")}</select>
      <select id="f-ordem" aria-label="Ordenar por">${ORDENS.map(([k, t]) => `<option value="${k}">${t}</option>`).join("")}</select>
    </div>
    <p class="suave" id="nota-ordem"></p>
    <ul class="lista-ver" id="lista-ver"></ul>
    <p class="suave">Ordenar a lista não é dar nota. Os números mostram quantidade, não qualidade. Propostas contadas de ${data(R.inicio_mandato)} em diante (${$(R.mandato ? R.mandato.nome : "mandato atual")}), para todos da mesma forma.</p>
    ${deOndeVem()}`;
}

function deOndeVem() {
  return `<h2>De onde vêm os números</h2>
    <dl class="origem">
      <dt>Propostas</dt><dd>Do sistema da Câmara (SISCAM), desde ${data(R.inicio_mandato)}. Cada documento é colocado num grupo por <a href="#/sobre#grupos">uma regra única</a>, pelo tipo e pelo texto oficial, igual para todos.</dd>
      <dt>Pedido não é obra feita</dt><dd>Um pedido de melhoria mostra que o vereador pediu. O sistema da Câmara não diz se a Prefeitura atendeu. Pedido repetido na mesma rua também não prova que nada foi feito: pode ser outro trecho.</dd>
      <dt>Presença</dt><dd>Da lista de chamada de cada sessão. Ausência registrada não quer dizer falta sem motivo: pode haver licença, atestado ou missão oficial.</dd>
      <dt>Votos</dt><dd>Do voto nominal registrado em cada sessão, matéria por matéria.</dd>
      <dt>Salário e equipe</dt><dd>Da folha de pagamento no Portal da Transparência da Câmara, mês a mês. Valor bruto, como o portal publica.</dd>
      <dt>Gastos do gabinete</dt><dd>Do relatório oficial da Câmara, que desde 2019 vem em quantidades (cópias, minutos, litros), não em reais.</dd>
      <dt>Emendas impositivas</dt><dd>Da lei do orçamento aprovada. É o valor previsto, não o que a Prefeitura já gastou.</dd>
      <dt>Achou um erro?</dt><dd>Compare com o link oficial ao lado de cada número e <a href="#/sobre#correcao">avise aqui</a>. Se a Câmara corrigir o registro dela, o número muda aqui na atualização seguinte.</dd>
    </dl>`;
}

async function telaRepetidos() {
  const d = await carregar("repetidos.json");
  const casos = d.casos.map((c) => `<details class="repetido caso">
      <summary><span class="caso-vezes"><b>${num(c.pedidos.length)}</b> pedidos</span>
        <span class="caso-rua">${$(c.rua)}${c.bairro ? `<span class="caso-bairro">${$(c.bairro)}</span>` : ""}</span>
        <span class="tag">${$(c.assunto)}</span>
        <span class="caso-meta">De ${num(c.vereadores)} ${c.vereadores === 1 ? "vereador" : "vereadores"} · primeiro em ${data(c.primeiro)} · último em ${data(c.ultimo)}</span>
        <span class="caso-abrir">Ver os pedidos</span></summary>
      <ul class="itens">${c.pedidos.map(itemPedido).join("")}</ul></details>`).join("");
  return `<a class="voltar" href="#/">← Início</a>
    <h1>O problema que não some</h1>
    <div class="aviso alerta">Desde ${data(R.inicio_mandato)}, encontramos <b>${num(d.total_casos)}</b> casos de pedido repetido para a mesma rua. Em <b>${num(d.casos_5_ou_mais)}</b> deles o pedido apareceu 5 vezes ou mais. Abaixo estão os ${d.casos.length} que mais se repetem.</div>
    <div class="aviso info">Quando o mesmo pedido volta várias vezes para a mesma rua, <b>pode ser</b> sinal de que o problema continua. O site da Câmara não mostra isso: nós cruzamos os pedidos um por um, pela rua e pelo assunto.</div>
    <div class="aviso">Repetição <b>não prova</b> que a Prefeitura ignorou o problema. Rua comprida ou avenida tem vários trechos, vereadores diferentes podem pedir a mesma coisa na mesma semana, e o serviço pode ter sido feito e o problema ter voltado. A rua e o assunto foram lidos do texto do pedido por um programa e podem ter erros. Abra e leia os pedidos para tirar a sua conclusão.</div>
    ${casos}
    <p><a class="botao" href="#/busca">Procurar a minha rua ou bairro</a></p>`;
}

function telaComparar() {
  const gs = ["bairro", "cobranca", "homenagem", "lei"];
  const curto = { bairro: "Pedidos de bairro", cobranca: "Cobranças", homenagem: "Homenagens", lei: "Leis" };
  const max = Object.fromEntries(gs.map((g) => [g, Math.max(1, ...R.vereadores.map((v) => v.grupos[g] || 0))]));
  const vs = R.vereadores.slice().sort((a, b) => a.apelido.localeCompare(b.apelido, "pt-BR"));
  const cartoes = vs.map((v) => `<div class="comp">
      <div class="comp-cab"><img src="${$(fotoLocal(v))}" alt="" loading="lazy" width="48" height="48" onerror="this.style.visibility='hidden'">
        <div><a class="comp-nome" href="#/v/${v.slug}?aba=propostas">${$(v.apelido)}</a><span class="comp-partido">${$(v.partido)}</span>${v.propostas_parcial ? `<span class="parcial">Propostas parciais *</span>` : ""}</div></div>
      <div class="comp-grade">${gs.map((g) => `<a class="comp-num comp-${g}" href="#/v/${v.slug}/${g}">
          <b>${num(v.grupos[g])}</b><span>${curto[g]}</span>
          <i class="barra" style="width:${Math.max(2, Math.round((v.grupos[g] / max[g]) * 100))}%"></i></a>`).join("")}</div>
    </div>`).join("");
  return `<a class="voltar" href="#/">← Início</a>
    <h1>Homenagem ou trabalho?</h1>
    <p>Quantos documentos de cada grupo cada vereador apresentou desde ${data(R.inicio_mandato)}. Toque num número para ler os documentos um por um. A barrinha compara com o maior número do grupo.</p>
    ${vs.some((v) => v.propostas_parcial) ? `<div class="aviso">* <b>Propostas parciais:</b> a página completa deste vereador não abriu no sistema da Câmara. Usamos a exportação oficial, que não traz pedidos de informação nem emendas, então “Cobranças” e “Leis” podem estar abaixo do real.</div>` : ""}
    ${cartoes}
    <p class="suave">Os grupos seguem <a href="#/sobre#grupos">uma regra única</a>, igual para todos. Quantidade não mede qualidade: uma lei pode valer mais que muitos pedidos. Um documento com mais de um autor conta para cada um deles.</p>`;
}

function fotoLocal(v) { return `fotos/${v.slug}.jpg`; }

function cartao(slugV, g, itens, fonte, parcial) {
  const n = itens.length;
  let det = EXPLICA[g];
  if (parcial && g === "lei") det += " Sem as emendas (dados parciais).";
  if (parcial && g === "cobranca") det += " Sem os pedidos de informação (dados parciais).";
  if (g === "outros" && n) {
    const t = {}; itens.forEach((d) => { t[d[2]] = (t[d[2]] || 0) + 1; });
    det = "Os tipos mais comuns: " + Object.entries(t).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k, c]) => `${k} (${num(c)})`).join(", ") + ".";
  }
  const camara = `<a class="parte-camara" href="${$(fonte)}" rel="noopener" target="_blank">${ICONE_SAIR} Conferir no site da Câmara</a>`;
  if (parcial && g === "outros") return `<div class="numero dividido"><div class="parte-site"><b>—</b><span>${$(R.grupos[g])}</span><small>Ainda não baixados para este vereador.</small></div>${camara}</div>`;
  return `<div class="numero dividido">
    <a class="parte-site" href="#/v/${slugV}/${g}"><b>${num(n)}</b><span>${$(R.grupos[g])}</span>
    <small>${$(det)}</small><em class="ver-aqui">Ver ${n === 1 ? "o documento" : "os documentos"} aqui ›</em></a>
    ${camara}</div>`;
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
      <div class="numeros dois">${Object.keys(R.grupos).map((g) => cartao(slug, g, f.grupos[g], f.fonte_propostas, f.propostas_parcial)).join("")}</div>
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
    <div class="aviso info">Folha de pagamento publicada pela Câmara no Portal da Transparência. O valor bruto é o do portal e pode incluir férias, 13º ou outras verbas do mês. A lotação no gabinete é a informada pela Câmara.</div>
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
    return `<div class="aviso">É o valor previsto na lei do orçamento. O site ainda não acompanha se a Prefeitura já gastou esse dinheiro. Todos os vereadores têm a mesma cota.</div>
      <div class="aviso info">Todo ano cada vereador indica para onde vai uma parte do orçamento da Prefeitura. Em regra, a Prefeitura é obrigada a executar essas indicações (salvo impedimento técnico), por isso se chamam emendas <b>impositivas</b>.</div>
      <div class="numeros um"><div class="numero"><b>${reais(total)}</b><span>indicados por ${$(f.apelido)} no orçamento de ${i.ano} (${lista.length} ${lista.length === 1 ? "emenda" : "emendas"})</span><small>${ext(i.documento, "Conferir na lei aprovada (" + $(i.lei) + ")")}</small></div></div>
      <ul class="itens">${itens || "<li>Nenhuma emenda encontrada.</li>"}</ul>`;
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
    return `<tr><th>${$(i.item)}${i.limite_mensal ? `<div class="suave" style="font-weight:400">limite: ${fmt(i.limite_mensal)} por mês</div>` : ""}</th><td>${v == null ? "não foi possível ler" : v ? fmt(v) + " " + $(i.unidade) : "nenhum"}</td><td>${fmt(i.total)}${i.soma_difere ? "*" : ""}</td></tr>`;
  }).join("");
  const difere = g.itens.some((i) => i.soma_difere);
  return `<table><tr><th>Item</th><th>No mês</th><th>No ano</th></tr>${linhas}</table>
    ${difere ? `<div class="aviso">* Neste item, o total do ano impresso no relatório da Câmara não é igual à soma dos meses do próprio relatório. Mostramos os números como a Câmara publicou. Confira no PDF.</div>` : ""}
    <div class="aviso info">Desde 2019 (Ato da Mesa 254/2019) a Câmara publica esse relatório em quantidades (cópias, minutos, litros), e não em reais. Um mês sem número pode ainda não ter sido lançado. ${ext(g.pdf, "Ver o relatório (PDF)")}</div>`;
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
    <p>Digite parte do nome do bairro ou da rua, para realizar a busca.</p>
    <form class="busca" id="fbusca"><input id="q" type="search" placeholder="Ex.: Jardim Brasil ou Rua Capivari" aria-label="Bairro ou rua" value="${$(q && q !== "*" ? q : "")}" autocomplete="off"><button>Buscar</button><button type="button" class="botao claro" id="todos">Todos</button></form>
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
  document.getElementById("todos").onclick = () => { inp.value = ""; buscar(true); };

  function buscar(todos) {
    const q = norm(inp.value);
    history.replaceState(null, "", "#/busca?q=" + (todos ? "*" : encodeURIComponent(inp.value)));
    sug.hidden = todos || q.length >= 3;
    if (!todos && q.length < 3) { out.innerHTML = `<p class="suave">Digite pelo menos 3 letras, ou toque em “Todos” para ver a cidade inteira.</p>`; return; }
    const achados = todos ? ped : ped.filter((p) => norm(p[5]).includes(q) || norm(p[4]).includes(q) || norm(p[3]).includes(q));
    if (!achados.length) { out.innerHTML = `<p>Nenhum pedido encontrado com “${$(inp.value)}”. Tente só uma parte do nome, sem “Jardim” ou “Vila”.</p>`; return; }
    // repetidos: mesma rua + mesmo assunto
    const grupos = {};
    achados.forEach((p) => { if (!p[4]) return; const k = norm(p[4]) + "|" + p[6]; (grupos[k] = grupos[k] || []).push(p); });
    const rep = Object.values(grupos).filter((g) => g.length >= 2).sort((a, b) => b.length - a.length);
    const porVer = {};
    achados.forEach((p) => p[7].forEach((i) => { porVer[i] = (porVer[i] || 0) + 1; }));
    out.innerHTML = `
      <h2>${todos ? `Todos os pedidos da cidade: ${num(achados.length)}` : `${num(achados.length)} pedidos encontrados`}</h2>
      <h3>Quem pediu</h3>
      <ul class="quem-pediu">${Object.entries(porVer).sort((a, b) => b[1] - a[1]).map(([i, n]) => `<li><a href="#/v/${R.slugs[i]}">${$(nomeVer(i))}</a><span>${num(n)} ${n === 1 ? "pedido" : "pedidos"}</span></li>`).join("")}</ul>
      ${rep.length ? `<h2>Pedidos que se repetem</h2>
      <div class="aviso">Pedido repetido <b>não prova</b> que a Prefeitura ignorou o problema. O serviço pode ter sido feito e o problema ter voltado, o pedido pode ser para outro trecho da mesma rua, ou vereadores diferentes podem ter pedido a mesma coisa. Rua e assunto foram lidos do texto do pedido por um programa, e podem ter erros.</div>
      ${rep.slice(0, 30).map(itemRepetido).join("")}
      ${rep.length > 30 ? `<p class="suave">E mais ${num(rep.length - 30)} casos de repetição. Refine a busca para ver.</p>` : ""}` : ""}
      <h2>${todos ? "Pedidos mais recentes" : "Pedidos encontrados"}</h2>
      <ul class="itens">${achados.slice().reverse().slice(0, 200).map(itemPedido).join("")}</ul>
      ${achados.length > 200 ? `<p class="suave">Mostrando os 200 mais recentes. ${todos ? "Pesquise um bairro ou rua" : "Refine a busca"} para ver os outros.</p>` : ""}
      <p><button type="button" class="botao claro" id="outra">Buscar outro bairro</button></p>`;
    document.getElementById("outra").onclick = () => { inp.value = ""; sug.hidden = false; out.innerHTML = ""; window.scrollTo(0, 0); inp.focus(); };
  }
  if (q0 === "*") buscar(true);
  else if (q0) buscar();
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
  const val = {
    salario: (v) => (v.dinheiro || {}).salario || 0,
    equipe: (v) => (v.dinheiro || {}).equipe_total || 0,
    emendas: (v) => (e && ((v.dinheiro || {}).emendas || {})[e.ano]) || 0,
    copias: (v) => (v.dinheiro || {}).copias || 0,
    combustivel: (v) => (v.dinheiro || {}).combustivel || 0,
  };
  const max = Object.fromEntries(Object.entries(val).map(([k, f]) => [k, Math.max(1, ...R.vereadores.map(f))]));
  const barra = (k, v, cor) => `<i class="barra" style="background:${cor};width:${val[k](v) ? Math.max(2, Math.round((val[k](v) / max[k]) * 100)) : 0}%"></i>`;
  const vs = R.vereadores.slice().sort((a, b) => a.apelido.localeCompare(b.apelido, "pt-BR"));
  const cartoes = vs.map((v) => {
    const d = v.dinheiro || {};
    return `<div class="comp">
      <div class="comp-cab"><img src="${$(fotoLocal(v))}" alt="" loading="lazy" width="48" height="48" onerror="this.style.visibility='hidden'">
        <div><a class="comp-nome" href="#/v/${v.slug}">${$(v.apelido)}</a><span class="comp-partido">${$(v.partido)}</span></div></div>
      <div class="comp-grade comp-dinheiro">
        <a class="comp-num" href="#/v/${v.slug}?aba=gastos"><b>${d.salario ? reais(d.salario) : "—"}</b><span>${d.salario ? `Salário bruto em ${mes}` : `Salário não encontrado em ${mes}`}</span>${barra("salario", v, "#1d55b8")}</a>
        <a class="comp-num" href="#/v/${v.slug}?aba=gastos"><b>${reais(d.equipe_total || 0)}</b><span>Equipe do gabinete em ${mes} (${d.equipe_pessoas || 0} ${d.equipe_pessoas === 1 ? "pessoa" : "pessoas"})</span>${barra("equipe", v, "#6a3fb5")}</a>
        <a class="comp-num" href="#/v/${v.slug}?aba=gastos"><b>${e && d.emendas ? reais(d.emendas[e.ano] || 0) : "—"}</b><span>Emendas no orçamento de ${e ? e.ano : ""}</span>${barra("emendas", v, "#1e7a46")}</a>
        <a class="comp-num" href="#/v/${v.slug}?aba=gastos"><b>${fmt(d.copias)}</b><span>Cópias e impressões em ${$(R.gabinete_ano)}</span>${barra("copias", v, "#c4410f")}</a>
        <a class="comp-num" href="#/v/${v.slug}?aba=gastos"><b>${fmt(d.combustivel)} litros</b><span>Combustível em ${$(R.gabinete_ano)}</span>${barra("combustivel", v, "#8a5a00")}</a>
      </div>
      <p class="comp-mais"><a href="#/v/${v.slug}?aba=gastos">Ver nomes da equipe, destino das emendas e outros meses</a></p>
    </div>`;
  }).join("");
  return `<h1>Gastos do prefeito e de cada vereador</h1>
    <div class="aviso info">Quanto cada vereador recebe, quanto custa a equipe do gabinete, quanto indicou em emendas do orçamento e o que o gabinete usou. Toque num quadro para ver os detalhes e escolher outros meses. A barrinha compara com o maior valor de cada quadro.</div>
    <div class="aviso">Salário e equipe são de <b>${mes}</b>, último mês fechado da folha. Emenda é o valor <b>previsto</b> no orçamento, não o que já foi gasto. Cópias e combustível são o total do ano no relatório da Câmara, que vem em quantidades, não em reais.</div>
    ${cartaoPrefeitoGastos()}
    ${cartoes}
    <p class="suave">Fontes: folha de pagamento no ${i ? ext(i.fonte, "Portal da Transparência") : "Portal da Transparência"}; emendas na ${e ? ext(e.documento, "lei do orçamento aprovada") : "lei do orçamento"}; cópias e combustível nos relatórios ${ext("https://www.camara-americana.sp.gov.br/Download/Listar/46", "Gastos com Gabinete")}.</p>`;
}

// ------------------------------------------------------------------ prefeito
// O prefeito aparece junto com os vereadores (lista, ficha em abas, gastos), com os dados que valem para ele.
const SIT_PREF = { aprovado: ["Aprovados", "sim"], tramitando: ["Ainda em votação", "neutro"], retirado: ["Retirados pelo prefeito", ""], rejeitado: ["Rejeitados ou arquivados", "nao"] };
const ABAS_PREF = [["gastos", "Gastos"], ["propostas", "Projetos"], ["vetos", "Vetos"], ["votos", "Votos"]];
const ICONE_PREF = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 21h18M5 21V10M19 21V10M9 21v-6h6v6M2 10l10-6 10 6"/></svg>`;
let P = null;
async function carregarPrefeito() {
  if (P) return P;
  try { P = await carregar("prefeito.json"); } catch (e) { P = null; }
  return P;
}
const nomePref = () => (P && P.cadastro && P.cadastro.nome) || "Prefeito";
const mesesTce = () => Object.keys((P && P.tce) || {}).sort();

function cartaoPrefeitoLista() {
  if (!P) return "";
  const s = (P.cadastro || {}).subsidio;
  return `<h2>Prefeito</h2>
    <ul class="lista-ver lista-pref"><li><a href="#/prefeito">
      <span class="foto-icone">${ICONE_PREF}</span>
      <span class="corpo">
        <span class="linha-nome"><span class="nome">${$(nomePref())}</span> <span class="partido">Prefeito</span></span>
        <span class="principal"><b>${num(P.projetos.length)}</b> projetos enviados à Câmara</span>
        <span class="extra">${num(P.vetos.length)} vetos${s ? ` · Salário fixado em lei: ${reais(s.prefeito)}` : ""}</span>
      </span>
      <svg class="seta" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 6l6 6-6 6"/></svg>
    </a></li></ul>`;
}

function cartaoPrefeitoGastos() {
  if (!P) return "";
  const s = (P.cadastro || {}).subsidio, o = (P.orcamento_gabinete || []).slice(-1)[0];
  const ult = mesesTce().slice(-1)[0], t = ult ? P.tce[ult] : null;
  return `<div class="comp">
      <div class="comp-cab"><span class="foto-icone pequena">${ICONE_PREF}</span>
        <div><a class="comp-nome" href="#/prefeito">${$(nomePref())}</a><span class="comp-partido">Prefeito</span></div></div>
      <div class="comp-grade comp-dinheiro">
        <a class="comp-num" href="#/prefeito?aba=gastos"><b>${s ? reais(s.prefeito) : "—"}</b><span>Salário mensal fixado em lei (subsídio)</span></a>
        <a class="comp-num" href="#/prefeito?aba=gastos"><b>${o ? reais(o.valor) : "—"}</b><span>Orçamento do Gabinete do Prefeito em ${o ? o.ano : ""}</span></a>
        <a class="comp-num" href="#/prefeito?aba=gastos"><b>${t ? reais(t.totais.pago) : "—"}</b><span>Pago por toda a Prefeitura em ${t ? nomeMesNum(ult) : ""}</span></a>
      </div>
      <p class="comp-mais"><a href="#/prefeito?aba=gastos">Ver quem mais recebeu e outros meses</a></p>
    </div>`;
}

const MESES_NUM = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const nomeMesNum = (k) => `${MESES_NUM[Number(k.slice(5)) - 1]}/${k.slice(0, 4)}`;

function secaoTce(k) {
  const t = P.tce[k];
  if (!t) return `<div class="aviso">Sem dados desse mês no TCE-SP.</div>`;
  const pf = t.pessoas_fisicas || {};
  return `<div class="numeros dois">
      <div class="numero"><b>${reais(t.totais.pago)}</b><span>pago pela Prefeitura em ${nomeMesNum(k)}</span><small>${ext(t.fonte, "Conferir no TCE-SP")}</small></div>
      <div class="numero"><b>${reais(t.totais.empenhado)}</b><span>empenhado (dinheiro reservado para gastar)</span></div>
      <div class="numero"><b>${reais(t.totais.liquidado)}</b><span>liquidado (serviço ou compra entregue)</span></div>
    </div>
    <h3>Quem mais recebeu da Prefeitura em ${nomeMesNum(k)}</h3>
    <table class="tabela-pagos"><thead><tr><th>Empresa ou órgão (CNPJ)</th><th>Pago</th></tr></thead><tbody>
    ${t.maiores_pagos.map((x) => `<tr><td>${$(x.nome)}<div class="meta">CNPJ ${$(x.cnpj)}</div></td><td>${reais(x.valor)}</td></tr>`).join("")}
    </tbody></table>
    <div class="aviso">${num(t.recebedores_cnpj)} empresas e órgãos receberam pagamentos no mês; aqui estão os ${t.maiores_pagos.length} maiores. ${pf.pagamentos ? `Pagamentos a pessoas físicas (${num(pf.pagamentos)} lançamentos, ${reais(pf.valor)}) entram só no total.` : ""} A folha de salários aparece como pagamentos à própria Prefeitura, ao INSS e ao instituto de previdência.</div>`;
}

function seletorTce(mes) {
  const ms = mesesTce();
  if (!ms.length) return `<div class="aviso">As despesas da Prefeitura ainda não foram coletadas no TCE-SP.</div>`;
  const k = ms.includes(mes) ? mes : ms[ms.length - 1];
  return `<label class="seletor">Mês <select id="mes-tce">${ms.slice().reverse().map((m) => `<option value="${m}"${m === k ? " selected" : ""}>${nomeMesNum(m)}</option>`).join("")}</select></label>
    <div id="painel-tce">${secaoTce(k)}</div>`;
}

function itemProjetoPref(p) {
  const [, cls] = SIT_PREF[p.grupo] || ["", ""];
  return `<li><span class="tag ${cls}">${$(p.situacao)}</span> ${ext(SISCAM_DOC(p.id), $(p.ident))}
    <div>${$(p.assunto).slice(0, 260)}${p.assunto.length > 260 ? "…" : ""}</div>
    <div class="meta">Chegou à Câmara em ${data(p.data)}</div></li>`;
}

async function telaPrefeito(aba, mes) {
  await carregarPrefeito();
  if (!P) return `<h1>Prefeito</h1><p>Os dados do prefeito ainda não foram coletados.</p>`;
  if (!ABAS_PREF.some(([k]) => k === aba)) aba = "gastos";
  const cad = P.cadastro || {}, s = cad.subsidio, o = (P.orcamento_gabinete || []).slice(-1)[0];
  const c = P.contagem || {};
  const total = P.projetos.length;
  const nomeVer = (sl) => { const v = vereador(sl); return v ? v.apelido : sl; };
  const vetos = P.vetos.map((x) => `<li><span class="tag ${/derrubou/.test(x.explica) ? "sim" : /não foi votado/.test(x.explica) ? "neutro" : "nao"}">${$(x.explica)}</span> ${ext(SISCAM_DOC(x.id), $(x.ident))}
      <div>${$(x.assunto).slice(0, 260)}${x.assunto.length > 260 ? "…" : ""}</div>
      <div class="meta">Projeto de ${x.autores.map(([n, sl]) => sl ? `<a href="#/v/${sl}">${$(nomeVer(sl))}</a>` : $(n)).join(", ")} · apresentado em ${data(x.data)} · Situação no sistema da Câmara: ${$(x.situacao)}</div></li>`).join("");
  const derrubados = P.vetos.filter((x) => /derrubou/.test(x.explica)).length;
  const mantidos = P.vetos.filter((x) => /manteve/.test(x.explica)).length;
  const pend = P.vetos.length - derrubados - mantidos;
  const votacoes = P.votacoes.map((x) => {
    const partes = Object.entries(x.votos).sort((a, b) => b[1] - a[1]).map(([k, n]) => `${$(k)}: ${num(n)}`).join(" · ");
    return `<li><span class="tag ${x.resultado === "Aprovado" ? "sim" : x.resultado ? "nao" : ""}">${$(x.resultado || "Resultado não informado")}</span> ${ext(x.url, $(x.materia))}
      <div>${$(x.assunto).slice(0, 220)}${x.assunto.length > 220 ? "…" : ""}</div>
      <div class="meta">${data(x.data)}${x.fase && x.fase !== "Não informado" ? " · " + $(x.fase) : ""} · ${partes}${x.contra.length ? " · Votaram contra: " + x.contra.map($).join(", ") : ""} · ${ext(x.sessao_url, "sessão")}</div></li>`;
  }).join("");
  const linhasVer = R.vereadores.map((v) => {
    const k = P.por_vereador[v.slug] || {};
    return `<tr><th><a href="#/v/${v.slug}?aba=votos">${$(v.apelido)}</a></th><td>${num(k["A favor"] || 0)}</td><td>${num(k["Contra"] || 0)}</td><td>${num(k["Ausente"] || 0)}</td><td>${num(k["Não vota"] || 0)}</td></tr>`;
  }).join("");
  const pv = P.periodo_votos;
  const grupoCartao = (g) => {
    const [rot] = SIT_PREF[g];
    return `<div class="numero"><b>${num(c[g] || 0)}</b><span>${rot}</span></div>`;
  };
  return `<a class="voltar" href="#/">← Prefeito e vereadores</a>
    <div class="cabeca-ver"><span class="foto-icone grande">${ICONE_PREF}</span>
      <div><h1>${$(nomePref())}</h1><p class="suave">${$(cad.cargo || "Prefeito")} · Mandato ${$(cad.mandato || "")}</p></div></div>
    <div class="caixa suave">O prefeito não é vereador: ele não vota nem tem presença nas sessões. Aqui estão o salário e os gastos, os projetos que ele mandou para a Câmara, o que ele vetou e como os vereadores votaram nas matérias dele.${cad.fonte_nome ? `<br>Nome conforme ${ext(cad.fonte_nome, $(cad.fonte_nome_texto || "documento oficial"))}.` : ""}</div>

    <div class="abas" role="tablist">
      ${ABAS_PREF.map(([k, t]) => `<button role="tab" data-aba="${k}" aria-selected="${k === aba}">${t}</button>`).join("")}
    </div>

    <section class="painel" data-painel="gastos"${aba === "gastos" ? "" : " hidden"}>
    <h2>Anual</h2>
    <div class="numeros dois">
      ${s ? `<div class="numero"><b>${reais(s.prefeito)}</b><span>salário mensal do prefeito (subsídio fixado em lei)</span><small>${ext(s.pdf, $(s.lei))}</small></div>
      <div class="numero"><b>${reais(s.vice)}</b><span>salário mensal do vice-prefeito</span></div>
      <div class="numero"><b>${reais(s.secretarios)}</b><span>salário mensal de cada secretário municipal</span></div>` : ""}
      ${o ? `<div class="numero"><b>${reais(o.valor)}</b><span>orçamento do Gabinete do Prefeito em ${o.ano}</span><small>${ext(o.pdf, $(o.lei))}</small></div>` : ""}
    </div>
    ${s ? `<div class="aviso">${$(s.obs)}</div>` : ""}
    ${o && o.orgaos ? `<h3>Orçamento de cada secretaria e órgão em ${o.ano}</h3>
    <div class="aviso info">Valor <b>previsto</b> na lei do orçamento de ${o.ano} para cada secretaria e órgão do município, não o que já foi gasto. Total: ${reais(o.total)}. ${ext(o.pdf, "Ver a lei (PDF)")}</div>
    <div class="tabela-rolar"><table class="tabela-orc"><thead><tr><th>Secretaria ou órgão</th><th>Previsto</th><th>Parte</th></tr></thead><tbody>
    ${o.orgaos.map((g) => { const pct = (g.valor / o.total) * 100; return `<tr><td>${$(g.nome)}<i class="barra-orc" style="width:${Math.max(1, Math.round((g.valor / o.orgaos[0].valor) * 100))}%"></i></td><td>${reais(g.valor)}</td><td>${pct < 0.1 ? "menos de 0,1" : pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% do total</td></tr>`; }).join("")}
    </tbody></table></div>
    <div class="aviso">A Câmara Municipal, o DAE, a Guarda Municipal, a Fundação de Saúde e o Instituto de Previdência também aparecem porque estão na mesma lei, mas não são secretarias do prefeito.</div>` : ""}
    <h2>Mensal</h2>
    <div class="aviso info">Despesas de <b>toda a Prefeitura</b> (sem o DAE, a Guarda e os outros órgãos), como a própria Prefeitura informou ao Tribunal de Contas do Estado (TCE-SP). O sistema do TCE não separa o que é do Gabinete do Prefeito.</div>
    ${seletorTce(mes)}
    </section>

    <section class="painel" data-painel="propostas"${aba === "propostas" ? "" : " hidden"}>
    <h2>Projetos que o prefeito mandou para a Câmara</h2>
    <p>${num(total)} projetos desde ${data(R.inicio_mandato)}. ${ext(P.fonte_projetos, "Conferir na Câmara")}</p>
    <div class="numeros">${["aprovado", "tramitando", "retirado"].map(grupoCartao).join("")}${c.rejeitado ? grupoCartao("rejeitado") : ""}</div>
    <p class="suave">“Aprovado” segue a situação que o sistema da Câmara mostra hoje para cada projeto. Um projeto aprovado em primeira discussão ainda precisa da segunda.</p>
    <ul class="itens">${P.projetos.map(itemProjetoPref).join("")}</ul>
    </section>

    <section class="painel" data-painel="vetos"${aba === "vetos" ? "" : " hidden"}>
    <h2>Vetos</h2>
    <p>Quando a Câmara aprova um projeto, o prefeito pode sancionar (virar lei) ou vetar, no todo ou em parte. O veto volta para a Câmara, que decide se mantém ou derruba.</p>
    <div class="numeros">
      <div class="numero"><b>${num(P.vetos.length)}</b><span>projetos de vereadores com veto desde ${data(R.inicio_mandato)}</span></div>
      <div class="numero"><b>${num(mantidos)}</b><span>vetos mantidos pela Câmara</span></div>
      <div class="numero"><b>${num(derrubados)}</b><span>vetos derrubados pela Câmara</span></div>
      ${pend ? `<div class="numero"><b>${num(pend)}</b><span>ainda sem votação</span></div>` : ""}
    </div>
    <ul class="itens">${vetos}</ul>
    <div class="aviso">Esta lista vem da pesquisa oficial da Câmara pela situação “Veto” de cada projeto. Um projeto vetado cuja situação depois mudou no sistema (por exemplo, para arquivado) pode não aparecer aqui.</div>
    </section>

    <section class="painel" data-painel="votos"${aba === "votos" ? "" : " hidden"}>
    <h2>Como os vereadores votam nas matérias do prefeito</h2>
    ${pv ? `<p>${num(P.votacoes.length)} votações de projetos e vetos do prefeito nas sessões já coletadas (de ${data(pv[0])} a ${data(pv[1])}). Votar “a favor” de um veto quer dizer manter o veto.</p>` : ""}
    ${avisoSessoes()}
    <div class="tabela-rolar"><table class="tabela-votos"><thead><tr><th>Vereador</th><th>A favor</th><th>Contra</th><th>Ausente</th><th>Não vota</th></tr></thead><tbody>${linhasVer}</tbody></table></div>
    <p class="suave">“Não vota” costuma aparecer para quem preside a sessão, que pelo regimento só vota em alguns casos. “Ausente” é ausente no momento daquela votação.</p>
    <ul class="itens">${votacoes}</ul>
    </section>`;
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
      <li><b>Prefeito:</b> a pesquisa oficial de documentos do SISCAM, filtrada pelo autor “Poder Executivo de Americana” (projetos enviados) e pela situação “Veto” (projetos de vereadores vetados). Os votos vêm das mesmas páginas de sessão. O nome vem de um projeto assinado pelo Gabinete do Prefeito; o salário, da lei que fixou os subsídios (Projeto de Lei nº 27/2024); o orçamento do gabinete, da lei do orçamento.</li>
      <li><b>Despesas da Prefeitura:</b> a ${ext("https://transparencia.tce.sp.gov.br/apis", "API aberta do Tribunal de Contas do Estado (TCE-SP)")}, com o que a própria Prefeitura informa ao sistema Audesp, mês a mês. O Portal da Transparência da Prefeitura não aceita acesso automático de fora do Brasil, por isso usamos o TCE.</li>
      <li><b>Presença e votos:</b> a página de cada sessão no SISCAM, que traz a chamada nominal e o voto de cada vereador em cada votação.</li>
    </ul>
    <p>Um robô identificado como “AmericanaFiscaliza” baixa poucas páginas por vez, com pausa entre elas, para não pesar no sistema da Câmara. Se a Câmara pedir, ele para.</p>

    <h2 id="grupos">Como as propostas são separadas</h2>
    <p>A mesma regra vale para todos os vereadores. Ela olha o tipo do documento no sistema da Câmara e, em alguns casos, palavras do assunto:</p>
    <table>${R.regras.map(([g, r]) => `<tr><th>${$(g)}</th><td>${$(r)}</td></tr>`).join("")}</table>
    <p class="suave">Contamos só documentos com data dentro do mandato escolhido no topo da página (${$(R.mandato ? R.mandato.nome : "mandato atual")}: de ${data(R.inicio_mandato)} a ${data(R.fim_mandato)}). Documento com vários autores conta para cada um.</p>

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
    a.classList.toggle("ativo", alvo === (partes[0] || "") || (alvo === "" && (partes[0] === "v" || partes[0] === "prefeito")));
  });
  try {
    if (!R) {
      R = await carregar("resumo.json");
      if (!MANDATOS) {
        MANDATOS = R.mandatos || [{ id: "atual", nome: "Mandato atual" }];
        const escolhido = lerEscolha();
        MANDATO = MANDATOS.some((m) => m.id === escolhido) ? escolhido : MANDATOS[0].id;
        const sel = document.getElementById("mandato");
        sel.innerHTML = MANDATOS.map((m) => `<option value="${$(m.id)}"${m.id === MANDATO ? " selected" : ""}>${$(m.nome)}</option>`).join("");
        sel.onchange = () => { MANDATO = sel.value; guardarEscolha(MANDATO); R = null; rota(); };
        if (MANDATO !== MANDATOS[0].id) R = await carregar("resumo.json");
      }
    }
    await carregarPrefeito();
    let html;
    if (partes[0] === "v" && partes[2]) html = await telaGrupo(partes[1], partes[2]);
    else if (partes[0] === "v") html = await telaVereador(partes[1], new URLSearchParams(qs || "").get("aba"), new URLSearchParams(qs || "").get("mes"));
    else if (partes[0] === "busca") html = await telaBusca(new URLSearchParams(qs || "").get("q"));
    else if (partes[0] === "prefeito") html = await telaPrefeito(new URLSearchParams(qs || "").get("aba"), new URLSearchParams(qs || "").get("mes"));
    else if (partes[0] === "sessoes") html = telaSessoes();
    else if (partes[0] === "gastos") html = telaGastos();
    else if (partes[0] === "comparar") html = telaComparar();
    else if (partes[0] === "repetidos") html = await telaRepetidos();
    else if (partes[0] === "sobre") html = await telaSobre();
    else html = telaInicio();
    app.innerHTML = html;
    document.querySelectorAll(".abas button").forEach((t) => t.onclick = () => {
      document.querySelectorAll(".abas button").forEach((x) => x.setAttribute("aria-selected", x === t));
      document.querySelectorAll(".painel").forEach((p) => { p.hidden = p.dataset.painel !== t.dataset.aba; });
      history.replaceState(null, "", partes[0] === "prefeito" ? `#/prefeito?aba=${t.dataset.aba}` : `#/v/${partes[1]}?aba=${t.dataset.aba}`);
    });
    if (document.getElementById("lista-ver")) {
      ["f-nome", "f-partido", "f-ordem"].forEach((id) => document.getElementById(id).addEventListener("input", desenharLista));
      desenharLista();
    }
    const sel = document.getElementById("mes-gasto");
    if (sel) sel.onchange = async () => {
      const f = await carregar(`vereador-${partes[1]}.json`);
      document.getElementById("painel-mes").innerHTML = secaoMes(f, sel.value);
      history.replaceState(null, "", `#/v/${partes[1]}?aba=gastos&mes=${sel.value}`);
    };
    const selT = document.getElementById("mes-tce");
    if (selT) selT.onchange = () => {
      document.getElementById("painel-tce").innerHTML = secaoTce(selT.value);
      history.replaceState(null, "", `#/prefeito?aba=gastos&mes=${selT.value}`);
    };
    const b = document.getElementById("mais-votos");
    if (b) b.onclick = async () => { const f = await carregar(`vereador-${partes[1]}.json`); document.getElementById("votos").innerHTML = f.votos.slice().reverse().map(itemVoto).join(""); b.remove(); };
    const quando = new Date(R.gerado_em);
    document.getElementById("atualizado").textContent = `Dados atualizados em ${quando.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" })}.`;
    document.getElementById("atualizado-topo").textContent = `Atualizado: ${quando.toLocaleDateString("pt-BR", { timeZone: "America/Sao_Paulo" })}, ${quando.toLocaleTimeString("pt-BR", { timeZone: "America/Sao_Paulo", hour: "2-digit", minute: "2-digit" })}`;
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
