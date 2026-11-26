#!/usr/bin/env python3
"""Coleta leve das propostas (proposituras) de cada vereador.

1. Lê a lista de vereadores do site da Câmara (/Vereador) e abre o perfil de
   cada um (site institucional, sem restrição no robots.txt), para pegar o
   nome, partido, contato público do gabinete e o ID do autor no SISCAM.
2. Baixa UMA página por vereador no SISCAM (/Vereadores/Proposituras/<id>),
   com pausa longa entre os pedidos. Pula quem já foi baixado.

Regras combinadas: robô identificado (sem disfarce), pausa entre pedidos,
para tudo em 403/429 ou se existir dados/PARAR.

Uso: python3 -I coletar_proposituras.py [pasta_de_dados] [--renovar N]
Só usa a biblioteca padrão do Python.
"""
import html, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

SITE = "https://www.camara-americana.sp.gov.br"
SISCAM = "https://americana.siscam.com.br"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
PAUSA_SITE = 5
PAUSA_SISCAM = 30

# --renovar N: além de baixar quem falta, baixa de novo as N páginas mais antigas
# (assim cada execução atualiza só alguns vereadores, em rodízio).
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
RENOVAR = int(sys.argv[sys.argv.index("--renovar") + 1]) if "--renovar" in sys.argv else 0
if RENOVAR:
    ARGS = [a for a in ARGS if a != str(RENOVAR)]
