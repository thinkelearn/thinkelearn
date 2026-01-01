#!/usr/bin/env bash
set -euo pipefail

# ====== Config ======
BASE_REF="${BASE_REF:-origin/main}"
HEAD_REF="${HEAD_REF:-feat/lms}"

OUT_DIR="${OUT_DIR:-./.tmp/pr_review_out}"

# Input files (per your request)
PLAN_FILE="${PLAN_FILE:-./docs/lms-implementation-plan.md}"
DIFF_FILE="${DIFF_FILE:-./.tmp/pr.diff}"

# If you prefer generating diff fresh from git, set REGEN_DIFF=1
REGEN_DIFF="${REGEN_DIFF:-0}"

# Modes: cheap | balanced | paranoid
MODE="${MODE:-balanced}"

# Chunking for massive diffs
MAX_LINES_PER_CHUNK="${MAX_LINES_PER_CHUNK:-1200}"

# How many files to deep-review (risk-ranked)
TOP_RISK_FILES="${TOP_RISK_FILES:-18}"          # overall deep set
TOP_RISK_SECURITY_FILES="${TOP_RISK_SECURITY_FILES:-16}"
TOP_RISK_PAYMENTS_FILES="${TOP_RISK_PAYMENTS_FILES:-18}"
TOP_RISK_ACCOUNTING_FILES="${TOP_RISK_ACCOUNTING_FILES:-18}"
TOP_RISK_TEST_FILES="${TOP_RISK_TEST_FILES:-24}"

# Map-reduce summary bounds (lines, not tokens)
SUMMARY_HEAD_LINES="${SUMMARY_HEAD_LINES:-900}"
SUMMARY_TAIL_LINES="${SUMMARY_TAIL_LINES:-900}"

# Retry/backoff for 429s
RETRY_MAX="${RETRY_MAX:-6}"
RETRY_BASE_SLEEP="${RETRY_BASE_SLEEP:-8}"   # seconds
RETRY_JITTER="${RETRY_JITTER:-3}"           # seconds

# ====== Helpers ======
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
timestamp() { date +"%Y-%m-%d_%H-%M-%S"; }
mkdirp() { mkdir -p "$1"; }

available_openai_models() {
  llm models -q openai/ 2>/dev/null | awk '{print $2}' | sed '/^$/d' || true
}

pick_model() {
  local prefs=("$@")
  local available
  available="$(available_openai_models)"

  for m in "${prefs[@]}"; do
    # Skip any pro models
    if [[ "$m" == *"-pro"* ]] || [[ "$m" == *"/o1-pro"* ]] || [[ "$m" == *"/o3-pro"* ]] || [[ "$m" == *"/gpt-5-pro"* ]]; then
      continue
    fi
    if echo "$available" | grep -qx "$m"; then
      echo "$m"
      return 0
    fi
  done

  echo "$available" | grep -v -- '-pro' | head -n 1 || true
}

