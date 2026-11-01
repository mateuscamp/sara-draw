# 0005 — Trilhos python-on-rails: portão único, apertos e desvios declarados

**Status:** Aceito
**Data:** 2026-11-01
**Driver ★:** testabilidade por agente (o agente fecha o ciclo sozinho e não afrouxa o portão)

## Contexto

Em 01/11 o projeto foi auditado com a skill python-on-rails (o Mateus pediu a análise). Medido
antes de mudar: lock em dia, `uv audit` sem vulnerabilidade, nenhum warning nos testes,
nenhum `type: ignore`. Faltavam o portão único (`make check`, hook Stop, CI), alguns apertos
de configuração que já passavam, motivo no formato `# motivo:` em 21 supressões, motivo em 3
`cast`, uma exceção de domínio no lugar de 27 `ValueError`, e o registro dos desvios que as
fases 0 a 8 foram fazendo sem ADR. O Mateus aceitou as quatro recomendações da auditoria.

Quantum: inalterado, um pacote.

## Decisão

1. **Portão único.** `make check` roda `scripts/portao.sh`: lock em dia, formatação, lint,
   supressão sem motivo, tipos, testes e `uv audit`. O hook Stop do Claude Code roda o mesmo
   script com `--rapido` (sem a auditoria, que precisa de rede) e o CI do GitHub roda o
   completo. Mudança em relação à skill: a etapa de supressão também pega as diretivas de
   arquivo do pyright (`# pyright: reportAny=false`), que a versão da skill não via; como o
   pyright não aceita texto depois da diretiva, o `# motivo:` vai na linha de cima do bloco.
2. **Apertos** (todos passavam no dia): `.python-version` 3.13; pytest com
   `filterwarnings = error`, `--strict-config` e `-ra`; basedpyright com `failOnWarnings`,
   `enableTypeIgnoreComments = false`, `reportIgnoreCommentWithoutRule` e
   `reportUnnecessaryTypeIgnoreComment`; complexidade máxima 8; saiu
   `reportUnusedFunction = "none"`, que não era preciso.
3. **Exceções.** Família `DrawingError(ValueError)` em `ai_draw/errors`: `GeometryError`,
   `ColorError`, `CanvasError`, `SettingError`; o `SceneError` do `io` também entra nela. Ser
   `ValueError` mantém quem já capturava `ValueError`. Para ser importável por todas as
   camadas, `errors` vira a camada de baixo de todas e não importa nada (emenda da tabela do
   ADR-0001).
4. **Desvios declarados** em relação ao padrão da skill:

| Padrão da skill | O projeto | Por quê | O que se perde |
|---|---|---|---|
| Ruff com lista explícita de regras | `select = ["ALL"]` | mais regras (D, CPY, INP, FBT...) desde a fase 0 | um upgrade do Ruff pode trazer regra nova e reprovar sem mudança de código; aí se corrige ou se declara aqui |
| sem `ignore` além de `TRY003` | ignora `COM812`, `CPY001`, `D203`, `D213`, `D401` | `COM812` briga com o `ruff format`; o SPDX é o aviso de licença e o teste de arquitetura cobra (ADR-0003); `D203`/`D213` são o par incompatível de `D211`/`D212`; docstring de valor lê melhor como substantivo | nada que o projeto use |
| `tests/**`: `S101`, `PLR2004`, `ANN401` | `tests/**`: `S101`, `PLR2004`, `D`, `INP001` | o nome do teste diz o que ele confere; `tests/` não é pacote | docstring em teste |
| — | `examples/**`: `INP001`; `docs/gallery/**`: `INP001`, `T201` | cenas e scripts rodados pelo `ai-draw` ou que imprimem a tabela do README | nada |
| basedpyright `recommended` | `all` | mais estrito | nada |
| `pythonVersion` igual ao `.python-version` | `pythonVersion = "3.11"`, `.python-version` 3.13 | biblioteca: os tipos são checados contra a versão mais velha que ela suporta; 3.13 é só o ambiente de desenvolvimento | a checagem não vê recurso exclusivo do 3.13, e é essa a ideia |
| sem dispensa de arquivo | `src/ai_draw/grid/arrays.py` e `tests/support/freetype_oracle.py` | numpy 2.5 tipa a aritmética de array como `Any`; o fontTools não tem tipos; cada dispensa fica contida num arquivo atrás de funções de tipo exato | o checker não olha dentro desses dois arquivos |
| import-linter | teste de AST em `tests/architecture` (ADR-0001) | já existia, cobre também terceiros por camada e ciclos, e mostra cada regra pegando violação plantada | uma ferramenta pronta e conhecida |
| config lida num módulo só | não há config | biblioteca sem variável de ambiente | — |

5. **Hypothesis**: decisão adiada para depois do `/code-audit` (fase 9). Candidatos a teste
   por propriedade: a cobertura suave soma a área do polígono; a linha de 1 px de qualquer
   curva é conexa e sem L; `Transform.then` é associativa; o PNG faz ida e volta.

## Consequências

**Ganha:** o mesmo veredito no agente, no hook e no CI; supressão sem motivo e warning
reprovam; quem usa a biblioteca pode capturar uma família de erro dela.

**Perde:** cada `make check` leva uns 15 s com o `uv audit`; o hook Stop prende o fim do turno
do agente enquanto o portão não passa; a camada `errors` é mais um item na tabela de
fronteiras.

**Aceito conscientemente:** o `select = ["ALL"]` fica, com o risco de upgrade descrito acima.
Revisitar se um upgrade do Ruff reprovar mais de uma vez por mês.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| portão inteiro | `scripts/portao.sh` | `make check`, hook Stop (`--rapido`), CI | qualquer etapa reprova |
| supressão com motivo | grep/awk do portão | idem | `noqa`, `pyright: ignore` ou diretiva de arquivo sem `# motivo:` |
| `errors` sob todas as camadas | `tests/architecture` | pytest | `errors` importa outra camada, ou camada fora da tabela |
| configuração só no `pyproject.toml` (auditoria G2, 01/11) | `tests/architecture` e o portão passando o `pyproject.toml` a cada ferramenta | `make check`, hook, CI | existe `.ruff.toml`, `ruff.toml`, `pyrightconfig.json`, `pytest.ini`, `tox.ini` ou `setup.cfg` |
| ninguém afrouxa o portão | `AGENTS.md` e `/code-audit` | revisão | mudança em `[tool.ruff]`, `[tool.basedpyright]` ou `[tool.pytest]` sem ADR |

Regra derivada no `AGENTS.md`: seção "Python".
