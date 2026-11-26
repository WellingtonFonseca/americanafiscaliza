#!/usr/bin/env python3
"""Coleta leve no Portal da Transparência da Câmara (SMARAPD): folha do mês.

Fonte: https://transparencia-cmamericana.smarapd.com.br/#/dinamico/restoapagar/pagamentosaservidores
O portal é uma página em JavaScript que lê os dados de /paiportalserver; o
servidor só responde a pedidos que informam a origem (o próprio portal), como
faz o navegador. Decisão do Wellington (26/11/2026): ler assim, de forma leve
e identificada, porque são dados públicos.

Guardamos só o necessário para o site: os vereadores (cargo VEREADOR) e quem
está lotado em gabinete de vereador. Nada de aposentados ou outros setores.
Uma folha por mês desde janeiro/2025 (início do mandato), em portal/folha-AAAA-MM.json.
Cada execução pede só os meses que ainda faltam, no máximo 4 (ou o número dado
em --limite N, usado uma vez para baixar o histórico).

Uso: python3 -I coletar_portal.py [pasta_de_dados] [--limite N]
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone

PORTAL = "https://transparencia-cmamericana.smarapd.com.br"
API = PORTAL + "/paiportalserver/modulovisao/filter"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
MESES = ["JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
CAMPOS = ["NomeServidor", "Cargo", "DescrLotacao", "DataAdmissao", "ValorBruto", "ValorLiquido"]
ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
LIMITE = int(sys.argv[sys.argv.index("--limite") + 1]) if "--limite" in sys.argv else 4
if "--limite" in sys.argv:
    ARGS.remove(sys.argv[sys.argv.index("--limite") + 1])
INICIO = (2025, 0)
PASTA = os.path.abspath(ARGS[0] if ARGS else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
SAIDA = os.path.join(PASTA, "portal")
os.makedirs(SAIDA, exist_ok=True)


def arquivo(ano, m):
    return os.path.join(SAIDA, f"folha-{ano}-{m + 1:02d}.json")


def log(msg):
    linha = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} [portal] {msg}"
    print(linha, flush=True)
    with open(os.path.join(PASTA, "coleta.log"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def folha(ano, mes):
    corpo = json.dumps({"ChaveModulo": "restoapagar", "NomeVisao": "pagamentosaservidores", "Filtros": [],
                        "Periodicidade": "MENSAL", "Periodo": mes, "Exercicio": ano, "Ordenacao": [],
                        "Pagina": 1, "QuantidadeRegistros": 1000}).encode()
    req = urllib.request.Request(API, data=corpo, method="POST", headers={
        "User-Agent": UA, "Content-Type": "application/json", "Origin": PORTAL, "Referer": PORTAL + "/"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def mes_anterior(ano, m):
    return (ano, m - 1) if m > 0 else (ano - 1, 11)


def main():
    if os.path.exists(os.path.join(PASTA, "PARAR")):
        log("arquivo PARAR existe; nada foi pedido"); return
    # Uma folha por mês, desde o início do mandato. A cada execução: o último mês
    # fechado (se ainda não temos) e no máximo LIMITE meses antigos que faltam.
    hoje = datetime.now()
    ano, m = mes_anterior(hoje.year, hoje.month - 1)  # m é 0..11; começa no mês anterior ao corrente
    meses = []
    while (ano, m) >= INICIO:
        meses.append((ano, m)); ano, m = mes_anterior(ano, m)
    faltam = [x for x in meses if not os.path.exists(arquivo(*x))]
    pedidos = 0
    for ano, m in faltam:
        if pedidos >= LIMITE:
            break
        if pedidos:
            time.sleep(4)
        mes = MESES[m]
        d = folha(ano, mes); pedidos += 1
        n = d.get("QuantidadeRegistros", 0)
        log(f"folha {mes.lower()}/{ano}: {n} registros")
        if not n or d.get("QuantidadePaginas", 1) != 1:
            continue  # mês ainda sem dados (ou grande demais); tenta de novo na próxima execução
        linhas = [{k: x.get(k) for k in CAMPOS} for x in d["Valores"]
                  if (x.get("Cargo") or "").strip().upper() == "VEREADOR" or (x.get("DescrLotacao") or "").upper().startswith("GABINETE")]
        json.dump({"fonte": PORTAL + "/#/dinamico/restoapagar/pagamentosaservidores", "ano": ano, "mes": mes,
                   "total_registros_no_portal": n, "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "linhas": linhas}, open(arquivo(ano, m), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"{mes.lower()}/{ano}: guardadas {len(linhas)} linhas (vereadores e gabinetes)")
    if not faltam:
        log("todas as folhas desde o início do mandato já estão guardadas")


if __name__ == "__main__":
    main()