set_models_by_mode() {
  if [[ -n "${MODEL_HOLISTIC:-}" || -n "${MODEL_DEEP:-}" || -n "${MODEL_SECURITY:-}" || -n "${MODEL_SYNTHESIS:-}" || -n "${MODEL_FALLBACK:-}" ]]; then
    return 0
  fi

  case "$MODE" in
    cheap)
      MODEL_HOLISTIC="$(pick_model openai/gpt-5-mini openai/o4-mini openai/gpt-4.1-mini openai/gpt-4o-mini)"
      MODEL_SECURITY="$(pick_model openai/gpt-5-mini openai/o4-mini openai/gpt-4.1-mini openai/gpt-4o-mini)"
      MODEL_DEEP="$(pick_model openai/gpt-5-mini openai/o4-mini openai/gpt-4.1 openai/gpt-4o)"
      MODEL_SYNTHESIS="$(pick_model openai/gpt-5-mini openai/o3 openai/o1 openai/gpt-4.1)"
      MODEL_FALLBACK="$(pick_model openai/gpt-5-mini openai/gpt-4.1-mini openai/gpt-4o-mini)"
      TOP_RISK_FILES="${TOP_RISK_FILES:-12}"
      TOP_RISK_PAYMENTS_FILES="${TOP_RISK_PAYMENTS_FILES:-12}"
      TOP_RISK_ACCOUNTING_FILES="${TOP_RISK_ACCOUNTING_FILES:-12}"
      TOP_RISK_TEST_FILES="${TOP_RISK_TEST_FILES:-14}"
      ;;
    paranoid)
      MODEL_HOLISTIC="$(pick_model openai/gpt-5 openai/gpt-5-mini openai/o3 openai/gpt-4.1)"
      MODEL_SECURITY="$(pick_model openai/gpt-5 openai/o3 openai/gpt-5-mini openai/o4-mini)"
      MODEL_DEEP="$(pick_model openai/gpt-5 openai/o3 openai/gpt-4.1 openai/gpt-4o)"
      MODEL_SYNTHESIS="$(pick_model openai/gpt-5 openai/o3 openai/o1 openai/gpt-4.1)"
      MODEL_FALLBACK="$(pick_model openai/gpt-5-mini openai/o4-mini openai/gpt-4.1-mini)"
      TOP_RISK_FILES="${TOP_RISK_FILES:-30}"
      TOP_RISK_SECURITY_FILES="${TOP_RISK_SECURITY_FILES:-24}"
      TOP_RISK_PAYMENTS_FILES="${TOP_RISK_PAYMENTS_FILES:-28}"
      TOP_RISK_ACCOUNTING_FILES="${TOP_RISK_ACCOUNTING_FILES:-28}"
      TOP_RISK_TEST_FILES="${TOP_RISK_TEST_FILES:-32}"
      ;;
    balanced|*)
      MODEL_HOLISTIC="$(pick_model openai/gpt-5-mini openai/o4-mini openai/gpt-4.1-mini openai/gpt-4o-mini)"
      MODEL_SECURITY="$(pick_model openai/gpt-5-mini openai/o3 openai/o4-mini openai/gpt-4.1)"
      MODEL_DEEP="$(pick_model openai/gpt-5 openai/o3 openai/gpt-4.1 openai/gpt-4o)"
      MODEL_SYNTHESIS="$(pick_model openai/gpt-5 openai/o3 openai/o1 openai/gpt-4.1)"
      MODEL_FALLBACK="$(pick_model openai/gpt-5-mini openai/o4-mini openai/gpt-4.1-mini)"
      ;;
  esac
}

chunk_file() {
  local infile="$1"; local outprefix="$2"
  local n="$MAX_LINES_PER_CHUNK"
  awk -v n="$n" -v p="$outprefix" '
    { print > (p sprintf(".part%03d", int((NR-1)/n)+1) ".txt") }
  ' "$infile"
}

llm_run() {
  local model="$1"
  local system="$2"
  local infile="$3"
  local outfile="$4"

  local attempt=1
  local tmp_err
  tmp_err="$(mktemp)"

  while true; do
    if ( llm -m "$model" -s "$system" < "$infile" > "$outfile" ) 2> "$tmp_err"; then
      rm -f "$tmp_err"
      return 0
    fi

    if ! grep -q "Error code: 429" "$tmp_err"; then
      echo "ERROR: llm failed (model=$model). Stderr:" >&2
      cat "$tmp_err" >&2
      rm -f "$tmp_err"
      return 1
    fi

    if (( attempt > RETRY_MAX )); then
      echo "ERROR: Reached retry max ($RETRY_MAX) for model=$model due to 429." >&2
      cat "$tmp_err" >&2
      rm -f "$tmp_err"
      return 1
    fi

    local sleep_s=$(( RETRY_BASE_SLEEP * attempt + (RANDOM % RETRY_JITTER) ))
    echo "WARN: 429 for model=$model. Backing off ${sleep_s}s (attempt $attempt/$RETRY_MAX)..." >&2
    sleep "$sleep_s"
    attempt=$(( attempt + 1 ))
  done
}

