#!/usr/bin/env bash
# Hook Stop do Claude Code: roda `scripts/portao.sh --rapido` quando qualquer arquivo do
# repositório mudou desde a última aprovação, e devolve a falha ao agente (exit 2) antes de ele
# dizer que terminou. Registro em .claude/settings.json do projeto:
#   {"hooks": {"Stop": [{"hooks": [{"type": "command",
#     "command": "\"$CLAUDE_PROJECT_DIR\"/scripts/hook_portao.sh", "timeout": 300}]}]}}
# Copiado da skill python-on-rails (adaptado do hook da ai-first-godot). ADR-0005.
set -uo pipefail

raiz="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
entrada="$(cat)"
# Na segunda parada seguida o agente já recebeu a falha uma vez: não prende a sessão em laço.
if python3 -c 'import json,sys; sys.exit(0 if json.loads(sys.argv[1]).get("stop_hook_active") else 1)' \
    "$entrada" 2> /dev/null; then
  exit 0
fi

cd "$raiz" || exit 0
# Impressão digital: commit atual, diff não commitado e arquivos novos, de qualquer tipo. O portão
# também lê score.json, README, PNG e configs (auditoria M9); --binary distingue dois PNG.
digital="$({
  git rev-parse HEAD 2> /dev/null
  git diff HEAD --binary 2> /dev/null
  git ls-files --others --exclude-standard -z | xargs -0 -r sha1sum
} | sha1sum | cut -d' ' -f1)"
projeto="$(basename "$(git rev-parse --show-toplevel 2> /dev/null || echo "$raiz")")"
marca="$HOME/.cache/$projeto-portao/$(basename "$raiz").aprovado"
[[ -f "$marca" && "$(cat "$marca")" == "$digital" ]] && exit 0

if saida="$(scripts/portao.sh --rapido 2>&1)"; then
  mkdir -p "$(dirname "$marca")"
  printf '%s\n' "$digital" > "$marca"
  exit 0
fi
{
  echo "Portão reprovou (scripts/portao.sh --rapido). Corrija antes de dizer que terminou:"
  printf '%s\n' "$saida" | tail -60
} >&2
exit 2
