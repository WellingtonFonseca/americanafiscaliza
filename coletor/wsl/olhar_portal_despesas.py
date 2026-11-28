#!/usr/bin/env python3
"""Passo 1 das despesas (rodar no computador do Wellington, internet do Brasil):
abre o Mapa do Site do Portal da Transparência da Prefeitura de Americana,
acha as páginas de despesa e guarda como cada uma é montada, para escrevermos
o script que baixa as despesas por secretaria, mês a mês.

Poucos pedidos: o mapa do site e no máximo 10 páginas de despesa, com pausa
de 5 segundos entre eles, robô identificado. Não baixa planilha nenhuma.

Uso no WSL:  python3 olhar_portal_despesas.py
Saída:       W:\\Desktop\\AmericanaFiscaliza\\diagnostico-despesas.zip  (mandar no chat)
"""
import os, re, sys, time, urllib.parse, urllib.request, zipfile
from http.cookiejar import CookieJar

BASE = "https://transparencia.americana.sp.gov.br/"
MAPA = BASE + "transparencia_index.php?p=mapaSite"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas)"
PAUSA = 5
MAX_PAGINAS = 10
INTERESSE = re.compile(r"despesa|empenho|pagamento|secretaria|unidade|[oó]rg[aã]o|execu[cç][aã]o|credor|fornecedor", re.I)

DESTINO = sys.argv[1] if len(sys.argv) > 1 else "/mnt/w/Desktop/AmericanaFiscaliza"
PASTA = os.path.join(DESTINO, "diagnosticos", "despesas")
os.makedirs(PASTA, exist_ok=True)
abrir = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar())).open
ultimo = 0.0


def pedir(url):
    global ultimo
    espera = ultimo + PAUSA - time.time()
    if ultimo and espera > 0:
        time.sleep(espera)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": BASE})
    try:
        with abrir(req, timeout=60) as r:
            return r.read()
    finally:
        ultimo = time.time()


def texto(b):
    return b.decode("latin-1", "replace") if b"charset=ISO-8859-1" in b[:3000] or b"iso-8859-1" in b[:3000] else b.decode("utf-8", "replace")


def main():
    print("Abrindo o mapa do site ...")
    mapa = texto(pedir(MAPA))
    open(os.path.join(PASTA, "mapa.html"), "w", encoding="utf-8").write(mapa)
    links = []
    for href, rotulo in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', mapa, re.S):
        r = re.sub(r"<[^>]+>|&nbsp;|\s+", " ", rotulo).strip()
        links.append((href, r))
    resumo = ["== TODOS OS LINKS DO MAPA =="] + [f"{r}  ->  {h}" for h, r in links]
    alvo, vistos = [], set()
    for h, r in links:
        u = urllib.parse.urljoin(MAPA, h.split("#")[0])
        if INTERESSE.search(r + " " + h) and urllib.parse.urlparse(u).netloc in BASE and u not in vistos:
            vistos.add(u); alvo.append((u, r))
    resumo += ["", "== PÁGINAS DE DESPESA BAIXADAS =="]
    for i, (u, r) in enumerate(alvo[:MAX_PAGINAS]):
        try:
            open(os.path.join(PASTA, f"pagina{i + 1:02d}.html"), "w", encoding="utf-8").write(texto(pedir(u)))
            resumo.append(f"pagina{i + 1:02d}.html  {r}  ->  {u}")
            print(f"ok: {r}")
        except Exception as e:
            resumo.append(f"[falhou] {r} -> {u}: {e}")
    open(os.path.join(PASTA, "resumo.txt"), "w", encoding="utf-8").write("\n".join(resumo))
    zipado = os.path.join(DESTINO, "diagnostico-despesas.zip")
    with zipfile.ZipFile(zipado, "w", zipfile.ZIP_DEFLATED) as z:
        for n in os.listdir(PASTA):
            z.write(os.path.join(PASTA, n), n)
    print(f"Pronto. Mande este arquivo no chat: {zipado}")


if __name__ == "__main__":
    main()
