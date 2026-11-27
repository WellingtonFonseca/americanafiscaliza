#!/usr/bin/env python3
"""Coletor leve de sessões da Câmara Municipal de Americana (SISCAM).

Cada execução baixa no máximo 15 páginas:
  1. a lista de sessões recentes (/sessoes), para descobrir a sessão mais nova;
  2. a sessão mais nova ainda não coletada;
  3. até 10 sessões antigas, recuando (histórico do mandato aos poucos; decisão do
     Wellington em 26/11/2026). Para ao chegar antes do início do mandato.

Regras combinadas:
  - o robô se identifica como AmericanaFiscaliza (não finge ser navegador);
  - pausa entre pedidos;
  - se o site responder 403 ou 429, ou se existir o arquivo PARAR, o coletor
    não faz nenhum pedido (cria PARAR no primeiro caso).

Uso: python3 -I coletar_sessoes.py [pasta_de_dados]
Saídas na pasta de dados: html/<id>.html, presenca.csv, votos.csv, sessoes.csv, estado.json
Só usa a biblioteca padrão do Python.
"""
import csv, html, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone

BASE = "https://americana.siscam.com.br"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas por semana)"
PAUSA = 10  # segundos entre pedidos
ANTIGAS_POR_EXECUCAO = 10  # sessões antigas guardadas por execução
MAX_TENTATIVAS_ANTIGAS = 13  # pedidos de sessões antigas por execução (inclui IDs que não existem)
INICIO_MANDATO = "2025-01-01"  # não recua para antes disso

PASTA = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados"))
HTML = os.path.join(PASTA, "html")
ESTADO = os.path.join(PASTA, "estado.json")
PARAR = os.path.join(PASTA, "PARAR")
os.makedirs(HTML, exist_ok=True)
pedidos = 0


