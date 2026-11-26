#!/usr/bin/env python3
"""Gera os arquivos JSON do site a partir do HTML oficial já baixado.

Entradas (pasta do coletor):
  dados/vereadores.json             lista de vereadores (do site da Câmara)
  dados/proposituras_html/<id>.html  página de propostas de cada vereador (SISCAM)
  dados/html/<id>.html               páginas de sessão (SISCAM)
Saídas em publico/dados/:
  resumo.json, vereador-<slug>.json, pedidos.json, verificacao.json

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
INICIO_MANDATO = "2025-01-01"  # mesma janela para todos: mandato atual (2025-2028)


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


def main():
    vereadores = json.load(open(os.path.join(DADOS, "vereadores.json"), encoding="utf-8"))
    pasta_s = os.path.join(DADOS, "html")
    sessoes = [ler_sessao(int(f.split(".")[0]), open(os.path.join(pasta_s, f), encoding="utf-8").read())
               for f in sorted(os.listdir(pasta_s), key=lambda x: int(x.split(".")[0]))]
    sessoes.sort(key=lambda x: (x["data"], str(x["id"])))
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
        mand = [d for d in docs if d["data"] >= INICIO_MANDATO]
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
                 "grupos": grupos, "presenca": pres, "votos": votos,
                 "fonte_propostas": f"{SISCAM}/Vereadores/Proposituras/{v['siscam_id']}"}
        json.dump(ficha, open(os.path.join(SAIDA, f"vereador-{slug}.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
        resumo_v.append({k: v[k] for k in ("slug", "apelido", "nome", "partido", "foto", "perfil_url", "telefone_gabinete", "email_gabinete", "siscam_id")} | {
            "propostas_baixadas": p is not None, "propostas_parcial": bool(p and p["parcial"]),
            "grupos": {g: len(l) for g, l in grupos.items()},
            "chamadas": len(pres), "presente": sum(1 for x in pres if x["situacao"] == "presente"),
            "ausente": sum(1 for x in pres if x["situacao"] == "ausente"),
            "fonte_propostas": ficha["fonte_propostas"]})

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

    sessoes_lista = [s["id"] for s in sessoes]
    resumo = {
        "gerado_em": verif["gerado_em"], "inicio_mandato": INICIO_MANDATO,
        "grupos": GRUPOS, "regras": CLASSIFICACAO_REGRAS, "assuntos_pedido": [a for a, _ in ASSUNTOS_PEDIDO] + ["Outros pedidos"],
        "vereadores": sorted(resumo_v, key=lambda x: sem_acento(x["apelido"])),
        "slugs": slugs, "sessoes": sessoes_pub,
        "periodo_sessoes": [sessoes[0]["data"], sessoes[-1]["data"]] if sessoes else None,
        "propostas_completas": all(por_slug.values()),
        "total_pedidos": len(pedidos),
        "ultima_proposta": max((d["data"] for p in por_slug.values() if p for d in p["docs"]), default=""),
    }
    json.dump(resumo, open(os.path.join(SAIDA, "resumo.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    json.dump(pedidos, open(os.path.join(SAIDA, "pedidos.json"), "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
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
