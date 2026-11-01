# 0002 — Dependências: numpy para a grade, Pillow só para arquivo

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** fidelidade às regras da pixel art

## Contexto

Escolha do Mateus em 31/10: numpy + Pillow. A alternativa recomendada era só a biblioteca
padrão. Num projeto anterior o Pillow foi medido e descartado para desenhar: o `rounded_rectangle`
deu 8 px diferentes da arte existente, e o resize padrão é bicúbico.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| Só biblioteca padrão (PNG por zlib) | zero dependência | laço Python por pixel, lento na saída suave; PNG próprio para manter | o Mateus escolheu numpy + Pillow |
| numpy | operação de grade vetorizada | uma dependência | sem leitura de formatos além do PNG próprio |
| numpy + Pillow | leitura e gravação de PNG/GIF/WebP prontas; grade rápida | ~25 MB de instalação | — |

## Decisão

numpy é o tipo da grade (ADR-0001). Pillow só lê e grava arquivo, em `io/`: nenhuma
primitiva de desenho, nenhum `resize` (ampliação é `grid.canvas.enlarge`, vizinho mais
próximo). `geometry/` fica em Python puro, sem numpy, porque o caminho tem dezenas de pontos
e o porte mantém a forma do Lua.

## Consequências

**Ganha:** ciclo ao vivo folgado em 256×256; menos código de formato para manter.

**Perde:** instalação maior; `numpy` traz tipos (`NDArray`) que exigem anotação cuidadosa
para o basedpyright estrito.

**Aceito conscientemente:** se o Pillow mudar a codificação, os bytes do PNG mudam; por isso
a comparação de teste é de pixels, não de bytes (regra de ofício: mesmo resultado sempre).

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| Pillow fora de `io/` | teste de fronteira | pytest / CI | import de `PIL` fora de `io/` |
| nenhum `ImageDraw` nem `resize` | teste de fronteira (nomes proibidos) | pytest / CI | aparecer em qualquer arquivo |
| numpy fora de `geometry/` | teste de fronteira | pytest / CI | `numpy` importado em `geometry/` |

Regra derivada no `AGENTS.md`: "Dependências". Dependência nova exige ADR.

## Emenda (31/10): dependências só de teste

**Status:** Aceito pelo Mateus em 31/10, ao começar a fase 7. Entram quando usadas:
`fonttools` e `freetype-py` na fase 7; `scikit-image` quando a bancada comparar com ele. Grupo `dev` do `pyproject.toml`, nunca instaladas com o pacote:
`fonttools` + `freetype-py` (oráculo da saída suave, fase 7) e `scikit-image` (linha de base
"pixel duro sem regras" da bancada, fase 3). Ganha: referência externa em vez de gabarito
feito por nós. Perde: `uv sync` mais pesado (~60 MB). Governança: o teste de fronteira
reprova import delas fora de `tests/`.
