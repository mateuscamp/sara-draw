# 0001 — O ai-draw é um pacote só, em cinco camadas de import em sentido único

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** fidelidade às regras da pixel art

## Contexto

Biblioteca vetorial em Python com saída suave e saída pixel art, para portfólio. O núcleo
nasce do porte de código Lua anterior do próprio autor, não publicado. A saída pixel
é o diferencial: o raster tudo-ou-nada em resolução baixa parte formas finas e deixa traço de
espessura irregular (medido em 31/10 na cena de referência do código anterior).

Quantum atual: um, o pacote `ai_draw` (biblioteca + CLI), sem dado próprio.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| Dois pacotes (núcleo + pixel) | instalação menor para quem só quer suave | dois releases casados, contrato público cedo | ninguém pediu só a suave |
| Desenhar com `ImageDraw` do Pillow | menos código | defeitos nascem fora do nosso controle | contra o driver ★ |
| Pacote único em camadas | um portão, refatorar entre camadas é barato | suave e pixel instalam juntas | — |

## Decisão

Um pacote, `src/ai_draw/`, com as camadas `geometry` (Python puro), `grid` (canvas numpy),
`pixel` e `smooth` (as duas saídas, que não se importam entre si) e `io` (o único lugar que
toca disco e Pillow); `cli.py` costura. A tabela de importação permitida mora no `PLANO.md`
e no teste de fronteira.

Convenções que todas as camadas compartilham e por isso ficam fixas aqui:

- Origem no canto superior esquerdo, y para baixo; ângulo positivo gira no sentido horário.
- O pixel (x, y) é amostrado no ponto (x + 0,5, y + 0,5); intervalo semiaberto em y.
- Canvas = `ndarray` uint8 de forma (altura, largura, 4), RGBA não pré-multiplicado, dono
  `grid/canvas.py`.
- Saída pixel: alfa só 0 ou 255.

## Consequências

**Ganha:** um `pip install`, uma suíte, e a saída pixel com controle de cada pixel.

**Perde:** quem quer só a saída suave instala a pixel junto; mudar a convenção de amostragem
depois invalida todo gabarito de teste.

**Aceito conscientemente:** revisitar se a saída suave ganhar usuários próprios que não usam
a pixel.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| tabela de importação, sem ciclo | `tests/architecture/test_imports.py` (AST) | pytest / CI | import fora da tabela |
| Pillow só em `io/` | mesmo teste | pytest / CI | `PIL` importado fora de `io/` |
| alfa binário na saída pixel | teste na bancada | pytest | algum alfa entre 1 e 254 |

Regra derivada no `AGENTS.md`: seção "Fronteiras".
