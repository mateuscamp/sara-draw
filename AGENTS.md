# ai-draw

Biblioteca de desenho vetorial em Python com saída suave e saída pixel art pixel-perfect.
Arquitetura: monólito modular, um pacote · Quantum: 1. ADRs em `docs/adr/`, plano em `PLANO.md`.

## Comandos

- Setup: `uv sync` — idempotente, sem rede depois da primeira vez.
- Testes: `uv run pytest` — headless, sem rede, suíte inteira < 10 s.
- Portão: `make check` (`scripts/portao.sh`). Rode antes de dizer "pronto" e mostre a saída;
  o hook Stop roda o mesmo com `--rapido`, e o CI o completo (ADR-0005).
- Ver uma cena (a partir da fase 1): `uv run ai-draw render <cena.py> --scale 10`; ao vivo
  (fase 2): `uv run ai-draw watch <cena.py>`; cores: `uv run ai-draw palette <cena.py> --near 10`.
- Exemplos em `examples/pixel/` (com `PALETTE` fechada: cor fora reprova) e `examples/smooth/`.
- `ai-draw lint <png|cena> --line '#rrggbb'`: defeitos de pixel art de qualquer imagem.
- README: a imagem e a tabela vêm de `docs/gallery/`; mudou a saída, rode
  `uv run ai-draw render docs/gallery/compare.py --scale 4` e `uv run python docs/gallery/scores.py`
  e cole a tabela (`tests/test_gallery.py` reprova o que estiver velho).
- Fitness functions: `tests/architecture/test_architecture.py`. Regra nova nasce com o teste
  que a mostra pegando uma violação plantada, visto falhar antes.

## Fronteiras (ADR-0001, ADR-0002)

- `errors/` (a família `DrawingError`) não importa nada; toda camada pode importá-la.
- `geometry/` só importa `errors/`; nada de terceiros.
- `grid/` só importa `errors/`; terceiros: só numpy.
- `pixel/` e `smooth/` importam `geometry/` e `grid/`; nunca um ao outro. Comum desce de camada.
- `io/` importa `grid/`; é o único que toca disco e o único que importa `PIL`.
- Proibido: `ImageDraw`, `Image.resize`. Ampliar é `Canvas.enlarged` (vizinho mais próximo).
- Canvas é `ndarray` uint8 (altura, largura, 4), RGBA, dono `grid/canvas.py`.
- Aritmética de array (comparar, reduzir, `np.pad`) só em `grid/arrays.py`, atrás de função
  com tipo exato: é o único arquivo do pacote dispensado do modo estrito. Nos testes, só
  `tests/support/freetype_oracle.py` (o fontTools não tem tipos).
- Pixel (x, y) amostrado em (x + 0,5, y + 0,5); intervalo semiaberto em y; y para baixo.
- Saída pixel: alfa só 0 ou 255.
- Import sempre absoluto (`from ai_draw.grid import canvas`); relativo reprova.
- Fronteira nova, dependência nova ou mudança de convenção exige ADR antes do código.

## Proveniência e licença (ADR-0003, ADR-0004)

- Todo `.py` começa com `# SPDX-License-Identifier: GPL-3.0-only`.
- Não copie asset, paleta nem constante dos projetos privados de origem; exemplos são novos.
- `notes/` é local e fica fora do git. O hook `pre-commit` reprova termo privado; nunca use `--no-verify`.

## Python (ADR-0005)

- Proibido mexer em `[tool.ruff]`, `[tool.basedpyright]`, `[tool.pytest]`, em `scripts/portao.sh`
  ou acrescentar ignore/exclude. Regra parece errada? Diga no relatório e pare: mudança é do Mateus, com ADR.
- Supressão só com regra e motivo na mesma linha: `# noqa: S603  # motivo: ...`,
  `# pyright: ignore[reportX]  # motivo: ...`; diretiva de arquivo com `# motivo:` na linha de cima.
  `cast` também é supressão: motivo na mesma linha.
- Erro de entrada: levante da família `ai_draw.errors` (`GeometryError`, `ColorError`,
  `CanvasError`, `SettingError`), com o valor recebido e o esperado. Proibido `except Exception`.
- `Any` de biblioteca (json, tomllib, numpy) para na borda.
- Dependência nova: `uv add`, com o que ela faz que a stdlib não faz e quem mantém, e ADR.

## Tipos e estilo

