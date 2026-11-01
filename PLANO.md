# ai-draw — decisão 1: como estruturar a biblioteca vetorial com saída suave e pixel art

**Bottom line** — um pacote Python só (monólito modular) com cinco camadas de import em
sentido único (`geometry → grid → pixel | smooth → io`), a saída pixel feita primeiro e
governada por detectores de defeito no portão · inverte se a saída suave virar produto à
parte, com usuários que não querem a pixel (aí vale separar em dois pacotes).

Decisões de 31/10 (do Mateus): Python; API em inglês; numpy + Pillow; GPL-3.0; nome
`ai-draw` / `ai_draw`; tipos checados por basedpyright e Ruff; desenvolvimento por TDD
(contrato em `AGENTS.md`). Ainda sem repositório. Ao fim da implementação, `/code-audit`.

## O diferencial

Lib vetorial suave já existe (cairo, skia, aggdraw). O raro é levar vetor a pixel art
**sem os defeitos que o pixel artist evita**. Medido em 31/10 na cena de referência do código Lua
anterior, ampliada 10x: o coração (forma grande e cheia) sai bem; a estrela fina se parte em pedaços
soltos; a onda de traço 2 px engorda, afina e tem degraus desiguais. O pacote existe para
consertar isso, e o README mostra o antes e o depois.

Limite honesto: abaixo de uns 20 px nenhuma regra substitui a decisão pixel a pixel. O mapa
de caracteres (`from_rows`) é ferramenta de primeira classe para o detalhe pequeno; o vetor
fica com as formas médias e grandes, e os dois se compõem na mesma tela.

## Drivers

| ★ | Característica | Origem (frase do problema) | Como se mede |
|---|---|---|---|
| ★ | Fidelidade às regras da pixel art | "a estrela se parte, a onda engorda e afina" | detectores na bancada: pixels soltos, componentes a mais, cantos em L, degrau irregular, variação de espessura, assimetria; meta 0 em cada caso da bancada |
| | Determinismo | regra de ofício: "mesmo resultado sempre" | mesma cena renderizada 2x (e em 2 processos) dá o mesmo hash de pixels |
| | Testabilidade por agente | o código é escrito e verificado por agente | `uv run pytest` headless, sem rede, suíte inteira < 10 s |
| | Legibilidade do erro visual | "o pixel artist vê o defeito, o teste tem de ver" | gabarito em mapa de caracteres: a falha imprime o desenho esperado e o obtido |
| | Instalação simples | portfólio: quem testa instala e roda | `pip install ai-draw` sem compilador, em 3.11+, só wheels de numpy e Pillow |
| | Ciclo ao vivo | origem: "arte vetorial em tempo real" (MagmaDev) | cena de 256×256 redesenhada em < 200 ms após salvar o script |
| | Proveniência limpa | o código de origem é privado, todos os direitos reservados | nenhum asset, paleta ou constante de jogo de origem no repositório (revisão a cada PR de exemplo) |

## Quantum atual

Um só: o pacote `ai_draw`, instalado como biblioteca e CLI, sem dado próprio além dos
arquivos que o usuário passa e recebe. Não há rede, serviço nem banco; nenhum driver de
modularidade pede distribuir, então a conversa é só de módulos dentro do pacote.

## Dimensões emaranhadas

- **Representação da tela** — se o tipo do canvas mudar (lista de tuplas → `ndarray`),
  pixel, smooth, grid e io mudam juntos. Por isso é decidido agora: `ndarray` uint8 H×W×4,
  dono `grid/canvas.py`.
- **Convenção de amostragem** — se o centro do pixel deixar de ser (x+0,5, y+0,5), muda o
  preencher, a linha, o prender na grade e todo gabarito de teste. Fixada no ADR-0001.
- **Pillow** — se o desenho usar `ImageDraw`, a saída pixel herda as escolhas dele (um
  projeto anterior mediu 8 px diferentes no `rounded_rectangle`). Pillow fica preso em `io/`.
- **Licença** — GPL-3.0 obriga quem distribui um programa que usa a lib a abrir o programa
  sob GPL; a escolha muda quem pode adotar o pacote, não o código (ADR-0003).

## Opções

