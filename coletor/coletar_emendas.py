#!/usr/bin/env python3
"""Baixa o Autógrafo da Lei Orçamentária (LOA) de cada ano, que traz o
"Anexo Especial de Emendas Individuais Impositivas" (vereador, secretaria,
cota, valor e destino de cada emenda). Um PDF por ano; só baixa se ainda não
tiver. Guardamos o texto extraído (pdftotext), não o PDF.

Para incluir um ano novo: acrescente em LOAS o Autógrafo da lei aprovada
(página do documento e o link do arquivo no SISCAM).
Uso: python3 -I coletar_emendas.py [pasta_de_dados]   (precisa do pdftotext)
"""
import json, os, subprocess, sys, tempfile, urllib.request

UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
LOAS = {
    "2026": {"lei": "LOA 2026 (Projeto de Lei nº 137/2025, Autógrafo nº 125/2025)",
             "documento": "https://americana.siscam.com.br/Documentos/Documento/451399",
             "pdf": "https://americana.siscam.com.br/arquivo?Id=685126"},
}
PASTA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
SAIDA = os.path.join(PASTA, "emendas")
os.makedirs(SAIDA, exist_ok=True)

if os.path.exists(os.path.join(PASTA, "PARAR")):
    sys.exit(0)
for ano, info in LOAS.items():
    txt = os.path.join(SAIDA, f"loa{ano}.txt")
    if not os.path.exists(txt):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(urllib.request.urlopen(urllib.request.Request(info["pdf"], headers={"User-Agent": UA}), timeout=120).read())
            tmp.flush()
            subprocess.run(["pdftotext", "-layout", tmp.name, txt], check=True)
        print(f"LOA {ano}: baixada")
json.dump(LOAS, open(os.path.join(SAIDA, "fontes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
