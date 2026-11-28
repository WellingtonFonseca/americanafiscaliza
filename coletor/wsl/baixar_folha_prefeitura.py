#!/usr/bin/env python3
"""Baixa a planilha "Remuneração dos Servidores" da Prefeitura de Americana,
mês a mês, desde janeiro de 2025 (rodar no computador do Wellington, com
internet do Brasil; o portal recusa acessos de fora do país).

É o mesmo que escolher Empresa "PREFEITURA DE AMERICANA", o mês e o ano no
portal e clicar no botão do Excel. Robô identificado, 15 segundos de pausa
entre os pedidos, no máximo 24 planilhas por vez. Pula os meses que já estão
na pasta. Para na hora se o portal responder 403 ou 429.

Uso no WSL:  python3 baixar_folha_prefeitura.py
Saída:       W:\\Desktop\\AmericanaFiscaliza\\planilhas\\remuneracao-AAAA-MM.xlsx
             W:\\Desktop\\AmericanaFiscaliza\\planilhas.zip  (mandar no chat)
"""
import os, re, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import date
from http.cookiejar import CookieJar

BASE = "https://transparencia.americana.sp.gov.br/"
PAGINA = BASE + "transparencia_index.php?p=servidor_remuneracao"
XLS = BASE + "transparencia_servidor_remuneracao_xls.php"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas)"
PAUSA = 15
MAX_MESES = 24
INICIO = (2025, 1)
EMPRESA = "1"  # PREFEITURA DE AMERICANA

DESTINO = sys.argv[1] if len(sys.argv) > 1 else "/mnt/w/Desktop/AmericanaFiscaliza"
PASTA = os.path.join(DESTINO, "planilhas")
os.makedirs(PASTA, exist_ok=True)
abrir = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar())).open
ultimo = 0.0


def pedir(url, dados=None):
    global ultimo
    espera = ultimo + PAUSA - time.time()
    if ultimo and espera > 0:
        time.sleep(espera)
    corpo = urllib.parse.urlencode(dados).encode("latin-1") if dados is not None else None
    req = urllib.request.Request(url, data=corpo, headers={"User-Agent": UA, "Referer": PAGINA})
    try:
        with abrir(req, timeout=180) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            print(f"O portal respondeu {e.code}. Parando para não insistir. Tente de novo outro dia.")
            sys.exit(2)
        raise
    finally:
        ultimo = time.time()


def formulario(ano, mes, h_ano, h_mes):
    return {"paginaAtual": "", "ultimaPagina": "", "h_anoFolha": h_ano, "h_mesFolha": h_mes,
            "cboEmpresa": EMPRESA, "cboMes": str(mes), "cboAno": str(ano),
            "txtNome": "", "cboCargo": "0", "cboSecretaria": "0"}


def planilha_ok(b, ano, mes):
    if not b.startswith(b"PK"):
        return False
    try:
        import io
        z = zipfile.ZipFile(io.BytesIO(b))
        txt = "".join(z.read(n).decode("utf-8", "replace") for n in z.namelist() if n.startswith("xl/"))
    except Exception:
        return False
    # o campo "Atualizado em:" da planilha traz o mês pedido, sozinho na célula (ex.: 07/2026)
    return "Remunera" in txt and f">{mes:02d}/{ano}<" in txt


def baixar_mes(ano, mes):
    # 1) direto, como o botão do Excel faz depois de uma consulta
    b = pedir(XLS, formulario(ano, mes, str(ano), str(mes)))
    if planilha_ok(b, ano, mes):
        return b
    # 2) se não veio, consulta o mês primeiro (como clicar em Consultar) e pede de novo
    pg = pedir(PAGINA, formulario(ano, mes, "0", "0")).decode("latin-1", "replace")
    h_ano = re.search(r'name="h_anoFolha" value="([^"]*)"', pg)
    h_mes = re.search(r'name="h_mesFolha" value="([^"]*)"', pg)
    b = pedir(XLS, formulario(ano, mes, h_ano.group(1) if h_ano else str(ano), h_mes.group(1) if h_mes else str(mes)))
    return b if planilha_ok(b, ano, mes) else None


def main():
    hoje = date.today()
    meses, (a, m) = [], INICIO
    while (a, m) < (hoje.year, hoje.month):  # só meses já encerrados
        meses.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    arq = lambda a, m: os.path.join(PASTA, f"remuneracao-{a}-{m:02d}.xlsx")
    faltam = [x for x in meses if not os.path.exists(arq(*x))][:MAX_MESES]
    if not faltam:
        print("Todos os meses já estão na pasta.")
    else:
        print(f"Vou baixar {len(faltam)} mês(es), com {PAUSA} s de pausa entre os pedidos. Pode levar alguns minutos.")
        pedir(PAGINA)  # abre a página uma vez, como um navegador
    for a, m in faltam:
        try:
            b = baixar_mes(a, m)
        except Exception as e:
            print(f"{m:02d}/{a}: falhou ({e.__class__.__name__}: {e}); tento de novo na próxima vez")
            continue
        if not b:
            print(f"{m:02d}/{a}: o portal não devolveu a planilha desse mês (talvez ainda não publicada)")
            continue
        open(arq(a, m), "wb").write(b)
        print(f"{m:02d}/{a}: ok ({len(b) // 1024} KB)")
    zipado = os.path.join(DESTINO, "planilhas.zip")
    with zipfile.ZipFile(zipado, "w", zipfile.ZIP_DEFLATED) as z:
        for n in sorted(os.listdir(PASTA)):
            if n.endswith(".xlsx"):
                z.write(os.path.join(PASTA, n), n)
    print(f"Pronto. Mande este arquivo no chat: {zipado}")


if __name__ == "__main__":
    main()
