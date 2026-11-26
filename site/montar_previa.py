#!/usr/bin/env python3
"""Junta o site num arquivo só (previa.html) para abrir com dois cliques, sem servidor.
Só serve para ver antes de publicar; o site de verdade é a pasta publico/."""
import base64, glob, json, os

AQUI = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(AQUI, "publico")
idx = open(os.path.join(P, "index.html"), encoding="utf-8").read()
css = open(os.path.join(P, "estilo.css"), encoding="utf-8").read()
js = open(os.path.join(P, "app.js"), encoding="utf-8").read()
dados = {os.path.basename(f): json.load(open(f, encoding="utf-8")) for f in glob.glob(os.path.join(P, "dados", "*.json"))}
fotos = {}
_logo = os.path.join(P, "img", "brasao-camara.png")
if os.path.exists(_logo):
    idx = idx.replace('src="img/brasao-camara.png"', 'src="data:image/png;base64,' + base64.b64encode(open(_logo, "rb").read()).decode() + '"')
for f in glob.glob(os.path.join(P, "fotos", "*.jpg")):
    fotos["fotos/" + os.path.basename(f)] = "data:image/jpeg;base64," + base64.b64encode(open(f, "rb").read()).decode()
js = js.replace("function fotoLocal(v) { return `fotos/${v.slug}.jpg`; }",
                "function fotoLocal(v) { return (window.FOTOS || {})[`fotos/${v.slug}.jpg`] || `fotos/${v.slug}.jpg`; }")
emb = "window.DADOS_EMBUTIDOS=" + json.dumps(dados, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";\nwindow.FOTOS=" + json.dumps(fotos) + ";\n"
html = idx.replace('<link rel="stylesheet" href="estilo.css">', f"<style>{css}</style>")
html = html.replace('<script src="app.js"></script>', f"<script>{emb}</script>\n<script>{js}</script>")
html = html.replace("<title>Americana Fiscaliza</title>", "<title>Americana Fiscaliza (prévia)</title>")
open(os.path.join(AQUI, "previa.html"), "w", encoding="utf-8").write(html)
print(f"previa.html: {len(html)//1024} KB")
