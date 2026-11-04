#!/usr/bin/env bash
# Gere o branch "estado" (registo de modelos, previsões emitidas, relatórios do monitor),
# montado como worktree em ./estado.
#   scripts/estado.sh abrir            -> cria/obtém o branch e monta-o em ./estado
#   scripts/estado.sh guardar "msg"    -> commit + push do que mudou em ./estado
set -euo pipefail
acao="${1:?abrir|guardar}"

case "$acao" in
  abrir)
    if git ls-remote --exit-code --heads origin estado >/dev/null 2>&1; then
      git fetch --depth=1 origin estado
      git worktree add -B estado estado origin/estado
    else
      git worktree add --orphan -b estado estado
      printf '# Estado de produção\n\nGerido pelos workflows. Não editar à mão.\n' > estado/README.md
    fi
    ;;
  guardar)
    msg="${2:-Atualiza estado}"
    cd estado
    git add -A
    if git diff --cached --quiet; then echo "Estado sem alterações"; exit 0; fi
    git -c user.name="github-actions[bot]" -c user.email="41898282+github-actions[bot]@users.noreply.github.com" \
      commit -q -m "$msg"
    for i in 1 2 3 4; do
      git push -q origin estado && exit 0
      sleep $((2 ** i)); git pull -q --rebase origin estado || true
    done
    exit 1
    ;;
esac