def log(msg):
    linha = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    print(linha)
    with open(os.path.join(PASTA, "coleta.log"), "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def baixar(caminho):
    """Retorna (status, texto). Para tudo em 403/429."""
    global pedidos
    if pedidos:
        time.sleep(PAUSA)
    pedidos += 1
    req = urllib.request.Request(BASE + caminho, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            open(PARAR, "w").write(f"{e.code} em {caminho} - {datetime.now().isoformat()}\n")
            log(f"PARADO: {e.code} em {caminho}. Remova {PARAR} só depois de verificar.")
            sys.exit(2)
        return e.code, ""


def limpar(x):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", x)).strip()


def extrair(sid, s):
    """Extrai cabeçalho, presença e votos de uma página de sessão."""
    s = html.unescape(s)
    titulo = re.search(r'<h3 class="page-header">(.*?)</h3>', s, re.S)
    titulo = limpar(titulo.group(1)).replace("Sessões - ", "") if titulo else ""
    data = re.search(r"Data:</strong>\s*([\d/]+)", s) or re.search(r"(\d\d/\d\d/\d{4})", titulo)
    data = data.group(1) if data else ""
    sessao = [sid, titulo, data, f"{BASE}/Sessoes/Sessao/{sid}"]
    pres, votos = [], []
    ini, fim = s.find("Frequências</strong>"), s.find("Votações</strong>")
    if ini >= 0:
        for blk in s[ini:fim if fim > ini else len(s)].split("<h4>")[1:]:
            chamada = limpar(blk.split("</h4>")[0])
            for cat, nomes in re.findall(r"<strong>(Presentes|Ausentes)[^<]*</strong>\s*-\s*([^<]*)", blk):
                for n in nomes.split(","):
                    if n.strip():
                        pres.append([sid, titulo, data, chamada, n.strip(), cat[:-1].lower()])
    if fim >= 0:
        for blk in s[fim:].split('class="data-list-item')[1:]:
            corpo = blk.split("</ul>")[-1]
            mat = re.search(r"<strong>\s*(?:<a[^>]*>)?([^<]+)", corpo)
            mat = limpar(mat.group(1)) if mat else ""
            pdf = re.search(r'href="(https://americana\.siscam\.com\.br/arquivo\?Id=\d+)"', blk)

            def campo(k):
                m = re.search(r"<strong>" + k + r":</strong>(.*?)</p>", blk, re.S)
                return limpar(m.group(1)) if m else ""

            for cat, nomes in re.findall(r"<strong>([^<(:]+?)\s*\(\d+\)</strong>\s*-\s*([^<]*)", blk):
                for n in nomes.split(","):
                    if n.strip():
                        votos.append([sid, data, mat, campo("Autoria"), campo("Fase"), campo("Votação"),
                                      n.strip(), cat.strip(), campo("Resultado"), pdf.group(1) if pdf else ""])
    return sessao, pres, votos


def reconstruir_csvs():
    """Regera os CSVs a partir de todo o HTML guardado (idempotente)."""
    S, P, V = [], [], []
    for nome in sorted(os.listdir(HTML), key=lambda x: int(x.split(".")[0])):
        sid = nome.split(".")[0]
        a, b, c = extrair(sid, open(os.path.join(HTML, nome), encoding="utf-8").read())
        S.append(a); P += b; V += c
    for arq, cab, linhas in [
        ("sessoes.csv", ["sessao_id", "sessao", "data", "url"], S),
        ("presenca.csv", ["sessao_id", "sessao", "data", "chamada", "vereador", "situacao"], P),
        ("votos.csv", ["sessao_id", "data", "materia", "autoria", "fase", "tipo_votacao", "vereador", "voto", "resultado", "pdf_painel"], V),
    ]:
        with open(os.path.join(PASTA, arq), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f); w.writerow(cab); w.writerows(linhas)
    return len(S), len(P), len(V)


def salvar_sessao(sid, texto):
    with open(os.path.join(HTML, f"{sid}.html"), "w", encoding="utf-8") as f:
        f.write(texto)


def main():
    if os.path.exists(PARAR):
        log(f"Arquivo PARAR existe; nada foi pedido ao site. Conteúdo: {open(PARAR).read().strip()}")
        return
    estado = json.load(open(ESTADO)) if os.path.exists(ESTADO) else {"coletadas": [], "inexistentes": [], "proxima_antiga": None}
    ja = set(estado["coletadas"]) | set(estado["inexistentes"])
    ja |= {int(n.split(".")[0]) for n in os.listdir(HTML)}

    # 1. sessão mais nova
    st, lista = baixar("/sessoes")
    ids = sorted({int(i) for i in re.findall(r"/Sessoes/Sessao/(\d+)", lista)}, reverse=True)
    log(f"lista de sessões: HTTP {st}, {len(ids)} IDs ({ids[:3]}...)")
    nova = next((i for i in ids if i not in ja), None)
    if nova:
        st, txt = baixar(f"/Sessoes/Sessao/{nova}")
        log(f"sessão nova {nova}: HTTP {st}")
        if st == 200:
            salvar_sessao(nova, txt); ja.add(nova); estado["coletadas"].append(nova)
    else:
        log("nenhuma sessão nova")

    # 1b. sessões já guardadas que ainda não tinham acontecido (sem chamada nem votos):
    #     pede de novo, no máximo 2 por execução, só quando a data já passou.
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    refeitas = 0
    for sid in sorted(ja, reverse=True)[:30]:
        arq = os.path.join(HTML, f"{sid}.html")
        if refeitas >= 2 or sid == nova or not os.path.exists(arq):
            continue
        cab, pres, vts = extrair(str(sid), open(arq, encoding="utf-8").read())
        data_s = "-".join(reversed(cab[2].split("/"))) if cab[2] else ""
        if pres or vts or not data_s or data_s >= hoje:
            continue
        st, txt = baixar(f"/Sessoes/Sessao/{sid}")
        log(f"sessão {sid} de {data_s} estava sem chamada; pedida de novo: HTTP {st}")
        if st == 200 and "Sessões -" in txt:
            salvar_sessao(sid, txt)
        refeitas += 1

    # 2. sessões antigas (recuando)
    alvo = estado["proxima_antiga"] if estado["proxima_antiga"] is not None else (min(ja) - 1 if ja else (ids[-1] - 1 if ids else None))
    tent = guardadas = 0
    while alvo and alvo > 0 and tent < MAX_TENTATIVAS_ANTIGAS:
        if alvo in ja:
            alvo -= 1; continue
        tent += 1
        st, txt = baixar(f"/Sessoes/Sessao/{alvo}")
        log(f"sessão antiga {alvo}: HTTP {st}")
        if st == 200 and "Sessões -" in txt:
            d = extrair(str(alvo), txt)[0][2]  # dd/mm/aaaa
            data_s = "-".join(reversed(d.split("/"))) if d else ""
            if data_s and data_s < INICIO_MANDATO:
                log(f"sessão {alvo} é de {data_s}, antes do mandato; histórico completo")
                alvo = 0
                break
            salvar_sessao(alvo, txt); estado["coletadas"].append(alvo); alvo -= 1
            guardadas += 1
            if guardadas >= ANTIGAS_POR_EXECUCAO:
                break
            continue
        estado["inexistentes"].append(alvo); alvo -= 1
    estado["proxima_antiga"] = alvo
    estado["coletadas"] = sorted(set(estado["coletadas"]))
    estado["inexistentes"] = sorted(set(estado["inexistentes"]))
    estado["ultima_execucao"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    json.dump(estado, open(ESTADO, "w"), indent=1)
    n = reconstruir_csvs()
    log(f"fim: {pedidos} pedidos; total {n[0]} sessões, {n[1]} linhas de presença, {n[2]} linhas de voto")


if __name__ == "__main__":
    main()
