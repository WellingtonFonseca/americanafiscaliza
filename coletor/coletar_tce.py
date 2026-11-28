#!/usr/bin/env python3
"""Despesas da Prefeitura de Americana, pela API aberta do TCE-SP (Audesp).

O Portal da Transparência da própria Prefeitura não responde a acessos de fora
do Brasil (nem do GitHub Actions). O Tribunal de Contas publica as despesas que
a Prefeitura informa ao sistema Audesp, mês a mês:
  https://transparencia.tce.sp.gov.br/api/json/despesas/americana/<ano>/<mes>

Guardamos só um RESUMO por mês (dados/prefeitura/tce-AAAA-MM.json): totais
empenhado, liquidado, pago e anulado da Prefeitura, e os maiores recebedores
pagos com CNPJ. Pagamentos a pessoas físicas entram só no total.

Leve: no máximo 4 pedidos por execução. Primeiro os meses que faltam (desde
jan/2025), depois a renovação dos 3 meses mais recentes, que o município ainda
pode completar. Para tudo se existir dados/PARAR ou em 403/429.
Uso: python3 -I coletar_tce.py [pasta_de_dados]
"""
import json, os, sys, time, urllib.error, urllib.request
from collections import defaultdict
from datetime import datetime, timezone

API = "https://transparencia.tce.sp.gov.br/api/json/despesas/americana/{ano}/{mes}"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
PAUSA = 10
MAX_PEDIDOS = 4
INICIO = (2025, 1)
ORGAO = "PREFEITURA MUNICIPAL DE AMERICANA"
EVENTOS = {"Empenhado": "empenhado", "Valor Liquidado": "liquidado", "Valor Pago": "pago", "Anulação": "anulado"}
TOP = 15

PASTA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
SAIDA = os.path.join(PASTA, "prefeitura")
PARAR = os.path.join(PASTA, "PARAR")
os.makedirs(SAIDA, exist_ok=True)


def log(msg):
    linha = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} [tce] {msg}"
    print(linha, flush=True)
    with open(os.path.join(PASTA, "coleta.log"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def valor(t):
    return float(t.replace(".", "").replace(",", ".")) if "," in t else float(t)


def resumir(linhas, ano, mes):
    tot = defaultdict(float)
    pagos = defaultdict(float)
    pf = [0, 0.0]
    for x in linhas:
        if x.get("orgao") != ORGAO or x.get("evento") not in EVENTOS:
            continue
        v = valor(x["vl_despesa"])
        tot[EVENTOS[x["evento"]]] += v
        if x["evento"] == "Valor Pago":
            if x["id_fornecedor"].startswith("CNPJ"):
                cnpj = x["id_fornecedor"].rsplit(" - ", 1)[-1].strip()
                pagos[(x["nm_fornecedor"].strip(), cnpj)] += v
            else:
                pf[0] += 1
                pf[1] += v
    maiores = sorted(pagos.items(), key=lambda kv: -kv[1])[:TOP]
    return {"ano": ano, "mes": mes, "orgao": ORGAO, "fonte": API.format(ano=ano, mes=mes),
            "coletado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "registros": len(linhas), "totais": {k: round(tot.get(k, 0.0), 2) for k in EVENTOS.values()},
            "recebedores_cnpj": len(pagos),
            "maiores_pagos": [{"nome": n, "cnpj": c, "valor": round(v, 2)} for (n, c), v in maiores],
            "pessoas_fisicas": {"pagamentos": pf[0], "valor": round(pf[1], 2)}}


def main():
    hoje = datetime.now(timezone.utc)
    meses = []
    a, m = INICIO
    while (a, m) < (hoje.year, hoje.month):  # só meses já encerrados
        meses.append((a, m))
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    arq = lambda a, m: os.path.join(SAIDA, f"tce-{a}-{m:02d}.json")
    faltam = [x for x in meses if not os.path.exists(arq(*x))]
    renovar = [x for x in meses[-3:] if x not in faltam]
    fila = (faltam + renovar)[:MAX_PEDIDOS]
    if not fila:
        log("nada a pedir"); return
    for i, (a, m) in enumerate(fila):
        if os.path.exists(PARAR):
            log("arquivo PARAR existe; parando"); sys.exit(2)
        if i:
            time.sleep(PAUSA)
        url = API.format(ano=a, mes=m)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
                linhas = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                open(PARAR, "w").write(f"{e.code} em {url} - {datetime.now().isoformat()}\n")
                log(f"PARADO: {e.code} em {url}"); sys.exit(2)
            log(f"{a}-{m:02d}: HTTP {e.code}"); continue
        except Exception as e:  # rede instável: tenta na próxima execução
            log(f"{a}-{m:02d}: falhou ({e.__class__.__name__})"); continue
        if not isinstance(linhas, list) or not linhas:
            log(f"{a}-{m:02d}: sem registros ainda"); continue
        res = resumir(linhas, a, m)
        json.dump(res, open(arq(a, m), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        log(f"{a}-{m:02d}: {len(linhas)} registros; pago pela Prefeitura R$ {res['totais']['pago']:,.2f}")
    log("fim")


if __name__ == "__main__":
    main()