| Opção | Ganha | Perde | Driver afetado | Viável? |
|---|---|---|---|---|
| Pacote único, camadas com fronteira testada | um `pip install`, um portão, refatorar entre camadas é barato | a saída suave carrega a pixel junto | ★ e testabilidade | sim, escolhida |
| Dois pacotes (`ai-draw-core` + `ai-draw-pixel`) | quem quer só suave instala menos | dois releases, versões casadas, contrato público entre eles cedo demais | testabilidade, instalação | não: nenhum usuário pediu só a suave |
| Desenhar com `ImageDraw` do Pillow e corrigir depois | menos código | os defeitos nascem fora do nosso controle; o L e o degrau já vêm feitos | ★ | não |
| Núcleo em Lua (porte zero) chamado do Python | reaproveita 1.400 linhas | duas linguagens, runtime extra, contra a decisão "Python" | instalação | não: decisão tomada |

## Trade-off da escolhida

A pixel art desta lib cabe em telas de 16 a 256 px: numpy dá folga de sobra para o ciclo ao
vivo (< 200 ms) sem extensão em C. O custo é a saída suave nascer acoplada ao pacote pixel e
o tamanho da instalação (numpy ~20 MB + Pillow ~5 MB) para quem só quer gerar um PNG.

## Arquitetura

```
src/ai_draw/
  geometry/    Python puro, ponto flutuante, sem pixel
    path.py          move_to, line_to, quad_to, cubic_to, close, polygon, ellipse,
                     rect, rounded_rect, join, flatten
    transform.py     afim 2D (a matrix do SVG); seno/cosseno exatos em 90°
  grid/        a grade de pixels (numpy); porte de um kit de grade anterior, só o núcleo
    canvas.py        Canvas (ndarray H×W×4 uint8), paint, span, rect, copy, enlarged
    arrays.py        máscaras numpy: o único módulo com aritmética de array (tipagem)
    noise.py         speckle com semente obrigatória
    rows.py          from_rows / to_rows: sprite por mapa de caracteres + legenda
    outline.py       outline (1 px calculado), outlined (pelas 8 vizinhas)
    palette.py       levantar cores, pares quase iguais, famílias, fundir, quantizar
    compare.py       diff pixel a pixel, recolor
  pixel/       saída (c): o trabalho de verdade
    fill.py          scanline com amostra no centro (porte do rasterizador Lua anterior)
    line.py          linha 1 px pixel-perfect: sem L, degraus regulares, curva simétrica
    stroke.py        traço de N px por carimbo de pincel ao longo da linha de 1 px
    snap.py          prender vértices na grade
    cleanup.py       pixel solto, reconectar pontas, preservar parte fina
    defects.py       os detectores: medem, nunca mudam pixel
  smooth/      saída (b): cobertura fracionária
    coverage.py      área exata por célula, nonzero/evenodd
    stroke.py        traço por offset do caminho, junta e ponta
  io/          único lugar que toca disco e Pillow
    png.py           ler e gravar PNG
    scene.py         roda a cena (draw() -> Canvas), com a pasta dela importável
    live.py          vigia a cena, redesenha, o imv recarrega
  cli.py       ai-draw render | watch | diff | palette
tests/<camada>/test_<modulo>.py · tests/architecture/ · tests/bench/
docs/adr/
```

Importação permitida (ADR-0001, teste em `tests/architecture/`):

| Camada | Importa do pacote | Terceiros |
|---|---|---|
| `geometry` | nada | nenhum |
| `grid` | nada | numpy |
| `pixel` | geometry, grid | numpy |
| `smooth` | geometry, grid | numpy |
| `io` | grid | numpy, Pillow |
| `cli.py` | todas | — |

`pixel` e `smooth` não se importam: o que for comum desce para `geometry` ou `grid`.

## A saída pixel, peça por peça

1. **Preencher** (porte direto): amostra no centro do pixel, intervalo semiaberto em y,
   regras nonzero e evenodd. Base de comparação de tudo que vem depois.
2. **Linha de 1 px pixel-perfect**: a curva achatada vira caminho 8-conexo, e todo canto em
   L perde o pixel do meio (o filtro "pixel perfect" do Aseprite). Depois, os degraus de cada
   trecho viram corridas constantes (1:1, 1:2, 1:3...) ou alternadas de forma simétrica,
   nunca 2-3-2-4.
3. **Curva simétrica**: elipse e arco por octante, espelhados; o ponto flutuante não decide
   qual lado ganha o pixel.
4. **Traço de N px**: carimbo de um pincel fixo (quadrado ou disco já rasterizado) ao longo
   da linha de 1 px, em vez de quadrilátero por segmento. A espessura deixa de oscilar porque
   o pincel é o mesmo em todo ponto.
