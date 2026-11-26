#!/usr/bin/env python3
"""Coleta leve no Portal da Transparência da Câmara (SMARAPD): folha do mês.

Fonte: https://transparencia-cmamericana.smarapd.com.br/#/dinamico/restoapagar/pagamentosaservidores
O portal é uma página em JavaScript que lê os dados de /paiportalserver; o
servidor só responde a pedidos que informam a origem (o próprio portal), como
faz o navegador. Decisão do Wellington (26/11/2026): ler assim, de forma leve
e identificada, porque são dados públicos.

Guardamos só o necessário para o site: os vereadores (cargo VEREADOR) e quem
está lotado em gabinete de vereador. Nada de aposentados ou outros setores.
Cada execução faz no máximo 3 pedidos (procura o último mês fechado com dados).

Uso: python3 -I coletar_portal.py [pasta_de_dados]
"""
import json, os, sys, time, urllib.request
from datetime import datetime, timezone

PORTAL = "https://transparencia-cmamericana.smarapd.com.br"
API = PORTAL + "/paiportalserver/modulovisao/filter"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
MESES = ["JANEIRO", "FEVEREIRO", "MARCO", "ABRIL", "MAIO", "JUNHO", "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO"]
CAMPOS = ["NomeServidor", "Cargo", "DescrLotacao", "DataAdmissao", "ValorBruto", "ValorLiquido"]
PASTA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
SAIDA = os.path.join(PASTA, "portal")
os.makedirs(SAIDA, exist_ok=True)


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


def main():
    if os.path.exists(os.path.join(PASTA, "PARAR")):
        log("arquivo PARAR existe; nada foi pedido"); return
    hoje = datetime.now()
    # Começa pelo mês anterior: a folha do mês corrente pode estar incompleta.
    ano, m = (hoje.year, hoje.month - 2) if hoje.month > 1 else (hoje.year - 1, 11)
    for tentativa in range(3):
        mes = MESES[m]
        d = folha(ano, mes)
        n = d.get("QuantidadeRegistros", 0)
        log(f"folha {mes.lower()}/{ano}: {n} registros")
        if n and d.get("QuantidadePaginas", 1) == 1:
            linhas = [{k: x.get(k) for k in CAMPOS} for x in d["Valores"]
                      if (x.get("Cargo") or "").strip().upper() == "VEREADOR" or (x.get("DescrLotacao") or "").upper().startswith("GABINETE")]
            json.dump({"fonte": PORTAL + "/#/dinamico/restoapagar/pagamentosaservidores", "ano": ano, "mes": mes,
                       "total_registros_no_portal": n, "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "linhas": linhas}, open(os.path.join(SAIDA, "folha.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            log(f"guardadas {len(linhas)} linhas (vereadores e gabinetes)")
            return
        m -= 1
        if m < 0:
            ano, m = ano - 1, 11
        time.sleep(5)
    log("nenhum mês com dados encontrado; mantida a folha anterior")


if __name__ == "__main__":
    main()
