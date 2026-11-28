#!/usr/bin/env python3
"""Importa as planilhas de "Remuneração dos Servidores" do Portal da
Transparência da Prefeitura de Americana (transparencia.americana.sp.gov.br).

O portal não aceita acesso automático de fora do Brasil (nem do GitHub
Actions), então as planilhas são baixadas à mão no portal (uma por mês, em
Excel) e importadas com este script. Guardamos só o que o site usa:
prefeito, vice-prefeito, secretários municipais (agentes políticos) e quem
está lotado no Gabinete do Prefeito, mais o total de servidores do mês.

Uso: python3 -I importar_folha_prefeitura.py planilha1.xlsx [planilha2.xlsx ...]
Saída: dados/prefeitura/folha/folha-AAAA-MM.json
Só biblioteca padrão (o arquivo do portal tem cabeçalho que o openpyxl recusa).
"""
import html, json, os, re, sys, zipfile
from datetime import datetime, timezone

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados", "prefeitura", "folha")
FONTE = "https://transparencia.americana.sp.gov.br/transparencia_index.php?p=servidor_remuneracao"
COLS = {"A": "matricula", "B": "nome", "C": "cargo", "D": "cargo_origem", "E": "lotacao", "F": "admissao",
        "G": "regime", "H": "vencimentos", "I": "ferias_13", "J": "licenca_premio", "K": "vantagens",
        "L": "previdencia", "M": "ir", "N": "fgts"}
VALORES = ("vencimentos", "ferias_13", "licenca_premio", "vantagens", "previdencia", "ir", "fgts")


def linhas(caminho):
    z = zipfile.ZipFile(caminho)
    ss = []
    if "xl/sharedStrings.xml" in z.namelist():
        t = z.read("xl/sharedStrings.xml").decode("utf-8", "replace")
        ss = [html.unescape("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S))) for si in re.findall(r"<si>(.*?)</si>", t, re.S)]
    folha = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    t = z.read(folha).decode("utf-8", "replace")
    for row in re.findall(r"<row[^>]*>(.*?)</row>", t, re.S):
        cel = {}
        for ref, attrs, corpo in re.findall(r'<c r="([A-Z]+)\d+"([^>]*)>(.*?)</c>', row, re.S):
            v = re.search(r"<v>(.*?)</v>", corpo, re.S)
            tx = re.search(r"<t[^>]*>(.*?)</t>", corpo, re.S)
            val = v.group(1) if v else (tx.group(1) if tx else "")
            if 't="s"' in attrs and v:
                val = ss[int(val)]
            cel[ref] = html.unescape(val).strip()
        yield cel


def numero(t):
    t = (t or "").strip()
    return float(t.replace(".", "").replace(",", ".")) if t else 0.0


def importar(caminho):
    todas = list(linhas(caminho))
    mes = next(c["D"] for c in todas if c.get("C", "").startswith("Atualizado"))
    empresa = next((c.get("D", "") for c in todas if c.get("C") == "Empresa"), "")
    cab = next(i for i, c in enumerate(todas) if c.get("A") == "Matricula")
    pessoas = []
    for c in todas[cab + 1:]:
        if not c.get("B"):
            continue
        p = {COLS[k]: c.get(k, "") for k in COLS}
        for k in VALORES:
            p[k] = numero(p[k])
        p["bruto"] = round(p["vencimentos"] + p["ferias_13"] + p["licenca_premio"] + p["vantagens"], 2)
        pessoas.append(p)
    m, a = mes.split("/")
    so = lambda f: [{k: p[k] for k in ("nome", "cargo", "cargo_origem", "lotacao", "admissao", "regime", "vencimentos", "ferias_13", "licenca_premio", "vantagens", "bruto")} for p in pessoas if f(p)]
    prefeito = so(lambda p: p["cargo"] == "PREFEITO")
    vice = so(lambda p: p["cargo"] == "VICE-PREFEITO")
    secretarios = sorted(so(lambda p: p["cargo"] == "SECRETARIO - AGENTE POLITICO"), key=lambda p: p["nome"])
    gabinete = sorted(so(lambda p: p["lotacao"] == "GABINETE DO PREFEITO" and p["cargo"] not in ("PREFEITO", "VICE-PREFEITO")), key=lambda p: -p["bruto"])
    out = {"ano": int(a), "mes": int(m), "empresa": empresa, "fonte": FONTE, "arquivo": os.path.basename(caminho),
           "importado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "total_servidores": len(pessoas), "total_bruto": round(sum(p["bruto"] for p in pessoas), 2),
           "prefeito": prefeito[0] if prefeito else None, "vice": vice[0] if vice else None,
           "secretarios": secretarios, "gabinete": gabinete}
    os.makedirs(PASTA, exist_ok=True)
    destino = os.path.join(PASTA, f"folha-{a}-{int(m):02d}.json")
    json.dump(out, open(destino, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{a}-{int(m):02d}: {len(pessoas)} servidores; prefeito {'ok' if prefeito else 'NÃO ENCONTRADO'}; "
          f"vice {'ok' if vice else 'NÃO ENCONTRADO'}; {len(secretarios)} secretários; {len(gabinete)} no Gabinete do Prefeito -> {destino}")


if __name__ == "__main__":
    for arq in sys.argv[1:]:
        importar(arq)
