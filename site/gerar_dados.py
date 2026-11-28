#!/usr/bin/env python3
"""Gera os arquivos JSON do site a partir do HTML oficial já baixado.

Entradas (pasta do coletor):
  dados/vereadores.json             lista de vereadores (do site da Câmara)
  dados/proposituras_html/<id>.html  página de propostas de cada vereador (SISCAM)
  dados/html/<id>.html               páginas de sessão (SISCAM)
Saídas em publico/dados/:
  resumo.json, vereador-<slug>.json, pedidos.json, verificacao.json, prefeito.json

Nada aqui inventa número: tudo é contagem direta do que está nas páginas
oficiais. As regras de grupo estão em CLASSIFICACAO_REGRAS e são as mesmas
para todos os vereadores.
Uso: python3 -I gerar_dados.py [pasta_do_coletor]
"""
import html, json, os, re, sys, unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone

AQUI = os.path.dirname(os.path.abspath(__file__))
COLETOR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(AQUI, "..", "coletor"))
DADOS = os.path.join(COLETOR, "dados")
SAIDA = os.path.join(AQUI, "publico", "dados")
os.makedirs(SAIDA, exist_ok=True)
SISCAM = "https://americana.siscam.com.br"
# Mandatos que o site conhece. O primeiro é o atual e vai em dados/; um mandato antigo,
# quando for coletado, iria em dados/<id>/ com a mesma estrutura.
MANDATOS = [{"id": "2025-2028", "nome": "Mandato 2025–2028", "inicio": "2025-01-01", "fim": "2028-12-31"}]
MANDATO = MANDATOS[0]
INICIO_MANDATO = MANDATO["inicio"]  # mesma janela para todos
FIM_MANDATO = MANDATO["fim"]