5. **Parte fina sem quebrar**: hipótese a medir, preencher = amostra no centro ∪ linha de
   1 px do próprio contorno. A linha é sempre conexa, então a ponta da estrela não se solta.
   Se engordar demais as formas grandes, vale só onde a forma é mais fina que ~2 px.
6. **Limpeza pós-raster**: tirar pixel solto, religar ponta separada por 1 px, desfazer L
   que sobrou entre peças.
7. **Grade e cor**: contorno de 1 px calculado, paleta fechada por famílias, quantizar sem
   pontilhado e sem meio-tom (alfa só 0 ou 255).

## Fitness functions

| Driver | Checagem | Tipo | Onde roda | Falha quando |
|---|---|---|---|---|
| ★ Fidelidade | `tests/bench/`: detectores sobre a bancada (estrela, onda 2 px, coração, círculos r 2–16, retas até 1:6); placar em `tests/bench/score.json` | holística, contínua | pytest / CI | algum detector piora em relação ao placar gravado (catraca: só desce), ou o caso que a fase fechou volta a ser > 0 |
| ★ Fidelidade | gabaritos em mapa de caracteres por função de `pixel/` | atômica, contínua | pytest | o pixel obtido difere do mapa |
| Fronteiras | `tests/architecture/test_imports.py`: a tabela de importação acima, sem ciclo | atômica, contínua | pytest / CI | camada importa fora da tabela; `PIL` fora de `io/` |
| Determinismo | renderizar a bancada 2x, inclusive em subprocesso com `PYTHONHASHSEED` diferente | atômica, contínua | pytest | hashes de pixel diferentes |
| Tipos | `basedpyright` em modo `all` (o mais estrito) sobre `src/` e `tests/`; `ruff check` + `ruff format --check` | atômica, contínua | portão local e CI | 1 erro ou aviso; `# type: ignore` / `noqa` sem motivo escrito na linha |
| TDD | o relatório de cada tarefa traz a linha do vermelho (falha na asserção) antes do verde | manual, a cada tarefa | agente, conferido pelo Mateus | teste novo sem vermelho mostrado |
| Testabilidade | duração da suíte | holística, contínua | CI | > 10 s |
| Legibilidade por agente | arquivo ≤ 400 linhas, função ≤ 40, nomes genéricos proibidos | atômica, contínua | pytest | qualquer violação fora da lista de isenções com ADR |
| Instalação | `uv build` + instalar a wheel num venv limpo e rodar `ai-draw render` num exemplo | holística, acionada | CI no release | falha de instalação ou de render |
| Ciclo ao vivo | render de cena 256×256 medido na bancada | holística, acionada | à mão antes do release | > 200 ms |
| Proveniência | revisão de todo PR que adiciona exemplo, paleta ou sprite | manual, a cada PR | Mateus | algo dos projetos de origem além do núcleo genérico |
| Paridade do porte (fase 1) | cena de referência rodada no `luajit` local vs o mesmo desenho em Python | holística, acionada | à mão, fora do CI (fonte privada) | 1 pixel diferente |

## Fases

| Fase | Entrega | Pronto quando |
|---|---|---|
| 0 | Esqueleto: `uv`, ruff, basedpyright, pytest, `tests/architecture/`, AGENTS.md, ADRs | portão verde num pacote vazio; o teste de fronteira visto falhar com um import proibido de propósito |
| 1 | geometry + `pixel/fill` + `io/png` + `ai-draw render` | paridade pixel a pixel com o Lua na cena de referência |
| 2 | grid (canvas, rows, outline, compare) + `ai-draw watch` com imv | sprite de exemplo novo sai por `from_rows` |
| 3 | `pixel/defects` + bancada + placar do antes | números de hoje gravados em `score.json` |
| 4 | linha 1 px pixel-perfect, degraus regulares, curva simétrica | L e degrau irregular em 0 na bancada |
| 5 | traço de N px por pincel, parte fina, limpeza | estrela em 1 componente, onda com espessura constante |
| 6 | paleta: famílias, fusão, quantização | cor fora da paleta reprova |
| 7 | smooth (cobertura exata, traço por offset) | coração e onda a ≤ 1/255 por canal do `FreeTypePen` |
| 8 | portfólio: README com antes/depois (contra `skimage.draw` e o raster cru), galeria, exemplos novos, `ai-draw lint` | tudo gerado por `ai-draw render` |
| 9 | `/code-audit` sobre o pacote inteiro | achados confirmados resolvidos ou registrados |