bounded_view() {
  local infile="$1"; local outfile="$2"
  local head_n="$SUMMARY_HEAD_LINES"; local tail_n="$SUMMARY_TAIL_LINES"
  local total
  total="$(wc -l < "$infile" || echo 0)"
  if (( total <= head_n + tail_n + 50 )); then
    cat "$infile" > "$outfile"
    return 0
  fi
  {
    echo "<BEGIN_HEAD>"
    head -n "$head_n" "$infile"
    echo "<...SNIP... total_lines=$total ...>"
    tail -n "$tail_n" "$infile"
    echo "<END_TAIL>"
  } > "$outfile"
}

summarize_to_brief() {
  local model="$1"
  local system="$2"
  local title="$3"
  local infile="$4"
  local outfile="$5"

  local bounded="$RUN_DIR/_bounded_${title}.txt"
  bounded_view "$infile" "$bounded"

  local prompt="$RUN_DIR/_prompt_brief_${title}.txt"
  {
    echo "Create a concise PR-review brief for section: $title"
    echo
    echo "Constraints:"
    echo "- concise, actionable"
    echo "- include severities and file paths when present"
    echo "- include missing-test suggestions where relevant"
    echo
    echo "Content:"
    cat "$bounded"
  } > "$prompt"

  llm_run "$model" "$system" "$prompt" "$outfile"
}

