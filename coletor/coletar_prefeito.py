#!/usr/bin/env python3
"""Coleta leve do que o prefeito (Poder Executivo) faz na Câmara, pelo SISCAM.

Baixa, no máximo uma vez a cada 6 dias, as planilhas da exportação oficial da
pesquisa do SISCAM (a mesma usada para os vereadores grandes):
  1. projetos de autoria do "PODER EXECUTIVO DE AMERICANA" (autor 29), desde 2025;
  2. projetos de vereadores cuja situação atual é de veto (acatado, rejeitado,
     parcial, em tramitação, ao substitutivo), desde 2025.
São 8 pedidos por semana, com pausa de 30 s entre eles.

Os votos dos vereadores nos projetos e vetos do prefeito já vêm das páginas de
sessão (coletar_sessoes.py); aqui não se pede nada a mais para isso.

Regras combinadas: robô identificado, pausa entre pedidos, para tudo em 403/429
ou se existir dados/PARAR.
Uso: python3 -I coletar_prefeito.py [pasta_de_dados]
"""
import json, os, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

SISCAM = "https://americana.siscam.com.br"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
PAUSA = 30
INTERVALO = timedelta(days=6)
ANO_INICIO = 2025
AUTOR_EXECUTIVO = 29  # "PODER EXECUTIVO DE AMERICANA" na lista de autores do SISCAM
# Situações de veto no filtro da pesquisa do SISCAM (código: nome como está lá)
SITUACOES_VETO = {
    535: "Veto acatado", 536: "Veto rejeitado", 620: "Veto em tramitação", 668: "Veto parcial acatado",
    633: "Veto ao Substitutivo acatado", 624: "Veto Subst. acatado", 1473: "Veto ao Substitutivo Tramitando",
}
EXPORTAR = ("/Documentos/Exportar?tipo=2&Pesquisa=Avancada&id=74&pagina=1&Modulo=DocumentosLista"
            "&DocumentosRelacionadosDetalhes=false&NoTexto=false&Documento=0&Numeracao=Documento"
            "&AnoInicial={ano}&AnoFinal={fim}&Situacao={sit}&TipoAutor={tipo}&AutoriaId={autor}&Iniciativa=Nenhum")

PASTA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
SAIDA = os.path.join(PASTA, "prefeito")
PARAR = os.path.join(PASTA, "PARAR")
ESTADO = os.path.join(SAIDA, "estado.json")
os.makedirs(SAIDA, exist_ok=True)
ultimo = 0.0


def log(msg):
    linha = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} [prefeito] {msg}"
    print(linha, flush=True)
    with open(os.path.join(PASTA, "coleta.log"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def baixar(url):
    global ultimo
    if os.path.exists(PARAR):
        log("arquivo PARAR existe; parando sem pedir nada"); sys.exit(2)
    espera = ultimo + PAUSA - time.time()
    if ultimo and espera > 0:
        time.sleep(espera)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            st, txt = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        st, txt = e.code, ""
        if e.code in (403, 429):
            open(PARAR, "w").write(f"{e.code} em {url} - {datetime.now().isoformat()}\n")
            log(f"PARADO: {e.code} em {url}"); sys.exit(2)
    ultimo = time.time()
    return st, txt


def exportar(nome, **filtro):
    url = SISCAM + EXPORTAR.format(ano=ANO_INICIO, fim=datetime.now().year, **filtro)
    st, txt = baixar(url)
    ok = st == 200 and txt.lstrip("﻿").startswith("Documento;")
    log(f"{nome}: HTTP {st}, {len(txt) // 1024} KB{'' if ok else ' (não guardado)'}")
    if ok:
        open(os.path.join(SAIDA, nome), "w", encoding="utf-8").write(txt)
    return ok


def main():
    estado = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {}
    agora = datetime.now(timezone.utc)
    if estado.get("coletado_em") and agora - datetime.fromisoformat(estado["coletado_em"]) < INTERVALO:
        log(f"última coleta em {estado['coletado_em']}; nada a pedir hoje")
        return
    ok = exportar("projetos-executivo.csv", sit=0, tipo="Prefeito", autor=AUTOR_EXECUTIVO)
    for cod in SITUACOES_VETO:
        ok = exportar(f"vetos-{cod}.csv", sit=cod, tipo="Vereador", autor=0) and ok
    if ok:
        estado["coletado_em"] = agora.isoformat(timespec="seconds")
        estado["situacoes_veto"] = SITUACOES_VETO
        json.dump(estado, open(ESTADO, "w"), ensure_ascii=False, indent=1)
    log("fim")


if __name__ == "__main__":
    main()