A saída pixel vem antes da suave: é o driver ★, e a suave reaproveita a geometria pronta.
Cada fase julga o ganho contra a saída da fase anterior, com o mesmo número de etapas dos
dois lados, nunca contra o raster cru.

## ADRs

- `docs/adr/0001-pacote-unico-em-camadas.md` · Aceito
- `docs/adr/0002-numpy-e-pillow.md` · Aceito
- `docs/adr/0003-licenca-gpl-3.md` · Aceito
- `docs/adr/0004-porte-dos-repositorios-privados.md` · Proposto

## Inspirações (pesquisa de 31/10)

Conferidas na página de cada projeto. O que copiar exige licença compatível com GPL-3.0;
o resto é leitura.

| Para | Projeto | Licença | Uso |
|---|---|---|---|
| `pixel/line` | Alois Zingl, "A Rasterizing Algorithm for Drawing Curves" (zingl.github.io/bresenham.html) | MIT | base de reta, elipse e Bézier inteiras, com a mesma família servindo à versão AA; pode portar |
| `pixel/line` | Pixelorama, `PixelPerfectDrawer` em `src/Classes/Drawers.gd` | MIT | remoção de L em janela de 3 pixels; pode portar |
| `pixel/line` | Superpixelator (Inglis, Vogel e Kaplan, NPAR 2012/2013; porte C++ DarkDefender/superpix) | porte GPL-3.0 | o mesmo problema, resolvido para linha: rasterizar vetor com as convenções do pixel artist. Ler os papers antes da fase 4 |
| `pixel/line` | Aseprite (`intertwiners.h`, `algo_line_perfect`) | EULA, não é open source | só leitura; nada de código |
| `pixel/stroke` | embedded-graphics (Rust) | MIT/Apache-2.0 | traço grosso pixel-exato com alinhamento dentro/fora/centro |
| `pixel/defects` | Kopf e Lischinski, "Depixelizing Pixel Art" (jerith/depixel) | MIT | heurísticas de ambiguidade diagonal (curvas, ilhas, pixels esparsos) para o detector de topologia 8-conexa |
| `pixel/defects` | SpriteKiln (LucasJRamos/spritekiln) | MIT | relatório de QA em números para agente (paleta, silhueta, clipping): o modelo do relatório da bancada |
| `pixel/fill` | exactextract | Apache-2.0 | fração exata de área por célula: hipótese "pinta se a área ≥ limiar" contra a amostra no centro, a medir na fase 5 |
| `smooth/coverage` | svgrasterize.py (aslpavel) | MIT | área com sinal acumulada e `np.cumsum` por linha, estilo font-rs; o modelo direto em numpy |
| `smooth/coverage` | fontTools `FreeTypePen` | MIT | oráculo de teste: o mesmo caminho pela FreeType, comparado ao nosso |
| bancada | scikit-image `skimage.draw` | BSD-3 | o "pixel duro sem regras" contra o qual o placar mostra o ganho |
| `grid/palette` | pyxel (`pal()`), pyxelate | MIT | API de paleta fechada e remapeamento |
| booleanas | skia-pathops | BSD-3 | união/diferença de caminhos para achar a silhueta antes do contorno; fica para depois da fase 8, se pedirem |

**A lacuna**, que é o argumento do README: nenhuma lib Python recebe vetor e entrega as duas
saídas. As suaves (cairo, Skia, AGG, Blend2D) sem AA só limiarizam; as de pixel duro (pyxel,
skimage) não têm Bézier nem regras; as regras existem só como pincel de editor (Aseprite,
Pixelorama) ou em pesquisa abandonada (Superpixelator, 2016). E **não existe validador
reutilizável de regras de pixel art**: o `pixel/defects` pode ser exposto como produto
(`ai-draw lint sprite.png`), funcionando até em arte feita à mão ou por IA.

## Fontes

Porte: código Lua anterior do autor, privado; caminhos e commits ficam em `notes/`, fora do
git. Ideia: vídeo do MagmaDev (YouTube CZ1IU-SkgTE,
14/10/2026), vetor suave em tempo de execução, sem código mostrado.

## Estado