def limpar(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", x))).strip()


def sem_acento(x):
    return "".join(c for c in unicodedata.normalize("NFD", x) if unicodedata.category(c) != "Mn").lower()


def iso(d):  # dd/mm/aaaa -> aaaa-mm-dd
    p = d.split("/")
    return f"{p[2]}-{p[1]}-{p[0]}" if len(p) == 3 else ""


# ---------------------------------------------------------------- grupos
GRUPOS = {
    "bairro": "Pedidos de melhoria nos bairros",
    "cobranca": "Perguntas e cobranças",
    "homenagem": "Homenagens",
    "lei": "Propostas de lei",
    "outros": "Outros documentos",
}
HOMENAGEM_RE = re.compile(
    r"aplauso|congratula|parab[eé]ns|pesar|falecimento|louvor|reconhecimento|homenag|"
    r"t[ií]tulo de cidad|cidad[aã]o (honor|american)|medalha|diploma|comenda|pr[eê]mio|honraria|"
    r"denomina(?!d[oa])|d[aá] (o )?nome|calend[aá]rio|institui (o|a) (dia|semana|m[eê]s)|"
    r"voto de (pesar|aplauso|congratula)|minuto de sil[eê]ncio", re.I)
COBRANCA_MOCAO_RE = re.compile(r"apelo|rep[uú]dio|protesto|reivindica|solicita|apoio", re.I)
TIPOS_LEI = {"Projetos de Lei", "Projetos de Emenda à Lei Orgânica", "Projetos de Resolução",
             "Projetos de Decreto Legislativo", "Projetos de Lei Complementar", "Emendas", "Substitutivos",
             "Subemendas"}
CLASSIFICACAO_REGRAS = [
    ["Pedidos de melhoria nos bairros", "Todas as Indicações. A indicação é o pedido do vereador para a Prefeitura (ou o DAE) fazer algo: tapar buraco, podar árvore, trocar lâmpada etc."],
    ["Perguntas e cobranças", "Requerimentos e Pedidos de Informação (o vereador pergunta ou cobra a Prefeitura e outros órgãos), e Moções de apelo, repúdio, protesto ou apoio."],
    ["Homenagens", "Moções de aplauso, congratulação ou pesar; e qualquer documento (moção, requerimento ou projeto) cujo assunto fale em título de cidadão, medalha, prêmio, diploma, nome de rua ou de prédio público (denominação), data comemorativa ou calendário oficial."],
    ["Propostas de lei", "Projetos de Lei, Projetos de Lei Complementar, de Resolução, de Decreto Legislativo e de Emenda à Lei Orgânica, Emendas e Substitutivos, quando não forem homenagem."],
    ["Outros documentos", "Todo o resto que aparece no nome do vereador no sistema da Câmara e não é proposta nova: pareceres de comissão, atos e autógrafos da Mesa Diretora (para quem é da Mesa), atas, pedidos de retirada e de vista, anexos, documentos administrativos do gabinete, relatórios do painel e as leis já aprovadas (a lei aprovada aparece aqui e o projeto dela aparece também em Propostas de lei)."],
]


def classificar(tipo, assunto):
    if tipo == "Indicações":
        return "bairro"
    if HOMENAGEM_RE.search(assunto) and (tipo in ("Moções", "Requerimentos") or tipo in TIPOS_LEI):
        return "homenagem"
    if tipo in ("Requerimentos", "Pedidos de Informação"):
        return "cobranca"
    if tipo == "Moções":
        return "cobranca" if COBRANCA_MOCAO_RE.search(assunto) else "outros"
    if tipo in TIPOS_LEI:
        return "lei"
    return "outros"


# ---------------------------------------------------------- pedidos de bairro
ASSUNTOS_PEDIDO = [
    ("Buraco e asfalto", r"buraco|asf[aá]lt|recape|pavimenta|cascalh|guia|sarjeta|cal[cç]ada|passeio"),
    ("Árvores e poda", r"poda|[aá]rvore|galho|erradica"),
    ("Iluminação", r"l[aâ]mpada|ilumina|poste|luminária|reator"),
    ("Água e esgoto", r"vazamento|esgoto|cavalete|hidr[oô]metro|dae|bueiro|galeria|boca de lobo|[aá]gua"),
    ("Limpeza e mato", r"limpeza|ro[cç]ad|mato|capina|entulho|lixo|varri[cç]|cata.?bagulho|terreno"),
    ("Trânsito e sinalização", r"sinaliza|faixa|lombada|redutor|sem[aá]foro|placa|estaciona|tr[aâ]nsito|radar|pintura"),
    ("Pragas e animais", r"dedetiza|desratiza|escorpi|dengue|mosquito|animal|c[aã]es|pombo"),
    ("Ônibus e pontos", r"[oô]nibus|abrigo|ponto de [oô]nibus|transporte"),
]
LOGRADOURO = r"(?:Rua|R\.|Avenida|Av\.|Pra[cç]a|Estrada|Alameda|Travessa|Rodovia|Viela|Largo|Passagem|Via|Marginal)"


def extrair_local(assunto):
    """Rua e bairro do texto da indicação. É leitura automática do texto: pode errar."""
    t = assunto.strip().rstrip(".")
    bairro = ""
    m = re.search(r"\s[–—-]\s+([^–—-]+)$", t)
    if m:
        bairro = m.group(1).strip()
        if len(bairro) > 60 or re.search(r"\d{2,}", bairro):
            bairro = ""
    if not bairro:
        BAIRRO_TIPO = r"(?:Vila|Jardim|Jd\.?|Parque|Pq\.?|Ch[aá]cara|Residencial|Res\.|Conjunto|Cidade|N[uú]cleo)"
        m = (re.search(r"\bbairros?\s+(?:d[oa]s?\s+)?([A-ZÀ-Ú][^,.;()]+)", t)
             or re.search(r"\b(?:na|no|da|do)\s+(?:regi[aã]o\s+d[oa]\s+)?(" + BAIRRO_TIPO + r"\s+[^,.;()]+)", t)
             or re.search(r",\s*(" + BAIRRO_TIPO + r"\s+[^,.;()]+)$", t))
        if m:
            bairro = re.split(r"\s+(?:em frente|defronte|pr[oó]ximo|junto|entre|onde|que|para|pois|devido|e\s+no)\b", m.group(1).strip())[0].strip()
            if len(bairro) > 50:
                bairro = ""
    rua = ""
    m = re.search(LOGRADOURO + r"\s+([^,–—\-(]+?)(?=\s*(?:,|\s[–—-]\s|\(|\bn[º°o]\.?\s*\d|\s\d|\besquina\b|\bdefronte\b|\bpr[oó]ximo\b|\bentre\b|\bjunto\b|\baltura\b|$))", t, re.I)
    if m:
        tipo_l = re.match(LOGRADOURO, m.group(0), re.I).group(0)
        tipo_l = {"r.": "Rua", "av.": "Avenida"}.get(tipo_l.lower(), tipo_l.capitalize())
        rua = f"{tipo_l} {m.group(1).strip()}"
    return rua, bairro


def assunto_pedido(assunto):
    a = assunto.lower()
    for nome, rx in ASSUNTOS_PEDIDO:
        if re.search(rx, a):
            return nome
    return "Outros pedidos"


# ------------------------------------------------------------ proposituras
def ler_proposituras(caminho):
    s = open(caminho, encoding="utf-8").read()
    docs, cabecalhos = [], {}
    for blk in re.split(r"<h3>", s)[1:]:
        cab = re.match(r"(.*?)\s*\((\d+)\)\s*</h3>", blk, re.S)
        if not cab:
            continue
        tipo = limpar(cab.group(1))
        cabecalhos[tipo] = int(cab.group(2))
        for m in re.finditer(r'<a href="/(Documentos|Sessoes)/Documento/(\d+)"[^>]*title="([^"]*)"[^>]*>.*?</a>\s*-\s*(\d\d/\d\d/\d{4})\s*-\s*(.*?)</p>', blk, re.S):
            docs.append({"id": int(m.group(2)) if m.group(1) == "Documentos" else "s" + m.group(2),
                         "tipo": tipo, "ident": limpar(m.group(3)),
                         "data": iso(m.group(4)), "assunto": limpar(m.group(5))})
    return docs, cabecalhos


TIPO_CSV = {  # nome no CSV -> (nome no plural, como na página do vereador; código do tipo na pesquisa)
    "Indicação": ("Indicações", 125), "Moção": ("Moções", 126), "Requerimento": ("Requerimentos", 124),
    "Projeto de Lei": ("Projetos de Lei", 119), "Projeto de Lei Complementar": ("Projetos de Lei Complementar", 120),
    "Projeto de Decreto Legislativo": ("Projetos de Decreto Legislativo", 121),
    "Projeto de Emenda à Lei Orgânica": ("Projetos de Emenda à Lei Orgânica", 123),
    "Projeto de Resolução": ("Projetos de Resolução", 122),
}


def ler_csv_exportado(caminho):
    """Plano B: exportação CSV oficial da pesquisa do SISCAM (só os 8 tipos principais)."""
    import csv
    docs = []
    for r in csv.DictReader(open(caminho, encoding="utf-8-sig"), delimiter=";"):
        plural, cod = TIPO_CSV.get(r["Documento"], (r["Documento"], 0))
        docs.append({"id": f"p{cod}-{r['Numero']}-{r['Ano']}", "tipo": plural,
                     "ident": f"{r['Documento']} Nº {r['Numero']}/{r['Ano']}",
                     "data": iso(r["Data"].strip()), "assunto": re.sub(r"\s+", " ", r["Ementa"]).strip()})
    return docs


# ---------------------------------------------------------------- gabinete
ITENS_GABINETE = [  # (rótulo no PDF, nome no site, unidade, chave do limite)
    (r"Corresp\w*ncias\s*\(unidade\)", "Correspondências", "unidades", "corresp"),
    (r"Impress\w*es/Fotoc\w*pias", "Impressões e cópias", "unidades", "impress"),
    (r"Tele\w*fonia Fixa", "Telefone fixo", "minutos", "fixa"),
    (r"Tele\w*fonia M\w*vel", "Telefone celular", "minutos", "m[oó]vel"),
    (r"Combust\w*vel", "Combustível", "litros", "combust"),
]


def historico_sessoes_completo():
    """O coletor de sessões marca proxima_antiga = 0 quando chega antes do início do mandato."""
    arq = os.path.join(DADOS, "estado.json")
    return os.path.exists(arq) and json.load(open(arq, encoding="utf-8")).get("proxima_antiga") == 0


def numero_br(t):
    t = t.strip()
    if t in ("", "-"):
        return 0.0
    if "," in t:
        return float(t.replace(".", "").replace(",", "."))
    return float(t.replace(".", "")) if re.fullmatch(r"\d{1,3}(\.\d{3})+", t) else float(t)


def ler_gabinete(txt):
    """Totais do ano como impressos no PDF (coluna Total). Não somamos mês a mês:
    as colunas dos meses vazios somem na extração e confundiriam os meses."""
    titulo = re.search(r"RELAT\S* DESPESAS GABINETE\s*-\s*(\d{4})", txt)
    nome = re.search(r"VEREADORA?\s+(.+)", txt)
    linhas = txt.splitlines()
    itens = []
    lim_txt = txt.split("LIMITE MENSAL", 1)[1] if "LIMITE MENSAL" in txt else ""
    cab = next((l for l in linhas if "Janeiro" in l and "Dezembro" in l), "")
    for rx, rot, uni, chave_lim in ITENS_GABINETE:
        linha = next((l for l in linhas if re.match(r"\s*" + rx, l, re.I) and "=" not in l), None)
        if linha is None:
            continue
        total = linha.split()[-1]
        lim = re.search(r"(?im)^.*" + chave_lim + r".*=\s*([\d.]+)", lim_txt)
        tot = numero_br(total) if re.fullmatch(r"[\d.,-]+", total) else 0.0
        itens.append({"item": rot, "unidade": uni, "total": tot,
                      "limite_mensal": numero_br(lim.group(1)) if lim else None,
                      "meses": gabinete_por_mes(cab, linha, rx, tot)})
    return {"ano": titulo.group(1) if titulo else "", "nome_pdf": nome.group(1).strip() if nome else "", "itens": itens}


MESES_CAB = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def gabinete_por_mes(cab, linha, rx, total):
    """Põe cada número da linha no mês cujo título está mais perto (pela coluna no texto
    do PDF). Só aceita se a soma dos meses bater com o Total impresso; senão devolve None."""
    if not cab:
        return None
    centros = [(m.start() + m.end()) / 2 for m in (re.search(r"\b" + n + r"\b", cab) for n in MESES_CAB) if m]
    if len(centros) != 12:
        return None
    ini = re.match(r"\s*" + rx + r"\S*", linha, re.I).end()
    nums = [(m.start(), m.end(), m.group()) for m in re.finditer(r"\d[\d.,]*", linha[ini:])]
    if not nums:
        return [0.0] * 12 if total == 0 else None
    nums = nums[:-1]  # o último é a coluna Total
    meses = [0.0] * 12
    for a, b, t in nums:
        c = ini + (a + b) / 2
        i = min(range(12), key=lambda k: abs(centros[k] - c))
        meses[i] += numero_br(t)
    return [round(x, 2) for x in meses]


# ---------------------------------------------------------------- emendas impositivas
RUIDO_PDF = re.compile(r"DOCUMENTO ASSINADO POR|consulta\.siscam|Página \d+ de \d+|Avenida Monsenhor Bruno Nardini|www\.camara-americana|"
                       r"Câmara Municipal de Americana|Estado de São Paulo|Autógrafo nº|Projeto de Lei nº|ANEXO ESPECIAL|Lei Orçamentária Anual|conforme Art\.", re.I)


def ler_emendas(txt):
    """Cada bloco 'EMENDA nº N' do Anexo Especial de Emendas Individuais Impositivas."""
    ini = txt.find("ANEXO ESPECIAL DE EMENDAS INDIVIDUAIS IMPOSITIVAS")
    if ini < 0:
        return []
    corpo = "\n".join(l for l in txt[ini:].splitlines() if not RUIDO_PDF.search(l))
    out = []
    for blk in re.split(r"\n\s*EMENDA n[ºo°]\s*", corpo)[1:]:
        num = re.match(r"(\d+)", blk)
        ver = re.search(r"Vereadora?:\s*(.+)", blk)
        sec = re.search(r"Secretaria Executora:\s*(.+)", blk)
        val = re.search(r"Valor:\s*R\$\s*([\d.]+,\d{2})", blk)
        cota = "saúde" if re.search(r"Cota Sa[úu]de:\s*\[\s*_*X_*\s*\]", blk, re.I) else ("geral" if re.search(r"Cota geral:\s*\[\s*_*X_*\s*\]", blk, re.I) else "")
        dest = re.search(r"Emenda:\s*(.*)", blk, re.S)
        destino = re.sub(r"\s+", " ", dest.group(1)).strip().strip("“”\" ") if dest else ""
        destino = re.split(r"\s+(?:Plenário|Sala das Sessões|[A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{12,}\s+(?:Presidente|Secretário))", destino)[0].strip().strip("“”\" ")
        if num and ver and val:
            out.append({"numero": int(num.group(1)), "vereador": ver.group(1).strip(), "secretaria": sec.group(1).strip() if sec else "",
                        "cota": cota, "valor": numero_br(val.group(1)), "destino": destino})
    return out


# ---------------------------------------------------------------- sessões
def ler_sessao(sid, s):
    s = html.unescape(s)
    t = re.search(r'<h3 class="page-header">(.*?)</h3>', s, re.S)
    titulo = limpar(t.group(1)).replace("Sessões - ", "") if t else ""
    d = re.search(r"Data:</strong>\s*([\d/]+)", s) or re.search(r"(\d\d/\d\d/\d{4})", titulo)
    sessao = {"id": sid, "titulo": titulo, "data": iso(d.group(1)) if d else "",
              "url": f"{SISCAM}/Sessoes/Sessao/{sid}", "chamadas": [], "votacoes": []}
    ini, fim = s.find("Frequências</strong>"), s.find("Votações</strong>")
    if ini >= 0:
        for blk in s[ini:fim if fim > ini else len(s)].split("<h4>")[1:]:
            ch = {"nome": limpar(blk.split("</h4>")[0]), "presentes": [], "ausentes": []}
            for cat, nomes in re.findall(r"<strong>(Presentes|Ausentes)[^<]*</strong>\s*-\s*([^<]*)", blk):
                ch["presentes" if cat == "Presentes" else "ausentes"] += [n.strip() for n in nomes.split(",") if n.strip()]
            sessao["chamadas"].append(ch)
    if fim >= 0:
        for blk in s[fim:].split('class="data-list-item')[1:]:
            mat = re.search(r'<strong>\s*<a href="(/Documentos/Documento/(\d+))">([^<]+)</a>', blk)
            if not mat:
                continue

            def campo(k):
                m = re.search(r"<strong>" + k + r":</strong>(.*?)</p>", blk, re.S)
                return limpar(m.group(1)) if m else ""
            votos = {}
            for cat, nomes in re.findall(r"<strong>([^<(:]+?)\s*\(\d+\)</strong>\s*-\s*([^<]*)", blk):
                for n in nomes.split(","):
                    if n.strip():
                        votos[n.strip()] = cat.strip()
            res = campo("Resultado")
            sessao["votacoes"].append({
                "materia": limpar(mat.group(3)), "url": SISCAM + mat.group(1), "fase": campo("Fase"),
                "autoria": campo("Autoria"), "assunto": campo("Assunto"), "quorum": campo("Quórum"),
                "tipo": campo("Votação"), "resultado": res if res.strip(". ") else "", "votos": votos})
    return sessao


def chave_nome(n):
    return re.sub(r"[^a-z ]", "", sem_acento(n)).strip()


# ---------------------------------------------------------------- prefeito
EXECUTIVO = "PODER EXECUTIVO DE AMERICANA"  # nome do autor no SISCAM
# O que cada situação de veto quer dizer, em linguagem simples (a situação oficial aparece junto)
VETO_EXPLICA = [
    ("rejeitado", "A Câmara derrubou o veto"),
    ("tramit", "O veto ainda não foi votado pela Câmara"),
    ("parcial acatado", "A Câmara manteve o veto a uma parte do projeto"),
    ("subst", "A Câmara manteve o veto ao texto substitutivo"),
    ("acatado", "A Câmara manteve o veto"),
]


def grupo_situacao(sit):
    s = sem_acento(sit)
    if s.startswith("aprovado"):
        return "aprovado"
    if "retirad" in s:
        return "retirado"
    if "arquiv" in s or "rejeitad" in s:
        return "rejeitado"
    return "tramitando"


def gerar_prefeito(sessoes, mapa, vereadores, checar, verif):
    """prefeito.json: projetos que o Executivo mandou, vetos e votos dos vereadores neles."""
    import csv
    pasta = os.path.join(DADOS, "prefeito")
    arq = os.path.join(pasta, "projetos-executivo.csv")
    if not os.path.exists(arq):
        return None
    estado = json.load(open(os.path.join(pasta, "estado.json"))) if os.path.exists(os.path.join(pasta, "estado.json")) else {}
    projetos = []
    for r in csv.DictReader(open(arq, encoding="utf-8-sig"), delimiter=";"):
        plural, cod = TIPO_CSV.get(r["Documento"], (r["Documento"], 0))
        d = iso(r["Data"].strip())
        if not (INICIO_MANDATO <= d <= FIM_MANDATO):
            continue
        projetos.append({"id": f"p{cod}-{r['Numero']}-{r['Ano']}", "ident": f"{r['Documento']} Nº {r['Numero']}/{r['Ano']}",
                         "data": d, "assunto": re.sub(r"\s+", " ", r["Ementa"]).strip(),
                         "situacao": r["Situação"].strip(), "grupo": grupo_situacao(r["Situação"])})
    projetos.sort(key=lambda x: (x["data"], x["id"]), reverse=True)
    checar(all(EXECUTIVO in r["Autoria"].upper()
               for r in csv.DictReader(open(arq, encoding="utf-8-sig"), delimiter=";")),
           f"Prefeito: os {len(projetos)} projetos da planilha do SISCAM são todos de autoria do {EXECUTIVO.title()}")

    por_apelido = {chave_nome(v["apelido"]): v["slug"] for v in vereadores}
    vetos, vistos = [], set()
    for nome in sorted(os.listdir(pasta)):
        if not (nome.startswith("vetos-") and nome.endswith(".csv")):
            continue
        for r in csv.DictReader(open(os.path.join(pasta, nome), encoding="utf-8-sig"), delimiter=";"):
            plural, cod = TIPO_CSV.get(r["Documento"], (r["Documento"], 0))
            pid = f"p{cod}-{r['Numero']}-{r['Ano']}"
            d = iso(r["Data"].strip())
            if pid in vistos or not (INICIO_MANDATO <= d <= FIM_MANDATO):
                continue
            vistos.add(pid)
            autores = [a.strip() for a in r["Autoria"].split(",") if a.strip()]
            sit = r["Situação"].strip()
            explica = next((t for k, t in VETO_EXPLICA if k in sem_acento(sit)), "")
            vetos.append({"id": pid, "ident": f"{r['Documento']} Nº {r['Numero']}/{r['Ano']}", "data": d,
                          "assunto": re.sub(r"\s+", " ", r["Ementa"]).strip(), "situacao": sit, "explica": explica,
                          "autores": [[a, por_apelido.get(chave_nome(a), "")] for a in autores]})
    vetos.sort(key=lambda x: (x["data"], x["id"]), reverse=True)
    soltos = sorted({a for x in vetos for a, sl in x["autores"] if not sl})
    if soltos:
        verif["avisos"].append(f"Prefeito: autores de projetos vetados que não são vereadores atuais: {', '.join(soltos)}.")
    checar(all(x["explica"] for x in vetos), f"Prefeito: as {len(vetos)} situações de veto têm explicação")

    # votações de matérias do Executivo nas sessões já coletadas
    votacoes = []
    conta = {v["slug"]: Counter() for v in vereadores}
    for s in sessoes:
        for vt in s["votacoes"]:
            if EXECUTIVO not in vt["autoria"].upper():
                continue
            por_voto = Counter(vt["votos"].values())
            votacoes.append({"data": s["data"], "materia": vt["materia"], "url": vt["url"], "fase": vt["fase"],
                             "assunto": vt["assunto"], "resultado": vt["resultado"], "veto": vt["materia"].startswith("Veto"),
                             "votos": dict(por_voto), "contra": sorted(n for n, x in vt["votos"].items() if x == "Contra"),
                             "sessao_url": s["url"], "titulo_sessao": s["titulo"]})
            for v in vereadores:
                voto = next((x for n, x in vt["votos"].items() if mapa.get(n) == v["slug"]), "sem registro")
                conta[v["slug"]][voto] += 1
    votacoes.reverse()
    checar(all(sum(c.values()) == len(votacoes) for c in conta.values()),
           f"Prefeito: cada vereador tem um registro em cada uma das {len(votacoes)} votações de matérias do Executivo")
    cad_arq = os.path.join(pasta, "cadastro.json")
    cadastro = json.load(open(cad_arq, encoding="utf-8")) if os.path.exists(cad_arq) else {}
    # orçamento do Gabinete do Prefeito na LOA (mesmo texto já baixado para as emendas)
    orcamento = []
    pasta_e = os.path.join(DADOS, "emendas")
    fontes_e = json.load(open(os.path.join(pasta_e, "fontes.json"), encoding="utf-8")) if os.path.exists(os.path.join(pasta_e, "fontes.json")) else {}
    for ano, f in sorted(fontes_e.items()):
        a = os.path.join(pasta_e, f"loa{ano}.txt")
        txt = open(a, encoding="utf-8").read() if os.path.exists(a) else ""
        m = re.search(r"\d\d\s*[–-]\s*Gabinete do Prefeito\s+R\$\s*([\d.]+,\d\d)", txt)
        if m:
            orcamento.append({"ano": int(ano), "valor": numero_br(m.group(1)), "lei": f["lei"], "pdf": f["pdf"]})
        # quadro "POR ÓRGÃOS DA ADMINISTRAÇÃO": orçamento de cada secretaria e órgão
        ini = txt.find("POR ÓRGÃOS DA ADMINISTRAÇÃO")
        fim = txt.find("TOTAL GERAL", ini)
        if ini >= 0 and fim > ini:
            orgaos = [{"codigo": c, "nome": re.sub(r"\s+", " ", n).strip(), "valor": numero_br(v)}
                      for c, n, v in re.findall(r"^\s*(\d\d)\s*[–-]\s*(.+?)\s*R\$\s*([\d.]+,\d\d)\s*$", txt[ini:fim], re.M)]
            tg = re.search(r"TOTAL GERAL\s+R\$\s*([\d.]+,\d\d)", txt[fim:])
            total = numero_br(tg.group(1)) if tg else 0
            ok = abs(sum(o["valor"] for o in orgaos) - total) < 0.01
            checar(ok, f"LOA {ano}: a soma do orçamento dos {len(orgaos)} órgãos e secretarias é igual ao total geral da lei")
            if orcamento and orcamento[-1]["ano"] == int(ano):
                orcamento[-1]["orgaos"] = sorted(orgaos, key=lambda o: -o["valor"])
                orcamento[-1]["total"] = total
    checar(bool(orcamento), "Prefeito: orçamento do Gabinete do Prefeito lido na lei do orçamento")
    # despesas da Prefeitura informadas ao TCE-SP (resumo mensal)
    pasta_t = os.path.join(DADOS, "prefeitura")
    tce = {}
    if os.path.isdir(pasta_t):
        for nome in sorted(os.listdir(pasta_t)):
            if nome.startswith("tce-") and nome.endswith(".json"):
                t = json.load(open(os.path.join(pasta_t, nome), encoding="utf-8"))
                tce[f"{t['ano']}-{t['mes']:02d}"] = t
    checar(all(t["totais"]["pago"] >= sum(x["valor"] for x in t["maiores_pagos"]) - 0.01 for t in tce.values()),
           f"Prefeitura (TCE-SP): em cada um dos {len(tce)} meses, a soma dos maiores recebedores não passa do total pago")
    # folha da Prefeitura (planilhas do portal importadas à mão: importar_folha_prefeitura.py)
    pasta_f = os.path.join(DADOS, "prefeitura", "folha")
    folha_pref = {}
    if os.path.isdir(pasta_f):
        for nome in sorted(os.listdir(pasta_f)):
            if nome.startswith("folha-") and nome.endswith(".json"):
                f = json.load(open(os.path.join(pasta_f, nome), encoding="utf-8"))
                folha_pref[f"{f['ano']}-{f['mes']:02d}"] = f
    if folha_pref:
        sub = (cadastro.get("subsidio") or {}).get("prefeito")
        checar(all(f["prefeito"] for f in folha_pref.values()),
               f"Folha da Prefeitura: o prefeito aparece em todos os {len(folha_pref)} meses importados")
        checar(not sub or all(f["prefeito"] and f["prefeito"]["vencimentos"] <= sub + 0.01 for f in folha_pref.values()),
               "Folha da Prefeitura: o vencimento do prefeito não passa do subsídio fixado em lei em nenhum mês")
        for k, f in sorted(folha_pref.items()):
            if sub and f["prefeito"] and abs(f["prefeito"]["vencimentos"] - sub) >= 0.01:
                verif["avisos"].append(f"Folha da Prefeitura {k}: vencimento do prefeito R$ {f['prefeito']['vencimentos']:.2f}, diferente do subsídio fixado em lei.")
    # despesas por secretaria (planilhas do portal: importar_despesas_prefeitura.py), ligadas ao orçamento pelo nome
    pasta_d = os.path.join(DADOS, "prefeitura", "despesas")
    despesas = {}
    norm = lambda t: unicodedata.normalize("NFD", t.split("/")[0]).encode("ascii", "ignore").decode().lower().strip()
    if os.path.isdir(pasta_d):
        for nome in sorted(os.listdir(pasta_d)):
            if not (nome.startswith("despesas-") and nome.endswith(".json")):
                continue
            d = json.load(open(os.path.join(pasta_d, nome), encoding="utf-8"))
            orc = next((o for o in orcamento if str(o["ano"]) == str(d["ano"]) and o.get("orgaos")), None)
            nomes_loa = {norm(g["nome"]): g for g in (orc or {}).get("orgaos", [])}
            for u in d["unidades"]:
                n = norm(u["nome"])
                g = next((g for k, g in nomes_loa.items() if k.startswith(n) or n.startswith(k)), None)
                u["nome_lei"] = g["nome"] if g else None
                u["previsto"] = g["valor"] if g else None
            if orc:
                checar(all(u["nome_lei"] for u in d["unidades"]),
                       f"Despesas {d['ano']}: as {len(d['unidades'])} secretarias do portal foram ligadas ao orçamento da lei pelo nome")
            checar(all(abs(sum(m[k] for m in u["por_mes"].values()) - u[k]) < 0.05 for u in d["unidades"] for k in ("empenhado", "pago")),
                   f"Despesas {d['ano']}: a soma dos meses bate com o total de cada secretaria")
            checar(all(u["pago"] >= sum(x["valor"] for x in u["maiores_pagos"]) - 0.01 for u in d["unidades"]),
                   f"Despesas {d['ano']}: em cada secretaria, a soma das empresas que mais receberam não passa do total pago")
            despesas[str(d["ano"])] = d
    return {
        "cadastro": cadastro, "orcamento_gabinete": orcamento, "tce": tce, "folha": folha_pref, "despesas": despesas,
        "autor_siscam": EXECUTIVO, "coletado_em": estado.get("coletado_em", ""),
        "fonte_projetos": f"{SISCAM}/Documentos/Pesquisa?Pesquisa=Avancada&id=74&pagina=1&Modulo=DocumentosLista&DocumentosRelacionadosDetalhes=false&NoTexto=false&Documento=0&Numeracao=Documento&AnoInicial={INICIO_MANDATO[:4]}&Situacao=0&TipoAutor=Prefeito&AutoriaId=29&Iniciativa=Nenhum",
        "projetos": projetos, "contagem": dict(Counter(p["grupo"] for p in projetos)),
        "vetos": vetos, "votacoes": votacoes,
        "por_vereador": {sl: dict(c) for sl, c in conta.items()},
        "periodo_votos": [sessoes[0]["data"], sessoes[-1]["data"]] if sessoes else None,
    }


def main():
    vereadores = json.load(open(os.path.join(DADOS, "vereadores.json"), encoding="utf-8"))
    pasta_s = os.path.join(DADOS, "html")
    sessoes = [ler_sessao(int(f.split(".")[0]), open(os.path.join(pasta_s, f), encoding="utf-8").read())
               for f in sorted(os.listdir(pasta_s), key=lambda x: int(x.split(".")[0]))]
    sessoes = sorted((x for x in sessoes if INICIO_MANDATO <= x["data"] <= FIM_MANDATO), key=lambda x: (x["data"], str(x["id"])))
    verif = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"), "checagens": [], "avisos": []}

    def checar(ok, texto):
        verif["checagens"].append({"ok": bool(ok), "texto": texto})

    # nomes usados nas sessões (apelido em maiúsculas) -> slug
    nomes_sessao = set()
    for s in sessoes:
        for c in s["chamadas"]:
            nomes_sessao |= set(c["presentes"]) | set(c["ausentes"])
        for v in s["votacoes"]:
            nomes_sessao |= set(v["votos"])
    mapa = {}
    for v in vereadores:
        alvo = chave_nome(v["apelido"])
        for n in nomes_sessao:
            if chave_nome(n) == alvo:
                mapa[n] = v["slug"]
    sem_par = sorted(n for n in nomes_sessao if n not in mapa)
    for n in sem_par:  # tentativa por sobrenome/parte do nome, registrada como aviso
        partes = set(chave_nome(n).split()) - {"dr", "da", "de", "do", "dos", "professora", "pastor"}
        cands = [v for v in vereadores if partes & set(chave_nome(v["apelido"] + " " + v["nome"]).split())]
        if len(cands) == 1:
            mapa[n] = cands[0]["slug"]
            verif["avisos"].append(f"O nome “{n}” das sessões foi ligado a {cands[0]['apelido']} por parte do nome. Conferir.")
    checar(all(n in mapa for n in nomes_sessao), f"Todos os {len(nomes_sessao)} nomes que aparecem nas sessões foram ligados a um vereador da lista oficial" +
           ("" if all(n in mapa for n in nomes_sessao) else f" (faltam: {', '.join(n for n in nomes_sessao if n not in mapa)})"))

    # ---------------- propostas
    todos_pedidos = {}
    por_slug = {}
    for v in vereadores:
        caminho = os.path.join(DADOS, "proposituras_html", f"{v['siscam_id']}.html")
        caminho_csv = os.path.join(DADOS, "proposituras_csv", f"{v['siscam_id']}.csv")
        parcial = False
        if v.get("siscam_id") and os.path.exists(caminho):
            docs, cab = ler_proposituras(caminho)
            cont = Counter(d["tipo"] for d in docs)
            bate = all(cont[t] == n for t, n in cab.items())
            checar(bate, f"{v['apelido']}: a quantidade de documentos lida em cada tipo bate com o total que a própria página da Câmara mostra ({sum(cab.values())} no total, todos os anos)")
        elif v.get("siscam_id") and os.path.exists(caminho_csv):
            docs, parcial = ler_csv_exportado(caminho_csv), True
            verif["avisos"].append(f"{v['apelido']}: a página completa de propostas não abriu (o servidor da Câmara estourou o tempo). Usamos a exportação oficial da pesquisa, que traz indicações, moções, requerimentos e projetos, mas não emendas, pedidos de informação, pareceres e outros documentos.")
        else:
            por_slug[v["slug"]] = None
            verif["avisos"].append(f"Propostas de {v['apelido']} ainda não foram baixadas.")
            continue
        mand = [d for d in docs if INICIO_MANDATO <= d["data"] <= FIM_MANDATO]
        for d in mand:
            d["grupo"] = classificar(d["tipo"], d["assunto"])
            if d["grupo"] == "bairro":
                chave_ind = re.sub(r"\D+", "-", d["ident"]).strip("-")  # número/ano: igual nas duas fontes
                p = todos_pedidos.setdefault(chave_ind, {**{k: d[k] for k in ("id", "ident", "data", "assunto")}, "autores": []})
                if isinstance(d["id"], int):
                    p["id"] = d["id"]
                p["autores"].append(v["slug"])
        por_slug[v["slug"]] = {"docs": mand, "total_todos_anos": None if parcial else len(docs), "parcial": parcial,
                               "primeiro": min((d["data"] for d in docs), default="")}

    # ---------------- gabinete (consumo em unidades, PDFs do site da Câmara)
    gab_por_slug = {}
    pasta_g = os.path.join(DADOS, "gabinete")
    if os.path.exists(os.path.join(pasta_g, "indice.json")):
        ind = json.load(open(os.path.join(pasta_g, "indice.json"), encoding="utf-8"))
        for a in ind["arquivos"]:
            g = ler_gabinete(open(os.path.join(pasta_g, a["texto"]), encoding="utf-8").read())
            palavras = set(chave_nome(a["nome_na_lista"] + " " + g["nome_pdf"].replace(".", " ")).split()) - {"da", "de", "do", "dos", "pr", "prof", "dr", "vereador", "vereadora"}
            cands = [v for v in vereadores if palavras & (set(chave_nome(v["apelido"] + " " + v["nome"]).split()) - {"da", "de", "do", "dos", "dr"})]
            if len(cands) != 1:
                cands = [v for v in cands if palavras <= set(chave_nome(v["apelido"] + " " + v["nome"]).split())] or cands
            if len(cands) == 1 and cands[0]["slug"] not in gab_por_slug:
                gab_por_slug[cands[0]["slug"]] = {**g, "pdf": a["pdf"], "fonte": ind["fonte"], "criado_em": a["criado_em"]}
            else:
                verif["avisos"].append(f"Relatório de gabinete “{a['nome_na_lista']}” não foi ligado a um único vereador.")
        checar(len(gab_por_slug) == len(vereadores), f"Relatórios de gastos de gabinete ligados a {len(gab_por_slug)} de {len(vereadores)} vereadores")
        checar(all(i["meses"] is not None for g in gab_por_slug.values() for i in g["itens"]),
               "Gastos de gabinete mês a mês: todas as linhas dos relatórios foram lidas")
        for slug_, g in gab_por_slug.items():
            for i in g["itens"]:
                if i["meses"] is not None and abs(sum(i["meses"]) - i["total"]) >= 0.01:
                    i["soma_difere"] = True
                    verif["avisos"].append(f"Gabinete {slug_}: em {i['item']}, a soma dos meses ({sum(i['meses']):.2f}) não bate com o Total impresso no PDF ({i['total']:.2f}). O site mostra os dois.")
        checar(all(len(g["itens"]) == len(ITENS_GABINETE) for g in gab_por_slug.values()), "Todos os relatórios de gabinete têm as 5 linhas esperadas (correspondências, cópias, telefone fixo, celular, combustível)")

    # ---------------- folha por mês (Portal da Transparência): vereador e equipe do gabinete
    folha_por_slug, folha_info, folha_meses, meses_folha, sem_pag = {}, None, {}, [], {}
    vazio = {"da", "de", "do", "dos", "das", "e", "dr", "pr", "vereador", "vereadora", "gabinete"}

    def toks(x):
        return set(chave_nome(x).split()) - vazio

    def achar(texto, campo):
        t = toks(texto)
        pont = sorted(((len(t & toks(campo(v))), v["slug"]) for v in vereadores), reverse=True)
        if pont[0][0] >= 1 and pont[0][0] > pont[1][0]:
            return pont[0][1]
        return None

    def ler_folha(F):
        fs_mes, nao_ligados, fracas = {}, [], []
        for x in F["linhas"]:
            reg = {"nome": x["NomeServidor"].strip(), "cargo": x["Cargo"].strip().capitalize(),
                   "bruto": numero_br(x["ValorBruto"] or "0"), "liquido": numero_br(x["ValorLiquido"] or "0"),
                   "admissao": (x.get("DataAdmissao") or "")[:10]}
            lot = (x["DescrLotacao"] or "").strip()
            if x["Cargo"].strip().upper() == "VEREADOR":
                slug = achar(reg["nome"], lambda v: v["nome"] + " " + v["apelido"])
                papel = "vereador"
            elif re.match(r"GABINETE (VEREADOR|VEREADORA|[A-Z])", lot) and "PRESID" not in lot:
                slug = achar(re.sub(r"^GABINETE\s+(VEREADORA?\s+)?", "", lot), lambda v: v["apelido"] + " " + v["nome"])
                papel = "equipe"
            else:
                nao_ligados.append(f"{lot} ({reg['cargo']})")
                continue
            if not slug:
                nao_ligados.append(f"{lot or reg['nome']} ({reg['cargo']})")
                continue
            d = fs_mes.setdefault(slug, {"vereador": None, "equipe": []})
            if papel == "vereador":
                if d["vereador"]:  # dois pagamentos no mesmo mês (ex.: 13º): soma
                    d["vereador"] = {**d["vereador"], "bruto": round(d["vereador"]["bruto"] + reg["bruto"], 2),
                                     "liquido": round(d["vereador"]["liquido"] + reg["liquido"], 2)}
                else:
                    d["vereador"] = reg
                v_ = next(v for v in vereadores if v["slug"] == slug)
                if len(toks(reg["nome"]) & toks(v_["nome"] + " " + v_["apelido"])) < 2:
                    d["vereador"]["ligacao_fraca"] = True
                    fracas.append(f"“{reg['nome']}” (cargo vereador) foi ligado a {v_['apelido']} só por uma parte do nome")
            else:
                d["equipe"].append(reg)
        for d in fs_mes.values():
            d["equipe"].sort(key=lambda r: -r["bruto"])
            d["total_equipe"] = round(sum(r["bruto"] for r in d["equipe"]), 2)
        return fs_mes, sorted(set(nao_ligados)), sorted(set(fracas))

    pasta_p = os.path.join(DADOS, "portal")
    arqs_f = sorted(f for f in os.listdir(pasta_p) if re.fullmatch(r"folha-\d{4}-\d{2}\.json", f)) if os.path.isdir(pasta_p) else []
    arqs_f = [a for a in arqs_f if INICIO_MANDATO[:7] <= a[6:13] <= FIM_MANDATO[:7]]
    for i, nome_arq in enumerate(arqs_f):
        F = json.load(open(os.path.join(pasta_p, nome_arq), encoding="utf-8"))
        chave = nome_arq[6:13]
        fs_mes, nao_ligados, fracas = ler_folha(F)
        for slug, d in fs_mes.items():
            folha_meses.setdefault(slug, {})[chave] = d
        meses_folha.append(chave)
        ultimo = i == len(arqs_f) - 1
        rot = f"{F['mes'].lower()}/{F['ano']}"
        sem_subsidio = [v["apelido"] for v in vereadores if not (fs_mes.get(v["slug"]) or {}).get("vereador")]
        if ultimo:
            folha_por_slug = fs_mes
            folha_info = {k: F[k] for k in ("fonte", "ano", "mes", "coletado_em")}
            for t in fracas:
                verif["avisos"].append(f"Folha: {t}. Conferir.")
            if nao_ligados:
                verif["avisos"].append(f"Folha de {rot}: linhas de gabinete que não ligamos a nenhum vereador: {'; '.join(nao_ligados)}.")
            checar(len([1 for d in fs_mes.values() if d["equipe"]]) == len(vereadores),
                   f"Folha de {rot}: equipe de gabinete encontrada para {len([1 for d in fs_mes.values() if d['equipe']])} de {len(vereadores)} vereadores")
        for nome_v in sem_subsidio:
            sem_pag.setdefault(nome_v, []).append(chave)
    for nome_v, ms in sem_pag.items():
        verif["avisos"].append(f"Folha: não encontramos o pagamento de {nome_v} como vereador em {len(ms)} de {len(meses_folha)} meses ({ms[0]} a {ms[-1]}). O site mostra “não encontrado”, sem adivinhar.")
    if meses_folha:
        esperado = []
        a_, m_ = int(meses_folha[0][:4]), int(meses_folha[0][5:])
        while f"{a_}-{m_:02d}" <= meses_folha[-1]:
            esperado.append(f"{a_}-{m_:02d}"); a_, m_ = (a_, m_ + 1) if m_ < 12 else (a_ + 1, 1)
        checar(meses_folha == esperado and meses_folha[0] == INICIO_MANDATO[:7],
               f"Folha mês a mês sem buracos de {meses_folha[0]} a {meses_folha[-1]} ({len(meses_folha)} meses)")

    # ---------------- emendas impositivas (Anexo Especial da LOA aprovada)
    emendas_por_slug, emendas_info = {}, []
    arq_e = os.path.join(DADOS, "emendas", "fontes.json")
    if os.path.exists(arq_e):
        for ano, info in sorted(json.load(open(arq_e, encoding="utf-8")).items()):
            txt = os.path.join(DADOS, "emendas", f"loa{ano}.txt")
            if not os.path.exists(txt) or not info.get("emendas", True):
                continue
            lista = ler_emendas(open(txt, encoding="utf-8").read())
            emendas_info.append({"ano": ano, **info, "quantidade": len(lista)})
            soltas = []
            for e in lista:
                t = set(chave_nome(e["vereador"]).split()) - {"da", "de", "do", "dr"}
                cands = [v for v in vereadores if t and t <= set(chave_nome(v["apelido"] + " " + v["nome"]).split())]
                if len(cands) != 1:
                    soltas.append(e["vereador"]); continue
                emendas_por_slug.setdefault(cands[0]["slug"], {}).setdefault(ano, []).append({**e, "vereador": cands[0]["apelido"]})
            if soltas:
                verif["avisos"].append(f"Emendas da LOA {ano} sem vereador identificado: {', '.join(soltas)}.")
            totais = {round(sum(x["valor"] for x in d.get(ano, [])), 2) for d in emendas_por_slug.values()}
            com = sum(1 for d in emendas_por_slug.values() if d.get(ano))
            checar(not soltas and com == len(vereadores), f"LOA {ano}: {len(lista)} emendas impositivas lidas, todas ligadas a um vereador ({com} de {len(vereadores)} vereadores)")
            checar(len(totais) == 1, f"LOA {ano}: a soma das emendas é a mesma para todos os vereadores ({', '.join('R$ ' + f'{x:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.') for x in sorted(totais))})")

    # ---------------- presença e votos
    resumo_v = []
    sessoes_pub = []
    for s in sessoes:
        sessoes_pub.append({"id": s["id"], "titulo": s["titulo"], "data": s["data"], "url": s["url"],
                            "chamadas": [c["nome"] for c in s["chamadas"]], "votacoes": len(s["votacoes"])})
        for c in s["chamadas"]:
            checar(len(c["presentes"]) + len(c["ausentes"]) == len(vereadores),
                   f"{s['titulo']}, {c['nome']}: presentes + ausentes = {len(c['presentes']) + len(c['ausentes'])} (a Câmara tem {len(vereadores)} vereadores)")
        for vt in s["votacoes"]:
            if len(vt["votos"]) != len(vereadores):
                verif["avisos"].append(f"{s['titulo']}, {vt['materia']}: a lista de votos tem {len(vt['votos'])} nomes, não {len(vereadores)}.")

    for v in vereadores:
        slug = v["slug"]
        pres = []
        for s in sessoes:
            for c in s["chamadas"]:
                sit = None
                for n in c["presentes"]:
                    if mapa.get(n) == slug: sit = "presente"
                for n in c["ausentes"]:
                    if mapa.get(n) == slug: sit = "ausente"
                pres.append({"sessao": s["id"], "titulo": s["titulo"], "data": s["data"], "chamada": c["nome"],
                             "situacao": sit or "sem registro", "url": s["url"]})
        votos = []
        for s in sessoes:
            for vt in s["votacoes"]:
                voto = next((val for n, val in vt["votos"].items() if mapa.get(n) == slug), None)
                votos.append({"sessao": s["id"], "data": s["data"], "titulo_sessao": s["titulo"], "materia": vt["materia"],
                              "url": vt["url"], "fase": vt["fase"], "autoria": vt["autoria"], "assunto": vt["assunto"],
                              "resultado": vt["resultado"], "voto": voto or "sem registro", "sessao_url": s["url"]})
        p = por_slug[slug]
        grupos = {g: [] for g in GRUPOS}
        if p:
            for d in sorted(p["docs"], key=lambda x: (x["data"], str(x["id"])), reverse=True):
                grupos[d["grupo"]].append([d["id"], d["data"], d["tipo"], d["ident"], d["assunto"]])
        ficha = {**v, "propostas_baixadas": p is not None, "propostas_parcial": bool(p and p["parcial"]),
                 "total_todos_anos": p["total_todos_anos"] if p else None,
                 "grupos": grupos, "presenca": pres, "votos": votos, "gabinete": gab_por_slug.get(slug),
                 "folha": folha_por_slug.get(slug), "folha_info": folha_info,
                 "folha_meses": folha_meses.get(slug, {}),
                 "emendas": emendas_por_slug.get(slug, {}), "emendas_info": emendas_info,
                 "fonte_propostas": f"{SISCAM}/Vereadores/Proposituras/{v['siscam_id']}"}
        json.dump(ficha, open(os.path.join(SAIDA, f"vereador-{slug}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        resumo_v.append({k: v[k] for k in ("slug", "apelido", "nome", "partido", "foto", "perfil_url", "telefone_gabinete", "email_gabinete", "siscam_id")} | {
            "propostas_baixadas": p is not None, "propostas_parcial": bool(p and p["parcial"]),
            "grupos": {g: len(l) for g, l in grupos.items()},
            "chamadas": len(pres), "presente": sum(1 for x in pres if x["situacao"] == "presente"),
            "ausente": sum(1 for x in pres if x["situacao"] == "ausente"),
            "votos_contra": sum(1 for x in votos if x["voto"] == "Contra"), "votacoes": len(votos),
            "fonte_propostas": ficha["fonte_propostas"],
            "dinheiro": {
                "salario": ((folha_por_slug.get(slug) or {}).get("vereador") or {}).get("bruto"),
                "equipe_pessoas": len((folha_por_slug.get(slug) or {}).get("equipe", [])),
                "equipe_total": (folha_por_slug.get(slug) or {}).get("total_equipe", 0),
                "emendas": {ano: round(sum(e["valor"] for e in l), 2) for ano, l in emendas_por_slug.get(slug, {}).items()},
                "copias": next((i["total"] for i in (gab_por_slug.get(slug) or {}).get("itens", []) if i["item"].startswith("Impress")), None),
                "combustivel": next((i["total"] for i in (gab_por_slug.get(slug) or {}).get("itens", []) if i["item"].startswith("Combust")), None),
            }})

    # ---------------- pedidos de bairro (base da busca)
    slugs = [v["slug"] for v in vereadores]
    pedidos, nao_local = [], 0
    for p in sorted(todos_pedidos.values(), key=lambda x: (x["data"], str(x["id"]))):
        rua, bairro = extrair_local(p["assunto"])
        if not rua and not bairro:
            nao_local += 1
        pedidos.append([p["id"], p["data"], p["ident"].replace("Indicação ", ""), p["assunto"], rua, bairro,
                        assunto_pedido(p["assunto"]), [slugs.index(a) for a in p["autores"]]])
    verif["avisos"].append(f"Em {nao_local} de {len(pedidos)} pedidos de bairro o programa não conseguiu ler a rua nem o bairro no texto; eles continuam aparecendo na busca por palavra.")

    prefeito = gerar_prefeito(sessoes, mapa, vereadores, checar, verif)
    if prefeito:
        json.dump(prefeito, open(os.path.join(SAIDA, "prefeito.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    sessoes_lista = [s["id"] for s in sessoes]
    resumo = {
        "gerado_em": verif["gerado_em"], "inicio_mandato": INICIO_MANDATO, "fim_mandato": FIM_MANDATO,
        "sessoes_completas": historico_sessoes_completo(),
        "mandato": MANDATO, "mandatos": MANDATOS,
        "grupos": GRUPOS, "regras": CLASSIFICACAO_REGRAS, "assuntos_pedido": [a for a, _ in ASSUNTOS_PEDIDO] + ["Outros pedidos"],
        "vereadores": sorted(resumo_v, key=lambda x: sem_acento(x["apelido"])),
        "slugs": slugs, "sessoes": sessoes_pub, "folha_info": folha_info, "meses_folha": meses_folha,
        "pago_total": {"vereadores": round(sum((d["vereador"] or {}).get("bruto", 0) for ms in folha_meses.values() for d in ms.values()), 2),
                       "equipes": round(sum(d["total_equipe"] for ms in folha_meses.values() for d in ms.values()), 2),
                       "de": meses_folha[0] if meses_folha else "", "ate": meses_folha[-1] if meses_folha else ""}, "emendas_info": emendas_info,
        "gabinete_ano": next((g["ano"] for g in gab_por_slug.values()), ""),
        "periodo_sessoes": [sessoes[0]["data"], sessoes[-1]["data"]] if sessoes else None,
        "propostas_completas": all(por_slug.values()),
        "total_pedidos": len(pedidos),
        "ultima_proposta": max((d["data"] for p in por_slug.values() if p for d in p["docs"]), default=""),
    }
    json.dump(resumo, open(os.path.join(SAIDA, "resumo.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(pedidos, open(os.path.join(SAIDA, "pedidos.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    # "O problema que não some": mesmo assunto pedido várias vezes para a mesma rua (mesma chave da busca do site)
    grupos_rep = {}
    for x in pedidos:
        if x[4]:
            grupos_rep.setdefault((re.sub(r"\s+", " ", sem_acento(x[4])).strip(), x[6]), []).append(x)
    reps = sorted((g for g in grupos_rep.values() if len(g) >= 2), key=lambda g: (-len(g), g[0][4]))
    json.dump({"total_casos": len(reps), "casos_5_ou_mais": sum(1 for g in reps if len(g) >= 5),
               "casos": [{"rua": g[0][4], "bairro": next((x[5] for x in g if x[5]), ""), "assunto": g[0][6],
                          "vereadores": len({i for x in g for i in x[7]}), "primeiro": min(x[1] for x in g), "ultimo": max(x[1] for x in g),
                          "pedidos": sorted(g, key=lambda x: x[1], reverse=True)} for g in reps[:50]]},
              open(os.path.join(SAIDA, "repetidos.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(verif, open(os.path.join(SAIDA, "verificacao.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(c["ok"] for c in verif["checagens"])
    print(f"{len(vereadores)} vereadores, {len(sessoes)} sessões, {len(pedidos)} pedidos de bairro; checagens {ok}/{len(verif['checagens'])} ok")
    for a in verif["avisos"]:
        print("AVISO:", a)
    for c in verif["checagens"]:
        if not c["ok"]:
            print("FALHOU:", c["texto"])
    return 0 if ok == len(verif["checagens"]) else 1


if __name__ == "__main__":
    sys.exit(main())
