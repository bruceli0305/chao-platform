#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/self_upgrade_e2e_smoke.sh [--apply] [--no-watch] TASK_CODE "upgrade request"

Default mode is non-mutating and runs a self-upgrade dry-run.
Use --apply to execute the full first-version self-upgrade chain:
  doctor -> agents/skills validation -> self-upgrade execute/apply/branch/commit/push/PR/CI -> watch

Environment:
  CHAO_SELF_UPGRADE_WATCH_INTERVAL  CI watch interval seconds, default 30
  CHAO_SELF_UPGRADE_WATCH_ATTEMPTS  CI watch attempts, default 20
EOF
}

apply=false
watch=true
args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply)
      apply=true
      shift
      ;;
    --no-watch)
      watch=false
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ $# -gt 0 ]]; do
        args+=("$1")
        shift
      done
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ ${#args[@]} -lt 2 ]]; then
  usage
  exit 2
fi

task_code="${args[0]}"
request="${args[*]:1}"

echo "== Doctor =="
uv run python main.py doctor --json

echo "== Agent registry =="
uv run python main.py agents-validate --json

echo "== Skill registry =="
uv run python main.py skills-validate --json

echo "== Self-upgrade status command =="
uv run python main.py self-upgrade-status --help >/dev/null

echo "== Self-upgrade request =="
echo "task_code=${task_code}"
echo "apply=${apply}"
echo "request_chars=${#request}"

if [[ "${apply}" == "true" ]]; then
  echo "== Self-upgrade full chain =="
  uv run python main.py self-upgrade "${task_code}" "${request}" \
    --execute \
    --apply \
    --branch \
    --commit \
    --push \
    --create-pr \
    --check-ci

  if [[ "${watch}" == "true" ]]; then
    echo "== Self-upgrade CI watch =="
    uv run python main.py self-upgrade-watch "${task_code}" \
      --interval "${CHAO_SELF_UPGRADE_WATCH_INTERVAL:-30}" \
      --attempts "${CHAO_SELF_UPGRADE_WATCH_ATTEMPTS:-20}"
  fi
else
  echo "== Self-upgrade dry-run =="
  uv run python main.py self-upgrade "${task_code}" "${request}"
fi

echo "== Self-upgrade E2E smoke completed =="
