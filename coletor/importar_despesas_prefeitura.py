#!/usr/bin/env python3
"""Importa as planilhas de despesas da Prefeitura de Americana baixadas com
coletor/wsl/baixar_despesas_prefeitura.py (Portal da Transparência, "Despesa",
movimento diário, exportado em Excel e classificado por dotação).

Cada planilha traz um lançamento por linha, com a unidade orçamentária
(secretaria) que gastou, o fornecedor e o valor. Guardamos um resumo por ano
(dados/prefeitura/despesas/despesas-AAAA.json): para cada secretaria, o total
empenhado, liquidado e pago no ano e em cada mês, e as empresas (CNPJ) que
mais receberam. Pagamentos a pessoas físicas (CPF mascarado no portal) entram
só nos totais. Valores negativos (anulações) entram como estão, descontando.

Uso: python3 -I importar_despesas_prefeitura.py pasta_com_as_planilhas
Só biblioteca padrão.
"""
import json, os, re, sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importar_folha_prefeitura import linhas, numero  # mesmo leitor de xlsx

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "prefeitura", "despesas")
FONTE = "https://transparencia.americana.sp.gov.br/transparencia_index.php?p=movDiario_consultaDespesa&t=5&r=33"
NOME_ARQ = re.compile(r"despesas-(\d{4})-(\d{2})-(empenhadas|liquidadas|pagas)(?:-uo\d+)?\.xlsx?$")
TIPO = {"empenhadas": "empenhado", "liquidadas": "liquidado", "pagas": "pago"}
CNPJ = re.compile(r"^(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s*-\s*(.+)$")
TOP = 10


def main(pasta):
    arquivos = sorted(n for n in os.listdir(pasta) if NOME_ARQ.match(n))
    anos = defaultdict(lambda: {"unidades": {}, "meses": set(), "arquivos": 0})
    pagos = defaultdict(lambda: defaultdict(float))  # (ano, unidade) -> (cnpj, nome) -> valor
    for n in arquivos:
        a, m, t = NOME_ARQ.match(n).groups()
        a, m, campo = int(a), int(m), TIPO[t]
        ano = anos[a]
        ano["meses"].add(m); ano["arquivos"] += 1
        todas = list(linhas(os.path.join(pasta, n)))
        cab = next(i for i, c in enumerate(todas) if c.get("A") == "Data" and c.get("AF") == "Valor")
        qtd = 0
        for c in todas[cab + 1:]:
            if not c.get("AF") or not c.get("E"):
                continue
            if c.get("C") != "02":
                raise SystemExit(f"{n}: órgão inesperado {c.get('C')} {c.get('D')}")
            v = numero(c["AF"])
            u = ano["unidades"].setdefault(c["E"], {"codigo": c["E"], "nome": c.get("F", ""), "empenhado": 0.0, "liquidado": 0.0,
                                                    "pago": 0.0, "por_mes": {}})
            u[campo] += v
            pm = u["por_mes"].setdefault(f"{m:02d}", {"empenhado": 0.0, "liquidado": 0.0, "pago": 0.0})
            pm[campo] += v
            qtd += 1
            if campo == "pago":
                f = CNPJ.match(c.get("AA", "").strip())
                if f:
                    pagos[(a, c["E"])][(f.group(1), f.group(2).strip())] += v
        print(f"{n}: {qtd} lançamentos")
    os.makedirs(PASTA, exist_ok=True)
    for a, ano in sorted(anos.items()):
        unidades = []
        for cod, u in sorted(ano["unidades"].items()):
            for k in ("empenhado", "liquidado", "pago"):
                u[k] = round(u[k], 2)
            u["por_mes"] = {mm: {k: round(x, 2) for k, x in v.items()} for mm, v in sorted(u["por_mes"].items())}
            top = sorted(pagos[(a, cod)].items(), key=lambda kv: -kv[1])[:TOP]
            u["maiores_pagos"] = [{"cnpj": c, "nome": nm, "valor": round(v, 2)} for (c, nm), v in top]
            unidades.append(u)
        meses = sorted(ano["meses"])
        out = {"ano": a, "meses": meses, "fonte": FONTE, "orgao": "PREFEITURA MUNICIPAL DE AMERICANA",
               "importado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "totais": {k: round(sum(u[k] for u in unidades), 2) for k in ("empenhado", "liquidado", "pago")},
               "unidades": unidades}
        destino = os.path.join(PASTA, f"despesas-{a}.json")
        json.dump(out, open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{a}: meses {meses[0]:02d} a {meses[-1]:02d}, {len(unidades)} secretarias, pago R$ {out['totais']['pago']:,.2f} -> {destino}")


if __name__ == "__main__":
    main(sys.argv[1])