# ====== Risk ranking (Phase 5 accounting-aware) ======
rank_files_by_risk() {
  local numstat_file="$1"
  local out_file="$2"

  awk '
    function contains(s, re) { return (s ~ re) }
    {
      add=$1; del=$2; file=$3
      if (add=="-" || del=="-") { add=500; del=500 } # binary-ish changes
      base = add + del
      w = 0

      # Payments/LMS core
      if (contains(file, /(payments|lms)\//)) w += 70

      # Stripe/webhooks/payment surface
      if (contains(file, /(stripe|webhook|checkout|payment|refund|charge|balance_transaction)/)) w += 220
      if (contains(file, /(payments\/webhooks\.py|payments\/stripe_client\.py|payments\/views\.py)/)) w += 140

      # Accounting/ledger/reconciliation (Phase 5)
      if (contains(file, /(ledger|accounting|reconcil|recalculate_totals|amount_gross|amount_refunded|amount_net)/)) w += 260
      if (contains(file, /(payments\/models\.py|payments\/admin\.py)/)) w += 120

      # Auth/security config
      if (contains(file, /(auth|account|permission|policy|acl|rbac|middleware|settings|csrf|csp|security|oauth|jwt|sso)/)) w += 170

      # Migrations
      if (contains(file, /\/migrations\/.*\.py$/)) w += 200

      # Templates + JS can be security relevant
      if (contains(file, /\.(html|jinja|twig)$/) || contains(file, /templates\//)) w += 60
      if (contains(file, /\.(js|ts|tsx)$/)) w += 45

      # Management commands / scripts
      if (contains(file, /(management\/commands|scripts)\//)) w += 40

      # Tests: reduce “risk” but still valuable for confidence
      if (contains(file, /(^|\/)(tests\/|test_).*\.py$/)) w -= 35

      score = base + w
      printf "%10d\t%6d\t%6d\t%s\n", score, add, del, file
    }
  ' "$numstat_file" | sort -nr > "$out_file"
}

take_top_ranked() {
  local ranked_file="$1"
  local regex="$2"
  local n="$3"
  awk -v re="$regex" -v n="$n" '$0 ~ re {print $4}' "$ranked_file" | head -n "$n"
}

# ====== Preflight ======
need git
need llm
need awk
need sed
need grep
need wc
need head
need tail
need sort
need uniq

set_models_by_mode

mkdirp "$OUT_DIR"
RUN_ID="$(timestamp)"
RUN_DIR="$OUT_DIR/$RUN_ID"
mkdirp "$RUN_DIR"

echo "==> Output: $RUN_DIR"
echo "==> Base..Head: $BASE_REF...$HEAD_REF"
echo "==> MODE=$MODE"
echo "==> Models:"
echo "   HOLISTIC=$MODEL_HOLISTIC"
echo "   SECURITY=$MODEL_SECURITY"
echo "   DEEP=$MODEL_DEEP"
echo "   SYNTHESIS=$MODEL_SYNTHESIS"
echo "   FALLBACK=$MODEL_FALLBACK"

git fetch origin >/dev/null 2>&1 || true

# ====== Collect artifacts ======
if [[ "$REGEN_DIFF" == "1" ]]; then
  echo "==> Regenerating diff from git..."
  git diff "$BASE_REF...$HEAD_REF" > "$RUN_DIR/pr.diff"
  DIFF_PATH="$RUN_DIR/pr.diff"
else
  if [[ ! -f "$DIFF_FILE" ]]; then
    echo "ERROR: Diff file not found at $DIFF_FILE" >&2
    echo "Tip: generate it with: git diff $BASE_REF...$HEAD_REF > $DIFF_FILE" >&2
    exit 1
  fi
  cp "$DIFF_FILE" "$RUN_DIR/pr.diff"
  DIFF_PATH="$RUN_DIR/pr.diff"
fi

PLAN_PATH=""
if [[ -f "$PLAN_FILE" ]]; then
  cp "$PLAN_FILE" "$RUN_DIR/lms-implementation-plan.md"
  PLAN_PATH="$RUN_DIR/lms-implementation-plan.md"
else
  echo "WARN: Plan file not found at $PLAN_FILE (continuing without it)" >&2
fi

git diff --stat "$BASE_REF...$HEAD_REF" > "$RUN_DIR/diffstat.txt"
git diff --name-status "$BASE_REF...$HEAD_REF" > "$RUN_DIR/name-status.txt"
git diff --name-only "$BASE_REF...$HEAD_REF" > "$RUN_DIR/files.txt"
git diff --numstat "$BASE_REF...$HEAD_REF" > "$RUN_DIR/numstat.txt"
git log --pretty=format:'%an|%ad|%s' --date=short "$BASE_REF..$HEAD_REF" > "$RUN_DIR/commit_log_compact.txt"

awk -F/ '{print $1}' "$RUN_DIR/files.txt" | sort | uniq -c | sort -nr > "$RUN_DIR/dirs_top.txt"
awk -F/ 'NF>1{print $1"/"$2}' "$RUN_DIR/files.txt" | sort | uniq -c | sort -nr > "$RUN_DIR/dirs_top2.txt"

{
  echo "Diff lines: $(wc -l < "$DIFF_PATH")"
  echo "Files changed: $(wc -l < "$RUN_DIR/files.txt")"
  echo
  cat "$RUN_DIR/diffstat.txt"
} > "$RUN_DIR/metrics.txt"

grep -E '^(diff --git |@@ )' "$DIFF_PATH" > "$RUN_DIR/diff_outline.txt" || true
head -n 600 "$RUN_DIR/diff_outline.txt" > "$RUN_DIR/diff_outline_head.txt" || true

# ====== Risk ranking ======
echo "==> Risk ranking..."
rank_files_by_risk "$RUN_DIR/numstat.txt" "$RUN_DIR/ranked_files.tsv"
head -n 100 "$RUN_DIR/ranked_files.tsv" > "$RUN_DIR/ranked_files_top100.tsv"

TOP_RISK_SET="$(awk 'NR<=N{print $4}' N="$TOP_RISK_FILES" "$RUN_DIR/ranked_files.tsv")"

SECURITY_SET="$(take_top_ranked "$RUN_DIR/ranked_files.tsv" "(stripe|webhook|checkout|payment|refund|charge|balance_transaction|auth|permission|middleware|settings|csrf|csp|security|oauth|jwt|sso)" "$TOP_RISK_SECURITY_FILES")"
PAYMENTS_SET="$(take_top_ranked "$RUN_DIR/ranked_files.tsv" "(payments/|stripe|webhook|checkout|payment|refund|enroll|lms)" "$TOP_RISK_PAYMENTS_FILES")"

# Phase 5 focused selection
ACCOUNTING_SET="$(take_top_ranked "$RUN_DIR/ranked_files.tsv" "(ledger|accounting|reconcil|recalculate_totals|amount_gross|amount_refunded|amount_net|charge\\.succeeded|charge\\.refunded|balance_transaction|payments/models\\.py|payments/webhooks\\.py|payments/admin\\.py)" "$TOP_RISK_ACCOUNTING_FILES")"

MIGRATIONS_SET="$(grep -E '/migrations/.*\.py$' "$RUN_DIR/files.txt" || true)"
TESTS_SET="$(take_top_ranked "$RUN_DIR/ranked_files.tsv" "(^|/)(tests/|test_).*\\.py$" "$TOP_RISK_TEST_FILES")"

# ====== HOLISTIC REVIEW ======
echo "==> Holistic synthesis..."
HOLISTIC_PROMPT="$RUN_DIR/prompt_holistic.txt"
{
  echo "You are a senior staff engineer reviewing a mega-merge PR for a Django/Wagtail LMS."
  echo
  echo "This PR includes Phase 1-5 of the LMS plan, including Phase 5 Accounting Ledger + Reconciliation."
  echo "Produce:"
  echo "- What changed (high-level)"
  echo "- Risk areas (ranked)"
  echo "- Suggested review order"
  echo "- Suggested manual test plan"
  echo "- Anything that looks inconsistent with Phase 5 accounting requirements"
  echo
  echo "=== DIFFSTAT ==="
  cat "$RUN_DIR/diffstat.txt"
  echo
  echo "=== TOP RISK FILES (score, add, del, path) ==="
  cat "$RUN_DIR/ranked_files_top100.tsv"
  echo
  echo "=== PHASE 5 FOCUS FILES (accounting/ledger/reconciliation) ==="
  echo "$ACCOUNTING_SET"
  echo
  echo "=== DIR BREAKDOWN ==="
  head -n 25 "$RUN_DIR/dirs_top.txt"
  echo
  echo "=== COMMIT LOG (last 300) ==="
  tail -n 300 "$RUN_DIR/commit_log_compact.txt"
  echo
  echo "=== DIFF OUTLINE (first 600 lines) ==="
  cat "$RUN_DIR/diff_outline_head.txt"
  echo
  if [[ -n "$PLAN_PATH" ]]; then
    echo "=== PLAN EXCERPT (Phase 5 accounting) ==="
    # Pull a bit more since Phase 5 is lower in the doc; bounded by tokenizer anyway.
    sed -n '300,500p' "$PLAN_PATH"
    echo
  fi
} > "$HOLISTIC_PROMPT"

llm_run \
  "$MODEL_HOLISTIC" \
  "Meticulous PR reviewer. Emphasize Phase 5 accounting ledger + reconciliation logic correctness and risk." \
  "$HOLISTIC_PROMPT" \
  "$RUN_DIR/00_holistic_review.md"

# ====== SECURITY REVIEW (chunk full diff) ======
echo "==> Security-focused review..."
SEC_PROMPT="$RUN_DIR/prompt_security.txt"
{
  echo "Security review of a Django/Wagtail PR."
  echo "Return: Threat model, Findings (High/Med/Low), Fixes, Production checklist."
  echo
  echo "Explicitly review payment/webhook + accounting ledger safety:"
  echo "- webhook signature verification + idempotency (WebhookEvent + ledger unique constraints)"
  echo "- authorization checks on payment endpoints"
  echo "- no global Stripe api_key (per-request only)"
  echo "- input validation and safe metadata handling"
  echo
  if [[ -n "$PLAN_PATH" ]]; then
    echo "=== PLAN EXCERPT (Security + Phase 5) ==="
    sed -n '140,220p' "$PLAN_PATH"
    sed -n '330,470p' "$PLAN_PATH"
    echo
  fi
  echo "=== TOP RISK SECURITY FILES (paths) ==="
  echo "$SECURITY_SET"
  echo
  echo "=== DIFFSTAT ==="
  cat "$RUN_DIR/diffstat.txt"
  echo
  echo "=== DIFF OUTLINE (first 600 lines) ==="
  cat "$RUN_DIR/diff_outline_head.txt"
} > "$SEC_PROMPT"

llm_run \
  "$MODEL_SECURITY" \
  "Security reviewer. Focus on authn/authz, input validation, secrets, webhooks, idempotency, and accounting data integrity." \
  "$SEC_PROMPT" \
  "$RUN_DIR/01_security_review.md"

mkdirp "$RUN_DIR/security_chunks"
chunk_file "$DIFF_PATH" "$RUN_DIR/security_chunks/diff"

for part in "$RUN_DIR/security_chunks"/diff.part*.txt; do
  tmp_prompt="$RUN_DIR/_sec_chunk_prompt.txt"
  {
    echo "Extract ONLY security-relevant findings from this diff chunk."
    echo "Output bullets with severity + file path + suggested fix."
    echo
    cat "$part"
  } > "$tmp_prompt"

  llm_run \
    "$MODEL_SECURITY" \
    "Security reviewer. Output only findings+fixes, no general commentary." \
    "$tmp_prompt" \
    "$RUN_DIR/_sec_chunk_out.md"
  cat "$RUN_DIR/_sec_chunk_out.md" >> "$RUN_DIR/01_security_review.md"
  echo -e "\n" >> "$RUN_DIR/01_security_review.md"
done

# ====== MIGRATIONS REVIEW ======
echo "==> Data integrity & migrations review..."
: > "$RUN_DIR/02_data_integrity_review.md"
if [[ -n "$MIGRATIONS_SET" ]]; then
  while read -r mf; do
    [[ -z "$mf" ]] && continue
    git diff "$BASE_REF...$HEAD_REF" -- "$mf" > "$RUN_DIR/_mig.tmp" || true
    [[ ! -s "$RUN_DIR/_mig.tmp" ]] && continue

    prompt="$RUN_DIR/_mig_prompt.txt"
    {
      echo "Review this Django migration for production safety:"
      echo "- locking risks"
      echo "- irreversible ops"
      echo "- missing indexes/constraints"
      echo "- data migration safety and rollback plan"
      echo
      echo "Special attention: Phase 5 accounting ledger constraints and indexes."
      echo
      echo "File: $mf"
      echo
      cat "$RUN_DIR/_mig.tmp"
    } > "$prompt"

    llm_run \
      "$MODEL_DEEP" \
      "Django migrations expert. Be strict and concrete." \
      "$prompt" \
      "$RUN_DIR/_mig_out.md"

    {
      echo "## $mf"
      cat "$RUN_DIR/_mig_out.md"
      echo -e "\n---\n"
    } >> "$RUN_DIR/02_data_integrity_review.md"
  done <<< "$MIGRATIONS_SET"
else
  echo "No migration files detected." >> "$RUN_DIR/02_data_integrity_review.md"
fi

# ====== ACCOUNTING + RECONCILIATION REVIEW (new, Phase 5-focused) ======
echo "==> Accounting + reconciliation review (Phase 5)..."
: > "$RUN_DIR/03_accounting_review.md"

# Ensure we always include canonical Phase 5 files if present
CANONICAL_ACCOUNTING_FILES="$RUN_DIR/_canonical_accounting_files.txt"
{
  echo "payments/models.py"
  echo "payments/webhooks.py"
  echo "payments/admin.py"
  echo "payments/migrations/0002_accounting_ledger.py"
  echo "payments/tests/test_models.py"
  echo "payments/tests/test_webhooks.py"
} | sort -u > "$CANONICAL_ACCOUNTING_FILES"

ACCOUNTING_SET_FILE="$RUN_DIR/_accounting_set.txt"
{
  echo "$ACCOUNTING_SET"
  cat "$CANONICAL_ACCOUNTING_FILES"
} | sed '/^$/d' | sort -u > "$ACCOUNTING_SET_FILE"

while read -r f; do
  [[ -z "$f" ]] && continue
  if ! grep -qx "$f" "$RUN_DIR/files.txt"; then
    # still allow if diff exists for file path (rare for deleted/renamed cases)
    git diff "$BASE_REF...$HEAD_REF" -- "$f" > "$RUN_DIR/_file.tmp" || true
    [[ ! -s "$RUN_DIR/_file.tmp" ]] && continue
  else
    git diff "$BASE_REF...$HEAD_REF" -- "$f" > "$RUN_DIR/_file.tmp" || true
    [[ ! -s "$RUN_DIR/_file.tmp" ]] && continue
  fi

  prompt="$RUN_DIR/_acct_prompt.txt"
  {
    echo "You are reviewing Phase 5: Accounting Data Model + Reconciliation."
    echo
    echo "Focus points (must cover):"
    echo "- PaymentLedgerEntry: entry types, constraints, idempotency, Stripe ID uniqueness"
    echo "- Payment totals: amount_gross/amount_refunded/amount_net; how derived; update_fields correctness"
    echo "- recalculate_totals(): correctness, fee handling, save=True semantics"
    echo "- Webhooks: charge.succeeded and charge.refunded ledger writes; replay/idempotency; early-return paths"
    echo "- Refunds: partial + multiple refunds aggregation; regression risk"
    echo "- Admin: ledger inline, filters, readability"
    echo "- Tests: coverage of partial/multiple refunds, idempotency, regression test for early return"
    echo
    echo "Provide PR-style comments with concrete fixes."
    echo
    echo "File: $f"
    echo
    cat "$RUN_DIR/_file.tmp"
  } > "$prompt"

  llm_run \
    "$MODEL_DEEP" \
    "Senior Django+Stripe accounting reviewer. Be precise about idempotency, invariants, totals reconciliation, and webhook edge cases." \
    "$prompt" \
    "$RUN_DIR/_acct_out.md"

  {
    echo "## $f"
    cat "$RUN_DIR/_acct_out.md"
    echo -e "\n---\n"
  } >> "$RUN_DIR/03_accounting_review.md"
done < "$ACCOUNTING_SET_FILE"

# ====== DEEP REVIEW (risk-ranked overall + payments set) ======
echo "==> Deep review (risk-ranked)..."
: > "$RUN_DIR/04_deep_review.md"

DEEP_SET="$RUN_DIR/_deep_set.txt"
{
  echo "$PAYMENTS_SET"
  echo "$TOP_RISK_SET"
} | sed '/^$/d' | sort -u > "$DEEP_SET"

while read -r f; do
  [[ -z "$f" ]] && continue
  if ! grep -qx "$f" "$RUN_DIR/files.txt"; then
    continue
  fi

  git diff "$BASE_REF...$HEAD_REF" -- "$f" > "$RUN_DIR/_deep_file.tmp" || true
  [[ ! -s "$RUN_DIR/_deep_file.tmp" ]] && continue

  prompt="$RUN_DIR/_deep_prompt.txt"
  {
    echo "PR review this file diff."
    echo "Focus: correctness, Django best practices, authz checks, query efficiency,"
    echo "transaction.atomic usage, and side effects."
    echo
    echo "If it touches Stripe/webhooks/payments/accounting:"
    echo "- check signature verification + idempotency"
    echo "- check ledger/totals invariants"
    echo
    echo "File: $f"
    echo
    cat "$RUN_DIR/_deep_file.tmp"
  } > "$prompt"

  llm_run \
    "$MODEL_DEEP" \
    "Senior Django engineer. Provide PR-style inline comments and concrete fixes." \
    "$prompt" \
    "$RUN_DIR/_deep_out.md"

  {
    echo "## $f"
    cat "$RUN_DIR/_deep_out.md"
    echo -e "\n---\n"
  } >> "$RUN_DIR/04_deep_review.md"
done < "$DEEP_SET"

# ====== TEST REVIEW (risk-ranked tests) ======
echo "==> Test review..."
: > "$RUN_DIR/05_tests_review.md"
if [[ -n "$TESTS_SET" ]]; then
  while read -r tf; do
    [[ -z "$tf" ]] && continue
    if ! grep -qx "$tf" "$RUN_DIR/files.txt"; then
      continue
    fi

    git diff "$BASE_REF...$HEAD_REF" -- "$tf" > "$RUN_DIR/_test.tmp" || true
    [[ ! -s "$RUN_DIR/_test.tmp" ]] && continue

    prompt="$RUN_DIR/_test_prompt.txt"
    {
      echo "Review these test changes. Identify missing cases and flakiness risks."
      echo "Especially important for Phase 5 accounting:"
      echo "- partial refund persists refunded amount"
      echo "- multiple refunds aggregate correctly"
      echo "- ledger entries idempotent"
      echo "- regression test for early return path calling recalculate_totals()"
      echo
      echo "File: $tf"
      echo
      cat "$RUN_DIR/_test.tmp"
    } > "$prompt"

    llm_run \
      "$MODEL_HOLISTIC" \
      "Pragmatic test reviewer. Focus on meaningful assertions, missing edge cases, and stability." \
      "$prompt" \
      "$RUN_DIR/_test_out.md"

    {
      echo "## $tf"
      cat "$RUN_DIR/_test_out.md"
      echo -e "\n---\n"
    } >> "$RUN_DIR/05_tests_review.md"
  done <<< "$TESTS_SET"
else
  echo "No tests detected (or none were in top risk set)." >> "$RUN_DIR/05_tests_review.md"
fi

# ====== FINAL SYNTHESIS (MAP-REDUCE, Phase 5-aware) ======
echo "==> Final synthesis (map-reduce)..."

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "holistic" \
  "$RUN_DIR/00_holistic_review.md" \
  "$RUN_DIR/10_brief_holistic.md"

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "security" \
  "$RUN_DIR/01_security_review.md" \
  "$RUN_DIR/11_brief_security.md"

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "migrations" \
  "$RUN_DIR/02_data_integrity_review.md" \
  "$RUN_DIR/12_brief_migrations.md" || true

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "accounting" \
  "$RUN_DIR/03_accounting_review.md" \
  "$RUN_DIR/13_brief_accounting.md"

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "deep" \
  "$RUN_DIR/04_deep_review.md" \
  "$RUN_DIR/14_brief_deep.md"

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "tests" \
  "$RUN_DIR/05_tests_review.md" \
  "$RUN_DIR/15_brief_tests.md"

FINAL_PROMPT="$RUN_DIR/prompt_final.txt"
{
  echo "Create ONE final GitHub PR review comment for a mega-merge PR (Phases 1-5)."
  echo
  echo "This PR includes Phase 5: Accounting Data Model + Reconciliation. Treat accounting correctness as a top priority."
  echo
  echo "Format:"
  echo "- Executive summary (what this PR accomplishes)"
  echo "- Key wins"
  echo "- Top risks (ranked)"
  echo "- Blocking issues (if any)"
  echo "- Accounting & reconciliation notes (Phase 5)"
  echo "- Security notes"
  echo "- Data integrity / migrations notes"
  echo "- Suggested follow-ups (small, concrete)"
  echo "- Manual test plan (step-by-step)"
  echo
  if [[ -n "$PLAN_PATH" ]]; then
    echo "Plan anchor (brief):"
    sed -n '320,420p' "$PLAN_PATH"
    echo
  fi
  echo "Use these bounded briefs (authoritative):"
  echo
  echo "=== Brief: Holistic ==="
  cat "$RUN_DIR/10_brief_holistic.md"
  echo
  echo "=== Brief: Accounting (Phase 5) ==="
  cat "$RUN_DIR/13_brief_accounting.md"
  echo
  echo "=== Brief: Security ==="
  cat "$RUN_DIR/11_brief_security.md"
  echo
  echo "=== Brief: Migrations ==="
  cat "$RUN_DIR/12_brief_migrations.md" 2>/dev/null || echo "(none)"
  echo
  echo "=== Brief: Deep review ==="
  cat "$RUN_DIR/14_brief_deep.md"
  echo
  echo "=== Brief: Tests ==="
  cat "$RUN_DIR/15_brief_tests.md"
  echo
} > "$FINAL_PROMPT"

if ! llm_run "$MODEL_SYNTHESIS" "Senior reviewer. Produce a crisp final PR comment." "$FINAL_PROMPT" "$RUN_DIR/99_final_pr_review.md"; then
  echo "WARN: Synthesis model '$MODEL_SYNTHESIS' failed; falling back to '$MODEL_FALLBACK'." >&2
  llm_run "$MODEL_FALLBACK" "Senior reviewer. Produce a crisp final PR comment." "$FINAL_PROMPT" "$RUN_DIR/99_final_pr_review.md"
fi

echo "==> Done."
echo "Outputs:"
ls -1 "$RUN_DIR" | sed 's/^/ - /'
echo
echo "Most useful file to paste into GitHub:"
echo " - $RUN_DIR/99_final_pr_review.md"
