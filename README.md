# Americana Fiscaliza

O que cada vereador de Americana-SP faz: presença nas sessões, propostas e votos.
Só dados oficiais da Câmara Municipal, com link para a fonte em cada número. Sem nota, ranking ou opinião.

Site: https://americanafiscaliza.com.br/

- `site/` — o site (pasta `site/publico` é o que vai ao ar) e o gerador de dados. Veja `site/LEIAME.md`.
- `coletor/` — robôs de coleta leve no sistema da Câmara (SISCAM) e os dados brutos baixados.
- `.github/workflows/atualizar.yml` — atualiza e publica no GitHub Pages duas vezes por semana.

Coleta leve: o robô se identifica como "AmericanaFiscaliza", baixa poucas páginas por vez, com pausa,
e para sozinho se a Câmara bloquear (403/429). Para parar de vez, crie o arquivo `coletor/dados/PARAR`.

Achou um erro nos dados? Abra uma *issue* neste repositório.