- Fase 0 (31/10): esqueleto, portão e oito fitness functions em `tests/architecture/`.
- Fase 1 (31/10): `geometry` (path, transform), `grid` (canvas, rows), `pixel` (fill, stroke,
  rounded), `io/png` e `ai-draw render`. Paridade com a cena de referência em Lua: 0 pixel
  diferente em 64×64 (conferência local, fora do git). A saída reproduz os defeitos de
  partida: pontas da estrela soltas, onda de 2 px com espessura irregular.

- Fase 2 (31/10): `from_rows`, `outline` e `outlined`, `diff` e `recolor`, `speckle` com
  semente, `ai-draw watch` (imv, `--also`, `--once`, `--no-viewer`) e o primeiro exemplo
  novo, `examples/potion.py` (mapa de caracteres + contorno calculado). O numpy 2.5 tipa
  comparação de array como `Any`; a aritmética de array ficou em `grid/arrays.py`, a única
  dispensa do modo estrito, e o próprio basedpyright reprova a aritmética fora dele.

- Fase 3 (31/10): `pixel/defects.py` com sete detectores (`orphans`, `components`,
  `l_corners`, `uneven_steps`, `thickness_defects`, `wobble`, `asymmetric_cells`) e a bancada
  em `tests/support/bench_cases.py`, com o placar em `tests/bench/score.json` (catraca: só
  desce). O `wobble` nasceu na fase: o critério do pincel (bloco w×w, nenhum (w+1)²) dava 0
  na onda, cuja largura oscila 3, 2, 3 nas laterais. Placar de partida, só o que não é zero:

  | caso | defeitos |
  |---|---|
  | estrela evenodd | 1 componente a mais (ponta solta) |
  | círculos 1 px, r 3–16 | 168 cantos em L, 80 de wobble |
  | retas 1 px, 1:1 a 1:6 | 48 cantos em L, 30 de wobble (só as inclinações 1:2, 1:4 e 1:6) |
  | losango 1 px | 84 cantos em L, 16 de espessura (bolhas nos vértices) |
  | onda 2 px | 10 de wobble |

  Preenchimentos (coração, círculos r 2–16, estrela nonzero) saem limpos e simétricos.

- Fase 4 (31/10): `pixel/line.py` e `pixel/steps.py`; o `stroke` de 1 px passou a ser a
  linha nova. Cada ponto vira o pixel que o contém (na divisa, o do lado de dentro; na ponta
  de forma simétrica, os dois), Bresenham inteiro liga os pixels (sempre do menor para o
  maior, igual nos dois sentidos), o filtro de L tira primeiro o pixel mais longe da curva
  (decidir pela ordem do caminho girava o círculo) e preserva os vértices de canto, e os
  degraus fora de ordem trocam com o vizinho, decididos todos juntos a cada passada. Placar:
  cantos em L 168/84/48 → 0, wobble 80/30 → 0, espessura do losango 16 → 0; nada subiu.
  Observado montado: círculos grandes (r ≥ 11) leem um pouco octogonais, a passagem do topo
  plano para os degraus é brusca; nenhuma métrica mede redondeza ainda.

- Fase 5 (31/10): traço de N px por pincel ao longo da linha de 1 px (`pixel/stroke.py`): coluna
  de N onde a linha corre deitada, linha de N onde corre em pé, quadrado nos trechos a 45°; em
  largura par o px extra vai para fora da curva, e o anel sai centrado e espelhado. A parte
  fina (`pixel/cleanup.py`): quando as faixas do preenchimento dão mais de uma peça, as células
  do próprio contorno de 1 px que tocam duas peças religam a folga, e só elas. Dois ajustes
  vieram da fase, cada um com teste visto falhar antes: "fino" no detector passou a ser a
  célula cujas corridas transversais são mais curtas que a largura (o escalonado de um traço
  íngreme mantém 2 px por linha e deixou de contar), e o ponto que só encosta numa divisa de
  pixel fica do lado dos vizinhos (o fundo do vale fazia calombo). Placar: estrela evenodd
  1 → 0 componente a mais, onda de 2 px 10 → 0 de wobble; nada subiu. Tempo, cena 256×256:
  traço de 2 px num círculo de raio 100 em 41 ms, preenchimento em 12 ms.

## Próximo passo

Fase 6: paleta (levantar cores, pares quase iguais, famílias, fundir, quantizar sem
pontilhado); meta: cor fora da paleta reprova. Pendente da fase 4: círculos grandes leem
octogonais, e falta um detector de redondeza.
