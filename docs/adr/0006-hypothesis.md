# 0006 — Hypothesis para as propriedades da geometria e da saída pixel

**Status:** Aceito pelo Mateus em 02/11 ("Aceito, implementa")
**Data:** 2026-11-02
**Driver ★:** fidelidade às regras da pixel art

## Contexto

O ADR-0005 (item 5) adiou a decisão para depois da fase 9 e listou candidatos a teste por
propriedade:
- a cobertura suave soma a área do polígono;
- a linha de 1 px de qualquer curva é conexa e sem L;
- `Transform.then` é associativa;
- o PNG faz ida e volta.

A fase 9 e o que veio depois mostraram de onde vêm os defeitos da saída pixel: de entradas que
ninguém escreveu à mão. Até aqui, quem os achou foram varreduras em grade, como 3.481 elipses
com raios de meio em meio pixel. Uma varredura só vê os pontos da sua grade.

**Protótipo de 02/11.** Feito numa cópia descartável do repositório, com o Hypothesis 6.170.14
só nela. Seis propriedades, perfil determinístico e 100 exemplos cada.
- Em segundos, achou dois defeitos fora do alcance das varreduras:
  - `ellipse(30, 30, 1.5, 10.026991306811004)` sai com 2 cantos em L;
  - o triângulo `(3, 30.875), (4, 31), (12, 23)`, de área 4,5, sai do `fill` com peça a mais
    ou pixel solto, embora o README prometa "thin parts kept joined".
- Uma amostra aleatória com semente, de 3.000 casos cada, mediu o tamanho dessas classes:
  - elipses com raios fora da grade: 160 com wobble (5%), 3 assimétricas e 1 com L. A
    varredura em grade dizia 0 wobble;
  - triângulos de área maior que 4: 106 em pedaços e 75 com pixel solto, quase sempre lascas
    finas.
- A ida e volta do PNG, a associatividade de `then` e a área da cobertura suave passaram.
- Na linha aberta, o encolhimento chegou a `x = 1.0000000000000002`: um ponto que o
  arredondamento a 9 casas trata como divisa de pixel, onde o sentido decide de propósito
  (B6, documentado). A propriedade precisa excluir esse caso; não é defeito.

A comparação foi feita contra o que existe hoje, com o mesmo número de etapas. Uma amostra
aleatória com semente também acha as classes. O que o Hypothesis acrescenta sobre ela:
- encolhe a falha ao menor exemplo (`cx=30, cy=30, rx=1.5`, em vez de `34.0, 36.0, 10.014,
  15.977`), e é esse exemplo que leva ao diagnóstico;
- puxa a geração para as bordas (inteiros, meios, 1e-16 de distância), que é onde a pixel art
  quebra;
- relata a falha num formato que se cola como teste.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| Exemplos e varreduras em grade, como hoje | zero dependência | não vê fora da grade | as 160 elipses com wobble passavam |
| Amostra aleatória com semente, escrita em cada teste | zero dependência | contraexemplo sem encolher, sem viés para as bordas, um laço à mão por propriedade | perde justamente o que leva do sintoma à causa |
| Hypothesis no grupo `dev` | encolhimento, bordas, relatório reproduzível | uma dependência, um cache em disco, menos de 1 s na suíte | — |

## Decisão

**Dependência.**
- `hypothesis>=6.170` entra no grupo `dev` do `pyproject.toml` e nunca vai no wheel.
- Ela traz uma única dependência transitiva, `sortedcontainers`.
- Traz tipos (`py.typed`): o protótipo passou no basedpyright `all` sem supressão.
- Mantenedores: David R. MacIver e Zac Hatfield-Dodds. Licença MPL-2.0. Como só roda no
  desenvolvimento, não é distribuída com o pacote GPL-3.0 (ADR-0003).

**Perfil único**, registrado e carregado em `tests/conftest.py`:
- `derandomize=True`: os mesmos exemplos em toda máquina e em todo CI, que é a regra de
  determinismo do `AGENTS.md`;
- `database=None`: nenhum exemplo guardado entre execuções;
- `deadline=None`: o tempo da máquina não decide o veredito;
- `max_examples=100`.

**O cache `.hypothesis/`.** Mesmo sem banco, o Hypothesis grava ali um cache das constantes do
código (visto no protótipo: 80 KB, com o próprio `.gitignore`). É cache de ferramenta, como o
`.pytest_cache`, e entra no `.gitignore` do projeto. O resultado não depende dele.

**Onde ficam as propriedades.**
- No arquivo de teste do módulo (`tests/<camada>/test_<modulo>.py`), nomeadas pela
  propriedade.
- Uma propriedade que usa `tmp_path` (a ida e volta do PNG) suprime o health check
  `function_scoped_fixture`, com `# motivo:` na linha: o arquivo é sobrescrito a cada
  exemplo.

**Ciclo.**
- A propriedade segue o TDD (`AGENTS.md`): é escrita, vista falhar na asserção, e só então vem
  a correção.
- O contraexemplo encolhido entra como `@example(...)` da propriedade, no mesmo commit da
  correção, para continuar sendo testado mesmo que a geração mude.
- Nenhuma propriedade entra com `xfail` ou `skip` (proibido pelo `AGENTS.md`). A que falha hoje
  entra com a sua correção.

**Primeiras propriedades.**
- Entram com este ADR as que passam hoje:
  - a ida e volta do PNG;
  - a associatividade de `then`;
  - a área da cobertura suave;
  - a linha aberta igual nos dois sentidos, fora das divisas de pixel.
- As que falham hoje viram tarefas, cada uma com a sua correção:
  - elipse com raios quaisquer, com a linha conexa, sem L, sem wobble e espelhada;
  - triângulo preenchido numa peça, sem pixel solto.

## Consequências

**Ganha:**
- uma rede para as classes de entrada que a grade não cobre;
- contraexemplos mínimos, que encurtam o diagnóstico;
- as invariantes do ADR-0005 escritas como teste.

**Perde:**
- uma dependência de desenvolvimento;
- menos de 1 s na suíte com 100 exemplos por propriedade (medido: ~0,4 s nas seis do protótipo; o teto é 10 s);
- um cache em `.hypothesis/`;
- propriedades mal escritas acham "defeitos" que são regras documentadas, como o B6, e
  precisam ser refinadas.

**Aceito conscientemente:**
- 100 exemplos determinísticos não exploram o espaço inteiro: são sempre os mesmos. Explorar
  mais é trabalho de sessão, com um perfil local de mais exemplos e sem `derandomize`, e o que
  for achado volta como `@example`.
- Mudar o código do teste muda os exemplos gerados, porque a semente vem dele: um teste que
  passava pode passar a achar um contraexemplo. É o comportamento desejado.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| perfil determinístico e sem banco | teste em `tests/architecture` que lê o perfil carregado | `make check`, hook, CI | o perfil ativo não tiver `derandomize=True` e `database=None` |
| Hypothesis só nos testes | a regra de terceiros por camada (ADR-0002), que já é lista de permissões | `make check`, hook, CI | `hypothesis` importado em `src/` |
| propriedade sem `xfail`/`skip` | `xfail_strict` e a revisão (`/code-review`, `/code-audit`) | CI, revisão | uma propriedade marcada para não reprovar |
| suíte dentro do teto | a regra de 10 s do `AGENTS.md` | revisão | a suíte passar de 10 s |

Regra derivada no `AGENTS.md`, seção "Testes": propriedade com o perfil do `conftest`; o
contraexemplo encolhido vira `@example` no commit da correção.
