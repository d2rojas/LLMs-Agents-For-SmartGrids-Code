#!/usr/bin/env bash
# Run the full PFAgent benchmark matrix behind Table \ref{tab:pf_protocol}:
# 14 methods x SYSTEMS, one (method, case) invocation of benchmarks/evaluate_llms.py
# each, written to OUT/<method-slug>/<case>/report.json. Idempotent: an existing
# report.json is skipped unless --force. Fill the table afterwards with
#   .venv/bin/python benchmarks/fill_table.py OUT
#
# Usage: scripts/run_pf_matrix.sh [--model P:M] [--out DIR] [--systems "case14 ..."]
#                                 [--n 40] [--k 1] [--max-rounds 8] [--seeds 1]
#                                 [--only "rule_based,react"] [--dry-run] [--force]
# Every option can also be given as an environment variable (MODEL, OUT, SYSTEMS,
# N, K, MAXROUNDS, SEEDS, PRICING); flags win over the environment.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"

MODEL="${MODEL:-openai:gpt-4o-mini}"
OUT="${OUT:-}"
SYSTEMS="${SYSTEMS:-case14 case30 case57 case118}"
N="${N:-40}"
K="${K:-1}"
MAXROUNDS="${MAXROUNDS:-8}"
SEEDS="${SEEDS:-1}"
PRICING="${PRICING:-pricing.json}"
DRY_RUN=0
FORCE=0
ONLY=""

# Methods of the table, in table order (react/plan_act gated variants are the ablation).
ALL_METHODS=(
  llm_only:structured llm_only:few_shot llm_only:cot llm_only:rag
  single_call:structured single_call:few_shot single_call:cot single_call:rag
  rule_based react react_nogate plan_act plan_act_nogate pfagent
)

# Rough tokens per item (prompt, completion) used only for the --dry-run cost estimate.
#   llm_only    : one call carrying the case description            ~6000 / 500
#   single_call : one function-calling round with the tool schemas  ~4000 / 400
#   agents      : ~5 LLM calls of ~4k context each                  ~20000 / 1500
#   rule_based  : no LLM                                             0 / 0
tokens_guess() {
  case "$1" in
    llm_only:*)    echo "6000 500" ;;
    single_call:*) echo "4000 400" ;;
    rule_based)    echo "0 0" ;;
    *)             echo "20000 1500" ;;
  esac
}

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model)      MODEL="$2"; shift 2 ;;
    --out)        OUT="$2"; shift 2 ;;
    --systems)    SYSTEMS="$2"; shift 2 ;;
    --n)          N="$2"; shift 2 ;;
    --k)          K="$2"; shift 2 ;;
    --max-rounds) MAXROUNDS="$2"; shift 2 ;;
    --seeds)      SEEDS="$2"; shift 2 ;;
    --pricing)    PRICING="$2"; shift 2 ;;
    --only)       ONLY="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --force)      FORCE=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

MODEL_SLUG="$(printf '%s' "$MODEL" | tr ':./ ' '____')"
OUT="${OUT:-benchmarks/results_matrix_${MODEL_SLUG}}"

# --only: comma/space separated; a bare group name (llm_only, single_call) selects all its strategies.
METHODS=()
if [[ -n "$ONLY" ]]; then
  for want in $(printf '%s' "$ONLY" | tr ',' ' '); do
    hit=0
    for m in "${ALL_METHODS[@]}"; do
      if [[ "$m" == "$want" || "$m" == "$want:"* ]]; then METHODS+=("$m"); hit=1; fi
    done
    if [[ $hit -eq 0 ]]; then
      echo "Unknown method in --only: $want (choose from: ${ALL_METHODS[*]})" >&2; exit 2
    fi
  done
else
  METHODS=("${ALL_METHODS[@]}")
fi

if [[ $DRY_RUN -eq 0 && ! -x "$PY" ]]; then
  echo "Project venv not found at $PY (create it with: python -m venv .venv && pip install -r requirements.txt)" >&2
  exit 1
fi

echo "# model=$MODEL out=$OUT systems=[$SYSTEMS] N=$N K=$K max_rounds=$MAXROUNDS seeds=$SEEDS pricing=$PRICING"
echo "# methods (${#METHODS[@]}): ${METHODS[*]}"

n_sys=0; for _ in $SYSTEMS; do n_sys=$((n_sys + 1)); done
llm_items=0; all_items=0; prompt_tok=0; compl_tok=0
planned=0; skipped=0; failed=0; failures=()

for m in "${METHODS[@]}"; do
  slug="${m//:/_}"
  read -r tin tout <<<"$(tokens_guess "$m")"
  for c in $SYSTEMS; do
    dir="$OUT/$slug/$c"
    cmd=("$PY" benchmarks/evaluate_llms.py --model "$MODEL" --method "$m" --case "$c"
         --gen-requests "$N" --k "$K" --seeds "$SEEDS" --max-rounds "$MAXROUNDS"
         --pricing-file "$PRICING" --out-dir "$dir")
    if [[ -f "$dir/report.json" && $FORCE -eq 0 ]]; then
      echo "skip  $m $c (report exists: $dir/report.json)"
      skipped=$((skipped + 1))
      continue
    fi
    items=$((N * SEEDS))
    all_items=$((all_items + items))
    if [[ "$m" != "rule_based" ]]; then
      llm_items=$((llm_items + items))
      prompt_tok=$((prompt_tok + items * tin))
      compl_tok=$((compl_tok + items * tout))
    fi
    planned=$((planned + 1))
    if [[ $DRY_RUN -eq 1 ]]; then
      printf '%q ' "${cmd[@]}"; echo
      continue
    fi
    echo "run   $m $c -> $dir"
    mkdir -p "$dir"
    if ! "${cmd[@]}" 2>&1 | tee "$dir/run.log"; then
      failed=$((failed + 1)); failures+=("$m/$c")
      echo "FAIL  $m $c (see $dir/run.log)" >&2
    fi
  done
done

echo "# planned runs: $planned  skipped (report exists): $skipped  systems: $n_sys"
echo "# items: $all_items total, $llm_items with an LLM (methods x systems x N x seeds; rule_based excluded)"

if [[ $DRY_RUN -eq 1 ]]; then
  echo "# assumed tokens/item (prompt/completion): llm_only 6000/500, single_call 4000/400, agents 20000/1500"
  echo "# assumed tokens: ${prompt_tok} prompt + ${compl_tok} completion"
  if [[ -x "$PY" && -f "$PRICING" ]]; then
    "$PY" - "$PRICING" "$MODEL" "$prompt_tok" "$compl_tok" <<'PYEOF'
import json, sys
path, model, p_tok, c_tok = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
book = json.load(open(path))
price = book.get(model)
if price is None:
    print(f"# no entry for {model} in {path}; cannot estimate USD (known: {', '.join(sorted(book))})")
else:
    usd = p_tok / 1e6 * float(price["input"]) + c_tok / 1e6 * float(price["output"])
    print(f"# price {model}: ${price['input']}/M in, ${price['output']}/M out  ->  order-of-magnitude estimate ~${usd:.2f} USD (x2-3 for retries/long traces)")
PYEOF
  else
    echo "# no venv or pricing file; USD estimate skipped"
  fi
  exit 0
fi

echo "# done. failed: $failed${failures:+ (${failures[*]})}"
echo "# fill the table with: $PY benchmarks/fill_table.py $OUT --per-system --scaling-csv $OUT/scaling.csv"
[[ $failed -eq 0 ]]
