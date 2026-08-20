# Instalador do NMTBot

## Como gerar o instalador .exe

1. Baixe e instale o Inno Setup: https://jrsoftware.org/isdl.php
2. Abra o arquivo `NMTBot.iss` no Inno Setup Compiler
3. Clique em Build (ou Ctrl+B)
4. O instalador sera gerado em ` installer\Output\NMTBot-Setup-v1.0.0.exe`

## O que o instalador faz

- Verifica se o Python 3.13+ esta instalado
  - Se nao estiver: oferece link para python.org (nao instala nada sozinho)
- Copia os arquivos do projeto para `C:\Program Files\NMTBot`
- Cria atalhos no Menu Iniciar e na Area de Trabalho
- Apos instalar, mostra instrucoes para instalar dependencias

## Fluxo para o usuario final

1. Baixa e instala o Python manualmente (python.org)
2. Roda o instalador do NMTBot
3. Abre "Instalar Dependencias" no Menu Iniciar
   - Roda: py -m pip install -r requirements.txt
   - Roda: py -m playwright install chromium
4. Inicia o NMTBot pelo atalho

## Adicionar icone personalizado

Coloque um arquivo `icon.ico` nesta pasta (installer/) e descomente as linhas de icon no NMTBot.iss.