- basedpyright em `typeCheckingMode = "all"`, zero erro e zero aviso; Ruff com regras amplas.
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

- O teste conduz o desenho: ele nasce do comportamento pedido, antes de existir solução.
- Spike (ADR-0007): só para uma pergunta escrita antes, fora do repositório, apagado antes do
  primeiro teste. O relatório diz o que ele ensinou; não cole o código dele. Corrigir, medir e
  desfazer para ver o vermelho é spike: declare.
- Antes do commit, erro deliberado: troque a implementação por uma versão errada plausível.
  Nenhum teste falhou? Falta teste, com o seu próprio vermelho.
- Bug: primeiro o teste de regressão visto falhando, depois o fix, no mesmo commit.
- Código sem teste: teste de caracterização antes de mudar.
- O relatório da tarefa mostra a linha de falha do vermelho e o resumo do verde.
- Mudança em `src/` é `fix:`, `feat:` ou `refactor:`. `fix:` e `feat:` trazem teste e, no corpo,
  `Comando`, `Vermelho` e `Verde`. Vale para todo commit fora do `origin/main`.
- Proibido para ficar verde: mudar asserção, `skip`/`xfail`, apagar teste ou renomeá-lo para fora
  da coleta, asserção mais fraca, mockar o sujeito sob teste, `try/except` no teste. Teste
  errado? Diga e volte ao vermelho.
- Gabarito de raster pequeno é mapa de caracteres no próprio teste (`from_rows`), não PNG.

## Bancada de defeitos (driver ★)

- `tests/bench/` mede os detectores de `pixel/defects.py` sobre a bancada fixa de
  `tests/support/bench_cases.py`; o placar fica em `tests/bench/score.json` e só pode descer
  (catraca). Todo detector é 0 em pixel art limpa. O teste também compara com o placar do
  commit anterior: métrica que sobe ou some reprova, mesmo com o `score.json` editado à mão.
- Melhoria de pixel compara contra a saída atual com o mesmo número de etapas, nunca contra o raster cru.
- Baixar o placar: rode `uv run pytest tests/bench --update-score` e mostre o antes e o depois no relatório.

## Refatoração

- Muda estrutura, não comportamento: suíte verde antes e depois, nenhuma asserção alterada.
- Nunca refatorar e mudar comportamento no mesmo commit. Commit `refactor:` não muda o que um teste espera: só nomes.
- Passos pequenos; edite o arquivo existente, nunca o regenere inteiro. Só nos arquivos que a tarefa toca.
- Mover código entre camadas é decisão arquitetural: ADR antes.

## Testes

- F.I.R.S.T. Disco só via `tmp_path`; nada de rede, relógio ou aleatório sem semente.
- Caminhos previsíveis: `src/ai_draw/<camada>/<modulo>.py` ↔ `tests/<camada>/test_<modulo>.py`.
- Propriedade (Hypothesis, ADR-0006): no arquivo de teste do módulo, com o perfil do
  `tests/conftest.py` (determinístico, sem banco). Vista falhar como qualquer teste; a que
  descreve o que já existe, com o defeito plantado. O contraexemplo encolhido vira `@example`
  no commit da correção. Explorar mais: `--hypothesis-profile=explore` (o teste de perfil
  reprova nesse modo, de propósito).

## Estrutura

```
src/ai_draw/
  errors/     DrawingError e família    (não importa nada)
  geometry/   path, transform, midline  (Python puro)
  grid/       canvas, arrays, noise, rows, outline, compare, palette   (numpy)
  pixel/      scan, fill, thin, line, steps, stroke, rounded, cleanup, defects
  smooth/     coverage (fill), stroke    (referência: FreeType 32×, tests/support)
  io/         png, scene, live          (único com disco e PIL)
  cli.py
tests/<camada>/ · tests/architecture/ · tests/bench/ · tests/support/ (regras e bancada, importáveis)
docs/adr/
```

## Revisão antes do push (ADR-0007)

- Todo diff de `src/` ou `tests/`: a `/code-audit`, em modo auditoria, em contexto separado
  (subagente ou outra sessão), com o diff e os ADRs, nunca o raciocínio de quem implementou.
- Diff em `pixel/` ou numa fronteira de ADR: antes dela, a `/code-review`, no esforço da sessão,
  nunca abaixo de high, com o nível explícito. `ultra` só o Mateus dispara. A `/code-audit`
  confere cada achado.
- Achado só se corrige com o sim do Mateus.
