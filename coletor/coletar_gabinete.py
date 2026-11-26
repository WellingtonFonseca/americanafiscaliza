#!/usr/bin/env python3
"""Coleta os relatórios "Gastos com Gabinete" do site da Câmara (um PDF por vereador).

Fonte: https://www.camara-americana.sp.gov.br/Download/Listar/46
Desde o Ato da Mesa 254/2019 a Câmara informa o consumo em unidades (cópias,
minutos, litros), não em reais. Guardamos só o texto extraído do PDF (pdftotext)
e o endereço do PDF original, para o repositório não crescer.

Uso: python3 -I coletar_gabinete.py [pasta_de_dados]   (precisa do pdftotext)
"""
import html, json, os, re, subprocess, sys, tempfile, time, urllib.request
from datetime import datetime, timezone

SITE = "https://www.camara-americana.sp.gov.br"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
PAUSA = 3
PASTA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
SAIDA = os.path.join(PASTA, "gabinete")
os.makedirs(SAIDA, exist_ok=True)


def baixar(url):
    time.sleep(PAUSA)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return r.read()


def log(msg):
    linha = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} [gabinete] {msg}"
    print(linha, flush=True)
    with open(os.path.join(PASTA, "coleta.log"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def main():
    if os.path.exists(os.path.join(PASTA, "PARAR")):
        log("arquivo PARAR existe; nada foi pedido"); return
    lista = html.unescape(baixar(SITE + "/Download/Listar/46").decode("utf-8", "replace"))
    links = re.findall(r'<a[^>]*href="(/Arquivos/Downloads/[^"]+\.pdf)"[^>]*>([^<]+)</a>', lista)
    indice = []
    for caminho, nome in links:
        url = SITE + caminho
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(baixar(url)); tmp.flush()
            txt = subprocess.run(["pdftotext", "-layout", tmp.name, "-"], capture_output=True, text=True, check=True).stdout
            info = subprocess.run(["pdfinfo", tmp.name], capture_output=True, text=True).stdout
        criado = re.search(r"CreationDate:\s*(.+)", info)
        arq = re.sub(r"[^a-z0-9]+", "-", caminho.split("/")[-1].lower()) + ".txt"
        open(os.path.join(SAIDA, arq), "w", encoding="utf-8").write(txt)
        indice.append({"nome_na_lista": nome.strip(), "pdf": url, "texto": arq,
                       "criado_em": criado.group(1).strip() if criado else ""})
        log(f"{nome.strip()}: ok")
    json.dump({"fonte": SITE + "/Download/Listar/46", "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "arquivos": indice}, open(os.path.join(SAIDA, "indice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    log(f"fim: {len(indice)} relatórios")


if __name__ == "__main__":
    main()
