
# Requisitos

- você deve construir um projeto de pipeline de webscraping em sites de fact-checking
- você deve escolher uma arquitetura simples, leve e eficiente para integrar diferentes soluções e bibliotecas pra cada agencia
- o projeto deve ter uma arquitetura padronizada de output de checagens encontradas
- as regras de negócio de seleção das notícias está definida diretamente na programação de cada spider da agencia
- o projeto deve ter um sistema de gerenciamento de log com structlog 
- o sistema deve armazenar os dados coletados com scraping localmente em formato de json que torne os dados rastreaveis pela execução
- o sistema deve ser capaz de não armazenar duas vezes a mesma notícia de uma mesma agência
- é útil que os dados de output tenham metadados funcionais pra recupração e cruzamento de informação
- você deve utilizar uv para package managment e ruff pra lint. 
- você deve construir uma pasta de /docs/ que contenha um arquivo de user_guide.md, design.md contendo um diagrama em mermaida da arquitetura
- as spiders devem poder ser agendadas ou executadas manualmente

## Agencias Fact-Check

lista de agências de fact-checking:
- https://www.reuters.com/fact-check/portugues/
- https://www.estadao.com.br/estadao-verifica/
- https://g1.globo.com/fato-ou-fake/
- https://www.aosfatos.org/
- https://www.agencialupa.org/checagem/
- https://checamos.afp.com/list
- https://noticias.uol.com.br/confere/
- https://projetocomprova.com.br/?filter=verificacao

