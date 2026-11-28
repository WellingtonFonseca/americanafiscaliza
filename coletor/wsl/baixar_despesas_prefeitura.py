#!/usr/bin/env python3
"""Baixa as despesas da Prefeitura de Americana, mês a mês, desde janeiro de
2025 (rodar no computador do Wellington, com internet do Brasil; o portal
recusa acessos de fora do país).

É o mesmo que abrir no portal "Despesa" (Movimento diário), escolher o
exercício, o mês, o tipo de lançamento (Empenhadas, Liquidadas, Pagas), deixar
"Classificar por Dotação" marcado e clicar no botão do CSV. A dotação traz a
secretaria (unidade orçamentária) de cada despesa.

São 3 arquivos por mês, com 10 segundos de pausa entre os pedidos e robô
identificado. Pula os meses que já estão na pasta, mas baixa de novo os 2
últimos meses fechados (a Prefeitura ainda pode completar esses lançamentos).
Para na hora se o portal responder 403 ou 429.

Uso no WSL:  python3 baixar_despesas_prefeitura.py
Saída:       W:\\Desktop\\AmericanaFiscaliza\\despesas-secretarias\\despesas-AAAA-MM-<tipo>.csv
             W:\\Desktop\\AmericanaFiscaliza\\despesas-secretarias-AAAA-MM-a-AAAA-MM.zip  (mandar no chat)
"""
import os, sys, time, urllib.error, urllib.parse, urllib.request, zipfile
from datetime import date
from http.cookiejar import CookieJar

BASE = "https://transparencia.americana.sp.gov.br/"
PAGINA = BASE + "transparencia_index.php?p=movDiario_consultaDespesa&t=5&r=33"
CSV = BASE + "transparencia_movDiarioDespesa_csv.php"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas)"
PAUSA = 10
MAX_MESES = 24
RENOVAR = 2
INICIO = (2025, 1)
TIPOS = {"E": "empenhadas", "L": "liquidadas", "P": "pagas"}

DESTINO = sys.argv[1] if len(sys.argv) > 1 else "/mnt/w/Desktop/AmericanaFiscaliza"
PASTA = os.path.join(DESTINO, "despesas-secretarias")
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
        with abrir(req, timeout=300) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            print(f"O portal respondeu {e.code}. Parando para não insistir. Tente de novo outro dia.")
            sys.exit(2)
        raise
    finally:
        ultimo = time.time()


def formulario(ano, mes, tipo):
    # os mesmos campos que o navegador manda, com todos os filtros em "Todas"
    return {"paginaAtual": "", "ultimaPagina": "", "h_idRelatorio": "33", "h_idTipoTransparencia": "5",
            "limpaCampos": "0", "cboAno": str(ano), "cboMes": f"{mes:02d}", "cboTipo": tipo, "cboTipoD": "O",
            "txtDataInicial": "", "txtDataFinal": "", "txtValorInicial": "", "txtValorFinal": "",
            "cbgFornecedor": "", "cbgFornecedor_id": "", "cboDestRecurso": "-1", "cboTipoC": "0",
            "txtNumContrato": "", "txtAnoContrato": "", "txtEmpenho": "", "txtNF": "", "cboModalidade": "-1",
            "cboUO": "-1", "cboUE": "0", "cboFuncao": "-1", "cboSubFuncao": "-1", "cboPrograma": "-1",
            "cboAcao": "-1", "cboCategoria": "-1", "cboContaDespesa": "-1", "chkDetalhe": "1", "chkDescricao": "1"}


def parece_csv(b):
    ini = b[:2000].lstrip().lower()
    return len(b) > 50 and not ini.startswith(b"<") and b"<html" not in ini and (b";" in ini or b"," in ini)


def baixar(ano, mes, tipo):
    f = formulario(ano, mes, tipo)
    b = pedir(CSV, f)
    if parece_csv(b):
        return b
    # se não veio, faz a consulta na página (como clicar em Consultar) e pede o CSV de novo
    pedir(PAGINA, f)
    b = pedir(CSV, f)
    return b if parece_csv(b) else None


def main():
    hoje = date.today()
    meses, (a, m) = [], INICIO
    while (a, m) < (hoje.year, hoje.month):  # só meses já encerrados
        meses.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    arq = lambda a, m, t: os.path.join(PASTA, f"despesas-{a}-{m:02d}-{TIPOS[t]}.csv")
    completo = lambda a, m: all(os.path.exists(arq(a, m, t)) for t in TIPOS)
    fila = [x for x in meses if not completo(*x) or x in meses[-RENOVAR:]][:MAX_MESES]
    print(f"Vou baixar {len(fila)} mês(es), 3 arquivos cada, com {PAUSA} s de pausa entre os pedidos. Pode levar uns {len(fila) * 3 * PAUSA // 60 + 1} minutos.")
    if fila:
        pedir(PAGINA)  # abre a página uma vez, como um navegador
    for a, m in fila:
        for t, nome in TIPOS.items():
            try:
                b = baixar(a, m, t)
            except Exception as e:
                print(f"{m:02d}/{a} {nome}: falhou ({e.__class__.__name__}: {e}); tento de novo na próxima vez")
                continue
            if not b:
                print(f"{m:02d}/{a} {nome}: o portal não devolveu o arquivo")
                continue
            open(arq(a, m, t), "wb").write(b)
            print(f"{m:02d}/{a} {nome}: ok ({len(b) // 1024} KB)")
    nomes = sorted(n for n in os.listdir(PASTA) if n.startswith("despesas-") and n.endswith(".csv"))
    if not nomes:
        print("Nenhum arquivo na pasta; nada para mandar."); return
    de, ate = nomes[0][9:16], nomes[-1][9:16]
    for velho in os.listdir(DESTINO):  # tira zips antigos das despesas, para não confundir
        if velho.startswith("despesas-secretarias-") and velho.endswith(".zip"):
            os.remove(os.path.join(DESTINO, velho))
    zipado = os.path.join(DESTINO, f"despesas-secretarias-{de}-a-{ate}.zip")
    with zipfile.ZipFile(zipado, "w", zipfile.ZIP_DEFLATED) as z:
        for n in nomes:
            z.write(os.path.join(PASTA, n), n)
    print(f"Pronto. Mande este arquivo no chat: {zipado}")


if __name__ == "__main__":
    main()
