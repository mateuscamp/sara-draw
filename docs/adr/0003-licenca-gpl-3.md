# 0003 — Licença GPL-3.0

**Status:** Aceito
**Data:** 2026-10-31
**Driver ★:** proveniência limpa (o código publicado tem de poder ser publicado)

## Contexto

Escolha do Mateus em 31/10: GPL 3.0. A recomendação era MIT. As dependências (numpy, BSD;
Pillow, MIT-CMU) são compatíveis com GPL-3.0.

## Alternativas consideradas

| Opção | Ganha | Perde | Por que não |
|---|---|---|---|
| MIT | adoção máxima, inclusive em jogo fechado | qualquer um fecha uma versão melhorada | o Mateus escolheu GPL |
| LGPL-3.0 | jogo fechado pode usar sem abrir o jogo; melhorias na lib voltam | regra de relink pouco clara em Python | não pedida |
| GPL-3.0 | toda versão distribuída com a lib fica aberta | jogo comercial fechado não pode embutir a lib | — |

## Decisão

**GPL-3.0-only**, a versão nomeada pelo Mateus (a variante "or-later" fica em aberto até ele
dizer; trocar de only para or-later antes do primeiro colaborador é grátis). Arquivo `LICENSE` com
o texto integral, `license = "GPL-3.0-only"` no `pyproject.toml` e cabeçalho SPDX em cada
arquivo de código.

## Consequências

**Ganha:** melhoria distribuída volta aberta.

**Perde:** quem distribui um programa que importa o `ai_draw` tem de distribuí-lo sob GPL;
isso afasta uso em jogo fechado, inclusive os do próprio Mateus se um dia forem fechados (o
dono do código pode relicenciar o que é só dele). As imagens geradas não são cobertas: saída
do programa não é obra derivada dele.

**Aceito conscientemente:** revisitar (LGPL ou MIT) se alguém pedir para usar em jogo fechado
e o Mateus quiser permitir; trocar exige o sim de todo colaborador externo que já tiver
contribuído, então quanto antes, mais barato.

## Governança

| O que verifica | Mecanismo | Onde roda | Falha quando |
|---|---|---|---|
| cabeçalho SPDX | teste de arquitetura | pytest / CI | arquivo `.py` sem `SPDX-License-Identifier: GPL-3.0-only` |
| licença no pacote | teste lê `pyproject.toml` | pytest | campo diferente de `GPL-3.0-only` |

Regra derivada no `AGENTS.md`: "Todo arquivo novo começa com o cabeçalho SPDX."
