# 0004 — Porte só do núcleo genérico, reescrito, e nada de asset dos projetos de origem

**Status:** Proposto
**Data:** 2026-10-31
**Driver ★:** proveniência limpa

## Contexto

O ponto de partida são duas bibliotecas Lua do próprio autor, em projetos privados "todos os
direitos reservados": uma vetorial (caminho, transformação, rasterização por scanline, PNG) e
uma de grade para pixel art (canvas, mapa de caracteres, contorno, paleta). Como o autor é o
mesmo, ele pode relicenciar o código dele; o que não vem sem decisão é a identidade dos jogos
(sprites, paletas, constantes). O repositório do ai-draw é público, então os caminhos, os
commits e os detalhes desses projetos ficam em `notes/`, fora do git.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| Copiar e traduzir linha a linha | rápido | carrega nomes e decisões de jogo | acopla a lib aos jogos |
| Reescrever do zero sem olhar | sem herança | perde as soluções já medidas (seno exato, semiaberto em y) | desperdício |
| Reescrever o núcleo genérico guiado pelo Lua, com paridade de pixel | mantém o que foi medido, sem o específico | trabalho de porte | — |

## Decisão

Entram, reescritos em Python com API em inglês: caminho, transformação, preencher por
scanline, traço (como base a superar), canvas, `from_rows`, contorno, diff, recolor,
enlarge, levantamento e fusão de paleta. Ficam de fora: sprites, paletas, famílias de cor,
constantes e geradores específicos de jogo, e o compressor próprio (o Pillow grava). Os
exemplos e a galeria são novos.

## Consequências

**Ganha:** a fase 1 parte de um comportamento conhecido e testável por paridade.

**Perde:** a paridade só roda na máquina do autor (a fonte é privada), fora do CI.

**Aceito conscientemente:** depois da fase 1 a paridade é descartada de propósito: as fases
seguintes mudam pixel para melhor.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| nenhum termo privado no git | hook `pre-commit` e `commit-msg` locais com a lista de `notes/` | cada commit | termo da lista no conteúdo, no nome de arquivo ou na mensagem |
| nenhum asset de origem | revisão de PR que adiciona exemplo, paleta ou sprite | autor, a cada PR | algo além do núcleo genérico |
| paridade da fase 1 | script local em `notes/` | à mão | 1 pixel diferente |

Regra derivada no `AGENTS.md`: "Não copie asset, paleta nem constante dos projetos privados
de origem" e "nunca use `--no-verify`".
