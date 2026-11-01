#!/usr/bin/env bash
# Portão único do projeto: o mesmo comando para o agente (make check), o hook Stop e o CI.
# Aprova só se tudo passar; a primeira etapa que reprova encerra com a saída dela.
#   scripts/portao.sh            completo (make check e CI)
#   scripts/portao.sh --rapido   sem a auditoria de dependências, que precisa de rede (hook Stop)
# Copiado da skill python-on-rails (ADR-0005), com uma mudança: a etapa de supressão também pega
# as diretivas de arquivo do pyright (`# pyright: reportAny=false`), que o pyright não deixa
# levar texto na mesma linha; para elas, o motivo vai na linha de cima.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."
rapido=false
[[ "${1:-}" == "--rapido" ]] && rapido=true

etapa() { printf '\n== %s\n' "$1"; }

etapa "lock em dia com o pyproject"
uv lock --check

etapa "formatação"
# Settings come only from pyproject.toml: a stray .ruff.toml, pyrightconfig.json or pytest.ini
# would otherwise switch a step off (audit G2; tests/architecture also rejects such files).
uv run --locked ruff format --check --config pyproject.toml .

etapa "lint"
uv run --locked ruff check --config pyproject.toml .

etapa "supressão sem motivo"
# Supressão de linha: `# noqa: S603  # motivo: ...` ou `# pyright: ignore[regra]  # motivo: ...`.
# Diretiva de arquivo (`# pyright: reportAny=false`): `# motivo: ...` na linha de cima.
# Diretivas seguidas formam um bloco; basta o motivo na linha antes do bloco.
sem_motivo="$(git ls-files '*.py' | xargs -r awk '
  FNR == 1 { anterior = ""; aceita = 0 }
  /^# *pyright: *[a-zA-Z]/ && !/pyright: *ignore/ {
    aceita = (anterior ~ /motivo:/) || aceita
    if (!aceita) print FILENAME ":" FNR ": " $0 "   (diretiva de arquivo: motivo na linha de cima)"
    anterior = $0
    next
  }
  /noqa|pyright: *ignore|type: *ignore/ && !/motivo:/ { print FILENAME ":" FNR ": " $0 }
  { anterior = $0; aceita = 0 }
')"
if [[ -n "$sem_motivo" ]]; then
  printf '%s\n' "$sem_motivo"
  echo "Supressão sem '# motivo:'. Corrija o código ou escreva o motivo."
  exit 1
fi

etapa "tipos"
uv run --locked basedpyright -p pyproject.toml

etapa "testes"
uv run --locked pytest -c pyproject.toml

if ! $rapido; then
  etapa "dependências com vulnerabilidade conhecida"
  uv audit --locked --preview-features audit
fi

printf '\nPortão aprovado.\n'
