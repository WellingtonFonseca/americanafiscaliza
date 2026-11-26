# Americana Fiscaliza — site

Site simples, para o morador ver no celular o que cada vereador de Americana-SP faz:
presença nas sessões, propostas e votos. Só dados oficiais, com link para a fonte em cada número.

## Pastas

- `publico/` — o site em si (HTML, CSS, JS, fotos e `dados/*.json`). É isto que vai para o GitHub Pages.
- `gerar_dados.py` — lê o HTML oficial guardado em `../coletor/dados/` e gera `publico/dados/`.
  Também faz as conferências automáticas; sai com erro se alguma falhar (o robô então não publica).
- `montar_previa.py` — junta tudo em `previa.html`, um arquivo só para abrir com dois cliques.
- `../.github/workflows/atualizar.yml` — o robô (coleta, gera, confere, publica).

## Como atualizar à mão

```
python3 -I ../coletor/coletar_sessoes.py ../coletor/dados          # até 3 páginas
python3 -I ../coletor/coletar_proposituras.py ../coletor/dados      # só quem falta
python3 -I gerar_dados.py ../coletor
python3 -I montar_previa.py
```

Para ver o site de verdade no computador: `cd publico && python3 -m http.server`, e abrir http://localhost:8000.

## Regras

- Mesma régua para todos: propostas contadas desde 01/01/2025 (mandato atual); grupos definidos em `CLASSIFICACAO_REGRAS` no `gerar_dados.py`.
- Rua, bairro e assunto dos pedidos são lidos do texto por programa: o site avisa que é leitura automática.
- Ausência registrada não é tratada como falta; sessão sem chamada não gera ausência para ninguém.
- Coleta leve: robô identificado como AmericanaFiscaliza, poucas páginas por execução, para em 403/429 ou se existir `coletor/dados/PARAR`.
