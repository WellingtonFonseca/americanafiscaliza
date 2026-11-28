#!/usr/bin/env python3
"""Passo 1 (rodar no computador do Wellington, internet do Brasil):
olha a página "Remuneração dos Servidores" do Portal da Transparência da
Prefeitura de Americana e guarda como ela é montada, para escrevermos o
script que baixa os meses sozinho.

Faz poucos pedidos (a página e até 6 arquivos de script dela), com pausa
de 5 segundos entre eles, com robô identificado. Não baixa planilha nenhuma.

Uso no WSL:  python3 olhar_portal_prefeitura.py
Saída:       W:\\Desktop\\AmericanaFiscaliza\\diagnostico-folha.zip  (mandar no chat)
"""
import html.parser, os, re, sys, time, urllib.parse, urllib.request, zipfile
from http.cookiejar import CookieJar

BASE = "https://transparencia.americana.sp.gov.br/"
PAGINA = BASE + "transparencia_index.php?p=servidor_remuneracao"
UA = "AmericanaFiscaliza/0.1 (robo civico; coleta leve de dados publicos, poucas paginas)"
PAUSA = 5
MAX_JS = 6

DESTINO = sys.argv[1] if len(sys.argv) > 1 else "/mnt/w/Desktop/AmericanaFiscaliza"
PASTA = os.path.join(DESTINO, "diagnosticos", "folha")
os.makedirs(PASTA, exist_ok=True)
abrir = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar())).open


def pedir(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": PAGINA})
    with abrir(req, timeout=60) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


class Ler(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms, self.links, self.js, self.botoes = [], [], [], []
        self._sel = None

    def handle_starttag(self, tag, a):
        a = dict(a)
        if tag == "form":
            self.forms.append({"action": a.get("action"), "method": a.get("method"), "id": a.get("id"), "campos": []})
        elif tag in ("input", "select", "textarea"):
            campo = {"tag": tag, "name": a.get("name"), "id": a.get("id"), "type": a.get("type"), "value": a.get("value"), "opcoes": []}
            (self.forms[-1]["campos"] if self.forms else self.botoes).append(campo)
            if tag == "select":
                self._sel = campo
        elif tag == "option" and self._sel is not None:
            self._sel["opcoes"].append(a.get("value"))
        elif tag == "a" and a.get("href"):
            self.links.append((a.get("href"), a.get("onclick")))
        elif tag == "script" and a.get("src"):
            self.js.append(a["src"])
        elif tag == "button" or a.get("onclick"):
            self.botoes.append({"tag": tag, "id": a.get("id"), "onclick": a.get("onclick"), "class": a.get("class")})

    def handle_endtag(self, tag):
        if tag == "select":
            self._sel = None


def main():
    print(f"Pedindo {PAGINA} ...")
    st, tipo, corpo = pedir(PAGINA)
    open(os.path.join(PASTA, "pagina.html"), "wb").write(corpo)
    txt = corpo.decode("utf-8", "replace")
    p = Ler(); p.feed(txt)
    linhas = [f"HTTP {st} {tipo} {len(corpo)} bytes", "", "== FORMULÁRIOS =="]
    for f in p.forms:
        linhas.append(f"form action={f['action']} method={f['method']} id={f['id']}")
        for c in f["campos"]:
            op = f" opções={c['opcoes'][:15]}" if c["opcoes"] else ""
            linhas.append(f"   {c['tag']} name={c['name']} id={c['id']} type={c['type']} value={c['value']}{op}")
    linhas += ["", "== CAMPOS E BOTÕES FORA DE FORMULÁRIO =="] + [str(b) for b in p.botoes[:80]]
    linhas += ["", "== LINKS QUE PARECEM EXPORTAÇÃO =="]
    linhas += [f"{h}  onclick={o}" for h, o in p.links if re.search(r"xls|excel|export|planilha|csv|remunera", (h or "") + (o or ""), re.I)]
    linhas += ["", "== TRECHOS DE SCRIPT DA PÁGINA COM ajax/xls/export =="]
    linhas += sorted(set(re.findall(r".{0,120}(?:ajax|\.xls|export|excel|\.php\?).{0,160}", txt, re.I)))[:80]
    js = [urllib.parse.urljoin(PAGINA, s) for s in p.js]
    js = [u for u in js if urllib.parse.urlparse(u).netloc == urllib.parse.urlparse(BASE).netloc][:MAX_JS]
    for i, u in enumerate(js):
        time.sleep(PAUSA)
        try:
            _, _, c = pedir(u)
            open(os.path.join(PASTA, f"script{i + 1}.js"), "wb").write(c)
            linhas.append(f"[script{i + 1}.js] {u}")
        except Exception as e:
            linhas.append(f"[falhou] {u}: {e}")
    open(os.path.join(PASTA, "resumo.txt"), "w", encoding="utf-8").write("\n".join(linhas))
    zipado = os.path.join(DESTINO, "diagnostico-folha.zip")
    with zipfile.ZipFile(zipado, "w", zipfile.ZIP_DEFLATED) as z:
        for n in os.listdir(PASTA):
            z.write(os.path.join(PASTA, n), n)
    print(f"Pronto: {len(p.forms)} formulário(s), {len(js)} script(s).")
    print(f"Mande este arquivo no chat: {zipado}")


if __name__ == "__main__":
    main()
