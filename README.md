# Gov Monitor — Indicadores por Área Governativa

Em produção: https://celine-mestre.github.io/gov-monitor/

Painel pesquisável que organiza indicadores e conjuntos de dados do Instituto Nacional de Estatística (INE) pelas 16 áreas governativas do XXV Governo Constitucional, com visualizações construídas a partir de filtros e ligação direta à API oficial do INE.

Secretaria-Geral do Governo · Direção de Serviços de Suporte à Decisão · Unidade de Pesquisa e Estatísticas.

## Novidades da v0.3

- Nova designação do produto: **Gov Monitor** (o protótipo chamou-se «Radar INE por Área Governativa» até setembro de 2026; a mudança abrange interface, README, scripts, robô de commits e ficheiros exportados).
- Catálogo e nota interna atualizados (dois códigos verificados: 0008074 e 0004167).

## Novidades da v0.2

- Cartões de área com ícones e cartões de indicador com miniatura de tendência (*sparkline*).
- KPI clicáveis com painel de detalhe (lista de indicadores, cobertura por área, estado da API e registo da recolha).
- Construtor de **indicadores compostos** por área: pesos, polaridade e normalização mín.–máx. 0–100 com média ponderada (nota metodológica visível no resultado).
- **Cruzamento de dois indicadores**: comparação em eixos independentes, diagrama de dispersão e correlação de Pearson com aviso de não causalidade.
- **O meu painel**: composição de painéis pessoais com indicadores, índices e cruzamentos; exportação e importação da configuração em JSON; impressão.
- Segundo código verificado na documentação oficial do catálogo da API: 0004167 — População residente (Estimativas anuais). Hiperligações permanentes por indicador (`xurl/indx/{código}/PT`).
- Novo script `scripts/gerar_catalogo.py`: descarrega o catálogo oficial de ~260 «Principais Indicadores» (`xml_indic.jsp?opc=3`) e propõe códigos por área governativa para validação humana — o caminho recomendado para pôr mais áreas a funcionar com API sem introduzir códigos não confirmados.

## O que faz

- **Pesquisa e filtros**: texto livre, área governativa, periodicidade e estado da ligação à API.
- **Catálogo por área governativa**: cada indicador tem fonte, periodicidade, unidade e, quando configurado, o código oficial do INE (*varcd*).
- **Visuais**: gráfico e tabela por indicador (Chart.js). As séries de demonstração estão sempre assinaladas com a marca «DEMONSTRAÇÃO».
- **Dados reais em três níveis**, por esta ordem:
  1. ficheiros `data/dados_{varcd}.json` recolhidos semanalmente pelo GitHub Actions;
  2. chamada direta do browser à API do INE (quando o servidor o permitir);
  3. série de demonstração embebida (recurso).
- **Acesso direto**: hiperligações para os dados JSON, para a metainformação e para a Base de Dados de Difusão do INE.

## A API do INE (referência)

Serviço REST de acesso livre e sem custos, documentado em www.ine.pt (Serviços : API):

- Dados: `https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd={codigo}&Dim1={tempo}&Dim2={geografia}&lang=PT`
- Metainformação: `https://www.ine.pt/ine/json_indicador/pindicaMeta.jsp?varcd={codigo}&lang=PT`

Exemplo oficial da documentação (taxa de criminalidade, código 0008074): `...pindica.jsp?op=2&varcd=0008074&Dim1=S7A2015&Dim2=200&Dim3=3&lang=PT`.

## Instalação e atualização no GitHub

O repositório em produção é `celine-mestre/gov-monitor`, com o GitHub Pages ativo (branch `main`, raiz). Para atualizar, substituir os ficheiros por upload (Add file : Upload files, que sobrepõe ficheiros com o mesmo nome) ou por `git push`.

O workflow `.github/workflows/atualizar-dados.yml` corre às segundas-feiras (06h30 UTC) e pode ser lançado manualmente no separador Actions. Grava `data/dados_*.json`, `data/meta_*.json` e `data/recolha.json`.

## Adicionar ou completar indicadores

1. Localizar o indicador em www.ine.pt : Base de Dados; no separador «Alterar condições de seleção», mudar de «Árvore» para «Códigos» para obter o código (*varcd*) e os códigos das dimensões.
2. Editar `data/catalogo.json`: preencher `varcd`, opcionalmente `dims_exemplo`, e mudar `verificado` para `true`.
3. Confirmar a estrutura das dimensões na metainformação (`pindicaMeta.jsp`) e em smi.ine.pt/Indicador.

Vêm verificados os códigos 0008074 (exemplo da documentação da API) e 0004167 (exemplo do catálogo oficial xml_indic.jsp). Os restantes estão propositadamente sem código para não introduzir referências não confirmadas.

## Logótipo

O `index.html` tem o espaço do logótipo preparado (`data:image/png;base64,SUBSTITUIR_PELO_BASE64`). Gerar o base64 a partir do ficheiro oficial `logo-sggov-pastilha.png` e substituir; enquanto não for substituído, a imagem fica simplesmente oculta.

## Limitações conhecidas

- A chamada direta do browser à API pode ser bloqueada por CORS; a recolha via GitHub Actions é o caminho previsto para produção.
- O intérprete da resposta segue a estrutura documentada (`[{IndicadorCod, IndicadorDsg, Dados:{período:[{geodsg, valor}]}}]`); indicadores com muitas dimensões podem exigir ajustes.
- As séries visíveis sem recolha são fictícias e estão marcadas como tal — não usar como dado oficial.

## Comparação com o Pordata (posicionamento)

O Pordata organiza por temas estatísticos; este radar organiza pela estrutura orgânica do Governo, permitindo a cada gabinete ver de imediato «os seus» indicadores, com rasto direto à fonte primária (API do INE, metainformação e data de extração em cada ficheiro recolhido).
