# ai-draw

Biblioteca de desenho vetorial em Python com saída suave e saída pixel art pixel-perfect.
Arquitetura: monólito modular, um pacote · Quantum: 1. ADRs em `docs/adr/`, plano em `PLANO.md`.

## Comandos

- Setup: `uv sync` — idempotente, sem rede depois da primeira vez.
- Testes: `uv run pytest` — headless, sem rede, suíte inteira < 10 s.
- Portão (rodar antes de declarar qualquer tarefa concluída):
  `uv run ruff format --check && uv run ruff check && uv run basedpyright && uv run pytest`
- Ver uma cena (a partir da fase 1): `uv run ai-draw render <cena.py> --scale 10`; ao vivo
  (fase 2): `uv run ai-draw watch <cena.py>`.
- Fitness functions: `tests/architecture/test_architecture.py`. Regra nova nasce com o teste
  que a mostra pegando uma violação plantada, visto falhar antes.

## Fronteiras (ADR-0001, ADR-0002)

- `geometry/` não importa nada do pacote nem de terceiros.
- `grid/` não importa nada do pacote; terceiros: só numpy.
- `pixel/` e `smooth/` importam `geometry/` e `grid/`; nunca um ao outro. Comum desce de camada.
- `io/` importa `grid/`; é o único que toca disco e o único que importa `PIL`.
- Proibido: `ImageDraw`, `Image.resize`. Ampliar é `grid.canvas.enlarge` (vizinho mais próximo).
- Canvas é `ndarray` uint8 (altura, largura, 4), RGBA, dono `grid/canvas.py`.
- Pixel (x, y) amostrado em (x + 0,5, y + 0,5); intervalo semiaberto em y; y para baixo.
- Saída pixel: alfa só 0 ou 255.
- Import sempre absoluto (`from ai_draw.grid import canvas`); relativo reprova.
- Fronteira nova, dependência nova ou mudança de convenção exige ADR antes do código.

## Proveniência e licença (ADR-0003, ADR-0004)

- Todo `.py` começa com `# SPDX-License-Identifier: GPL-3.0-only`.
- Não copie asset, paleta nem constante dos projetos privados de origem; exemplos são novos.
- `notes/` é local e fica fora do git. O hook `pre-commit` reprova termo privado; nunca use `--no-verify`.

## Tipos e estilo

- basedpyright em `typeCheckingMode = "all"`, zero erro e zero aviso; Ruff com regras amplas.
- `# type: ignore` e `# noqa` só com o código da regra e o motivo na mesma linha.
- Tipos explícitos em toda função pública; sem `Any`. Arrays com `NDArray[np.uint8]` e afins.
- Funções de 4 a 20 linhas (teto 40); arquivo ≤ 400 linhas.
- Código em inglês: nomes, docstrings, comentários e mensagens de erro. Documentos
  (`PLANO.md`, ADRs, este arquivo) em português.
- Proibidos como nome inteiro: `data`, `info`, `handler`, `manager`, `helper`, `utils`,
  `process`, `base`, `common`, `item`, `obj` (`base_color` pode).
- Early return; no máximo 2 níveis de indentação.
- Exceção com o valor recebido e o formato esperado: `f"radius={r!r}, expected > 0"`.
- Determinismo: aleatório só com semente recebida; ordenação sempre com desempate.

## Comentários

- Escreva o PORQUÊ. Docstring pública: intenção + um exemplo.
- Não apague comentário de proveniência em refactor; cite ADR ou commit quando a linha existe por causa dele.

## Ciclo de mudança (TDD)

1. Vermelho: um teste, um comportamento, nomeado pelo comportamento. Rode e veja falhar NA
   ASSERÇÃO — `ImportError`, `NameError` ou fixture quebrada não contam.
2. Verde: o mínimo de código que passa, sem editar o teste. Rode a suíte inteira.
3. Refatore com a suíte verde. Depois o portão e o commit.

- Bug: primeiro o teste de regressão visto falhando, depois o fix, no mesmo commit.
- O relatório da tarefa mostra a linha de falha do vermelho e o resumo do verde.
- Proibido para ficar verde: mudar asserção, `skip`/`xfail`, apagar teste, asserção mais
  fraca, mockar o sujeito sob teste, `try/except` no teste. Teste errado? Diga e volte ao vermelho.
- Gabarito de raster pequeno é mapa de caracteres no próprio teste (`from_rows`), não PNG.

## Bancada de defeitos (driver ★)

- `tests/bench/` mede os detectores de `pixel/defects.py` sobre a bancada fixa; o placar
  fica em `tests/bench/score.json` e só pode descer (catraca).
- Melhoria de pixel compara contra a saída atual com o mesmo número de etapas, nunca contra o raster cru.
- Baixar o placar: rode `uv run pytest tests/bench --update-score` e mostre o antes e o depois no relatório.

## Refatoração

- Muda estrutura, não comportamento: suíte verde antes e depois, nenhuma asserção alterada.
- Nunca refatorar e mudar comportamento no mesmo commit.
- Passos pequenos; edite o arquivo existente, nunca o regenere inteiro.
- Mover código entre camadas é decisão arquitetural: ADR antes.

## Testes

- F.I.R.S.T. Disco só via `tmp_path`; nada de rede, relógio ou aleatório sem semente.
- Caminhos previsíveis: `src/ai_draw/<camada>/<modulo>.py` ↔ `tests/<camada>/test_<modulo>.py`.

## Estrutura

```
src/ai_draw/
  geometry/   path, transform           (Python puro)
  grid/       canvas, rows, outline, palette, compare   (numpy)
  pixel/      fill, line, stroke, snap, cleanup, defects
  smooth/     coverage, stroke
  io/         png, live                 (único com disco e PIL)
  cli.py
tests/<camada>/ · tests/architecture/ · tests/bench/
docs/adr/
```

## Ao terminar a implementação

- Rode a skill `/code-audit` sobre o pacote inteiro (fase 9 do plano).