PASTA = os.path.abspath(ARGS[0] if ARGS else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
PERFIS = os.path.join(PASTA, "perfis")
CSVS = os.path.join(PASTA, "proposituras_csv")
os.makedirs(CSVS, exist_ok=True)
ANO_INICIO = 2025  # mandato atual
EXPORTAR = ("/Documentos/Exportar?tipo=2&Pesquisa=Avancada&id=74&pagina=1&Modulo=DocumentosLista"
            "&DocumentosRelacionadosDetalhes=false&NoTexto=false&Documento=0&Numeracao=Documento"
            "&AnoInicial={ano}&AnoFinal={fim}&Situacao=0&TipoAutor=Vereador&AutoriaId={autor}&Iniciativa=Nenhum")
PROPS = os.path.join(PASTA, "proposituras_html")
PARAR = os.path.join(PASTA, "PARAR")
for p in (PERFIS, PROPS):
    os.makedirs(p, exist_ok=True)
ultimo = 0.0


def log(msg):
    linha = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} [proposituras] {msg}"
    print(linha, flush=True)
    with open(os.path.join(PASTA, "coleta.log"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def baixar(url, pausa):
    global ultimo
    if os.path.exists(PARAR):
        log("arquivo PARAR existe; parando sem pedir nada"); sys.exit(2)
    espera = ultimo + pausa - time.time()
    if espera > 0:
        time.sleep(espera)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            st, txt = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, txt = e.code, ""
        if e.code in (403, 429):
            open(PARAR, "w").write(f"{e.code} em {url} - {datetime.now().isoformat()}\n")
            log(f"PARADO: {e.code} em {url}"); sys.exit(2)
    ultimo = time.time()
    return st, txt


def limpar(x):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", x))).strip()


def chave(n):
    import unicodedata
    n = "".join(c for c in unicodedata.normalize("NFD", n) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z ]", "", n.lower()).strip()


def main():
    st, lista = baixar(SITE + "/Vereador", 0)
    log(f"lista de vereadores: HTTP {st}")
    slugs = sorted(set(re.findall(r'href="/vereadores/([a-z0-9-]+)"', lista)))
    vereadores = []
    for slug in slugs:
        m = re.search(r'href="/vereadores/' + slug + r'"><h4 class="color-link">(.*?)</h4>', lista)
        apelido = limpar(m.group(1)) if m else slug
        arq = os.path.join(PERFIS, slug + ".html")
        if os.path.exists(arq):
            txt = open(arq, encoding="utf-8").read()
        else:
            st, txt = baixar(f"{SITE}/vereadores/{slug}", PAUSA_SITE)
            log(f"perfil {slug}: HTTP {st}")
            if st != 200:
                continue
            open(arq, "w", encoding="utf-8").write(txt)
        sid = re.search(r"Vereadores/Proposituras/(\d+)", txt)
        nome = re.search(r'<h4 class="nome-ver">(.*?)</h4>', txt)
        nome = limpar(nome.group(1)) if nome else ""
        partido = re.search(r"\(([^()]+)\)\s*$", nome)
        tel = re.search(r"<strong>Telefone:</strong>\s*([^<]+)", txt)
        email = re.search(r"([\w.+-]+@camara-americana\.sp\.gov\.br)", txt)
        foto = re.search(r'<img src="(/Arquivos/Vereadores/[^"]+)"', txt)
        vereadores.append({
            "slug": slug, "apelido": apelido,
            "nome": re.sub(r"\s*\([^()]+\)\s*$", "", nome),
            "partido": partido.group(1).strip() if partido else "",
            "siscam_id": int(sid.group(1)) if sid else None,
            "telefone_gabinete": tel.group(1).strip() if tel else "",
            "email_gabinete": email.group(1) if email else "",
            "foto": SITE + foto.group(1) if foto else "",
            "perfil_url": f"{SITE}/vereadores/{slug}",
        })
    # Perfis sem o link para o SISCAM: o ID do autor vem da lista de autores
    # do formulário de pesquisa do SISCAM (mesmo número usado na página de propostas).
    # IDs já descobertos numa execução anterior (evita pedir a lista de autores de novo)
    arq_v = os.path.join(PASTA, "vereadores.json")
    antigos = {x["slug"]: x.get("siscam_id") for x in json.load(open(arq_v, encoding="utf-8"))} if os.path.exists(arq_v) else {}
    for v in vereadores:
        if not v["siscam_id"] and antigos.get(v["slug"]):
            v["siscam_id"] = antigos[v["slug"]]
            v["siscam_id_origem"] = "lista de autores do SISCAM"
    if any(not v["siscam_id"] for v in vereadores):
        st, idx = baixar(SISCAM + "/index/74", PAUSA_SISCAM)
        log(f"lista de autores do SISCAM: HTTP {st}")
        autores = {chave(limpar(n)): int(i) for i, n in re.findall(r'<option value="(\d+)"\s*>([^<]+)</option>', idx)}
        for v in vereadores:
            if not v["siscam_id"] and chave(v["apelido"]) in autores:
                v["siscam_id"] = autores[chave(v["apelido"])]
                v["siscam_id_origem"] = "lista de autores do SISCAM"
    json.dump(vereadores, open(os.path.join(PASTA, "vereadores.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"{len(vereadores)} vereadores; {sum(1 for v in vereadores if v['siscam_id'])} com ID no SISCAM")

    def guardado(v):  # (arquivo que já temos, data dele) — página completa ou CSV
        for pasta, ext in ((PROPS, "html"), (CSVS, "csv")):
            a = os.path.join(pasta, f"{v['siscam_id']}.{ext}")
            if os.path.exists(a) and os.path.getsize(a) > 1000:
                return a, os.path.getmtime(a)
        return None, 0

    # Rodízio guardado em arquivo (a data dos arquivos não serve: o checkout do git zera tudo).
    arq_r = os.path.join(PASTA, "rodizio.json")
    rod = json.load(open(arq_r)) if os.path.exists(arq_r) else {}
    fila = sorted((rod.get(str(v["siscam_id"]), ""), v["siscam_id"]) for v in vereadores if v["siscam_id"] and guardado(v)[0])
    renovar = {sid for _, sid in fila[:RENOVAR]}
    for sid in renovar:
        rod[str(sid)] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(rod, open(arq_r, "w"), indent=1, sort_keys=True)
    for v in vereadores:
        if not v["siscam_id"]:
            continue
        arq = os.path.join(PROPS, f"{v['siscam_id']}.html")
        tem, _ = guardado(v)
        if tem and v["siscam_id"] not in renovar:
            continue
        if tem and tem.endswith(".csv"):
            # Já sabemos que a página completa não abre (504): renova direto pelo CSV,
            # sem forçar o servidor da Câmara de novo.
            st, txt = baixar(SISCAM + EXPORTAR.format(autor=v["siscam_id"], ano=ANO_INICIO, fim=datetime.now().year), PAUSA_SISCAM)
            log(f"exportação CSV {v['apelido']} ({v['siscam_id']}): HTTP {st}, {len(txt)//1024} KB")
            if st == 200 and txt.lstrip("﻿").startswith("Documento;"):
                open(tem, "w", encoding="utf-8").write(txt)
            continue
        st, txt = baixar(f"{SISCAM}/Vereadores/Proposituras/{v['siscam_id']}", PAUSA_SISCAM)
        log(f"proposituras {v['apelido']} ({v['siscam_id']}): HTTP {st}, {len(txt)//1024} KB")
        if st == 200:
            open(arq, "w", encoding="utf-8").write(txt)
        elif not os.path.exists(arq):
            # Página grande demais: o servidor da Câmara estoura o tempo (504).
            # Plano B: a exportação CSV oficial da pesquisa, só do mandato atual.
            # Ela traz os 8 tipos principais (indicações, moções, requerimentos e
            # projetos), não traz emendas nem pareceres. O site marca isso.
            st, txt = baixar(SISCAM + EXPORTAR.format(autor=v["siscam_id"], ano=ANO_INICIO, fim=datetime.now().year), PAUSA_SISCAM)
            log(f"exportação CSV {v['apelido']} ({v['siscam_id']}): HTTP {st}, {len(txt)//1024} KB")
            if st == 200 and txt.lstrip("\ufeff").startswith("Documento;"):
                open(os.path.join(CSVS, f"{v['siscam_id']}.csv"), "w", encoding="utf-8").write(txt)
    log("fim")


if __name__ == "__main__":
    main()
