# 0007 — O ciclo de mudança segue o contrato da arquitetura-ai-first

**Status:** Aceito pelo Mateus em 04/11 ("Aceito, revisa")
**Data:** 2026-11-04
**Driver ★:** fidelidade às regras da pixel art

## Contexto

O `AGENTS.md` já traz o ciclo vermelho, verde e refatoração, e os commits de correção registram
os dois. Em 02/11 ficou visível o que ele não cobre. A linha do meio (5aa395f) nasceu em scripts
de rascunho, e a tangente (50ad9a6) foi corrigida, medida e desfeita só para ver o vermelho. O
vermelho foi real, mas confirmou uma solução pronta: quem conduziu o desenho foi o protótipo. E
os commits cd194d3..63e2054 foram para o `main`, que é público, sem revisão em contexto separado:
a regra de revisão só citava a fase 9.

Quantum atual: um pacote Python, sem dado próprio (ADR-0001). O trabalho vai direto no `main`,
sem PR.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| Deixar o `AGENTS.md` como está | nenhum custo | o protótipo continua decidindo antes do teste; push sem revisão | foi o que produziu o caso de 02/11 |
| Só regras escritas | custo mínimo | regra sem teste não sobrevive a três sessões | decisão sem enforcement é intenção |
| Regras escritas e fitness functions do que dá para conferir | enforcement barato, sem dependência | duas regras novas; o CI confere só o último commit | — |
| Mutation testing no CI | mede se os testes pegam mudança de comportamento | dependência nova e um job longo, contra o teto de 10 s da suíte | ainda sem evidência de teste sem dente; o erro deliberado faz o mesmo à mão em cada ciclo |

## Decisão

**Spike.** Protótipo é permitido para responder uma pergunta escrita antes. Fica fora do
repositório e é apagado antes do primeiro teste. O relatório diz o que ele ensinou, e o desenho
reescrito sai do teste, sem colar o código do spike.

**Erro deliberado.** Antes do commit, troca-se a implementação por uma versão errada plausível.
Se nenhum teste falhar, falta teste.

**Teste desligado.** Nenhum `skip` ou `xfail`, inclusive renomear teste para fora da coleta.

**Commit.** Mudança em `src/` é `fix:`, `feat:` ou `refactor:`. `fix:` e `feat:` trazem um teste
Python no mesmo commit e `Comando`, `Vermelho` e `Verde` no corpo. `refactor:` não muda o que um
teste espera: na diferença de `tests/`, só nomes podem mudar. Vale para todo commit ainda fora
do `origin/main`, porque o `fix:` e o `docs:` depois dele sobem juntos.

**Revisão antes do push.** Sem PR, ela roda antes do push, em contexto separado, com o diff e os
ADRs e sem o raciocínio de quem implementou.
- Todo diff de `src/` ou `tests/`: a `/code-audit`, em modo auditoria.
- Diff que toca `pixel/`, onde está o driver ★, ou uma fronteira de ADR: antes dela, a
  `/code-review`, no esforço da sessão e nunca abaixo de high, com o nível explícito. A
  `/code-audit` confere cada achado.
- Achado só se corrige com o sim do Mateus.

**Não entra agora:** mutation testing. A ordem também não se prova pelo histórico do git, o que
ensinaria a fabricar commits: a prova dela é o vermelho no relatório.

## Consequências

**Ganha:** o teste volta a conduzir o desenho, e nada chega ao `main` sem um segundo olhar.

**Perde:**
- a revisão custa tokens e tempo em cada push;
- spike apagado às vezes é reescrito do zero;
- o CI lê só o último commit, porque o `checkout` dele já está no `origin/main`: o intervalo
  inteiro é conferido no `make check` local, e ampliar o CI é mudança no workflow, do Mateus;
- a regra do `refactor:` compara strings, números e símbolos do diff, e não vê troca de palavra:
  `pytest.raises(A)` por `pytest.raises(B)`, `is True` por `is False`, `in` por `not in` passam,
  e também um assert sem símbolo apagado ou números trocados entre duas asserções;
- a regra do `refactor:` não lê doctest em `src/`, e um merge não mostra arquivos: em
  `pull_request`, ela não confere nada;
- a regra do `fix:` vê nomes de arquivo: `tests/conftest.py` conta como teste, um teste apagado
  também, e renomear para fora de `src/` passa. Fora de um repositório git, ela não reprova;
- `disabled_tests` não vê `async def _test_a`, `class _TestA`, prefixos como `disabled_test_`,
  `skipUnless`, `expectedFailure`, `SkipTest`, `__test__ = False`, `collect_ignore`,
  `getattr(pytest, ...)` nem arquivo renomeado, e acusa qualquer `.skip()`. Tudo isso fica para
  a `/code-audit`.

**Aceito conscientemente:** a regra do commit confere a presença da evidência, não a verdade
dela; isso fica para a `/code-audit`. Revisitar o mutation testing se uma regressão passar pela
suíte com o erro deliberado feito.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| teste desligado | `disabled_tests` em `tests/architecture` | `make check`, hook, CI | `skip`, `xfail`, `importorskip` ou função `_test_`, `xtest_`, `dont_test_` em `tests/` |
| commit com teste e evidência | `cycle_violations` sobre os commits fora do `origin/main` e o último | `make check`, hook; no CI, só o último | `src/` em outro tipo de commit, ou `fix:`/`feat:` sem teste ou sem Comando, Vermelho e Verde |
| refatoração pura | `cycle_violations` | `make check`, hook; no CI, só o último | `refactor:` que muda string, número ou símbolo em `tests/` |
| spike, erro deliberado e revisão | evidência no relatório | `/code-audit`, a cada push | o relatório não os mostra |

Regra derivada no `AGENTS.md`: seções "Ciclo de mudança (TDD)", "Refatoração" e "Revisão antes
do push".
