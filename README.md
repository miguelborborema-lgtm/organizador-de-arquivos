# Organizador de Arquivos

Aplicação em Python e Streamlit para conferir e organizar arquivos de um ZIP antes de gerar uma nova versão organizada.

## Funcionalidades

- Classificação por semana (segunda a domingo) e por categoria: documentos, planilhas, imagens, PDFs e outros formatos.
- Identificação de arquivos com conteúdo idêntico por SHA-256.
- Marcação manual de arquivos críticos e separação dos duplicados para revisão.
- Pesquisa por nome e filtros de semana, tipo e status.
- Seleção de arquivos individualmente ou por pasta, sem alterar o ZIP de origem.
- Exportação de um novo ZIP com as pastas organizadas e um `Relatorio_Geral.csv` com os arquivos incluídos e excluídos.

> **Importante:** as semanas são calculadas pela **data de modificação registrada em cada entrada do ZIP**, que pode ser diferente da data de criação ou download do arquivo. A marcação de duplicado sinaliza todos os arquivos com o mesmo conteúdo; a aplicação não elimina automaticamente nenhuma cópia.

## Executar localmente ou no GitHub Codespaces

Requer Python 3.10 ou superior.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Acesse a URL exibida pelo Streamlit, envie um ZIP e revise as pastas antes de exportar.

## Estrutura

```text
app.py                  # Interface Streamlit
core/organizer.py       # Análise, classificação e exportação
styles/app.css          # Estilos da interface
.streamlit/config.toml  # Tema e configuração de upload
tests/test_organizer.py # Testes automatizados
requirements.txt        # Dependências
```

## Testes

```bash
python -m unittest discover -s tests -v
```

## Limites e cuidados

A análise impõe limites de 2.000 arquivos, 100 MB por arquivo e 500 MB descompactados, além de verificações de caminhos inseguros e links simbólicos. O upload do Streamlit está configurado para até 200 MB. Esses limites não substituem uma auditoria de segurança para uso público em produção. O processamento ocorre na memória do processo Streamlit; evite enviar documentos sensíveis a instalações de terceiros.

## Tecnologias

Python, Streamlit, pandas e biblioteca padrão (`zipfile`, `hashlib`, `csv`, `datetime`).

## Evolução

Este repositório apresenta uma primeira versão funcional. Possíveis melhorias futuras incluem pré-visualização de arquivos e regras personalizadas de classificação.
