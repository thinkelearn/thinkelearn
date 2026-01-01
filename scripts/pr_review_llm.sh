#!/usr/bin/env bash
set -euo pipefail

# ====== Config ======
BASE_REF="${BASE_REF:-origin/main}"
HEAD_REF="${HEAD_REF:-feat/lms}"

OUT_DIR="${OUT_DIR:-./.tmp/pr_review_out}"

# Models (pick best you have; script will fall back automatically)
MODEL_HOLISTIC="${MODEL_HOLISTIC:-4.1-mini}"    # structure + synthesis of stats/outlines
MODEL_DEEP="${MODEL_DEEP:-4.1}"                 # file-level deep reviews
MODEL_SECURITY="${MODEL_SECURITY:-o3}"          # security extraction from chunks
MODEL_SYNTHESIS="${MODEL_SYNTHESIS:-o3}"        # final synthesis (try best reasoning here)
MODEL_FALLBACK="${MODEL_FALLBACK:-4.1}"         # fallback if synthesis model errors

MAX_LINES_PER_CHUNK="${MAX_LINES_PER_CHUNK:-1200}"
MAX_FILES_PER_DEEP_PASS="${MAX_FILES_PER_DEEP_PASS:-25}"

# Input files (per your request)
PLAN_FILE="${PLAN_FILE:-./docs/lms-implementation-plan.md}"
DIFF_FILE="${DIFF_FILE:-./.tmp/pr.diff}"

# If you prefer generating diff fresh from git, set REGEN_DIFF=1
REGEN_DIFF="${REGEN_DIFF:-0}"

# TPM safety: cap how much we feed to any single summarization step
# (These are lines, not tokens; keep conservative.)
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

chunk_file() {
  local infile="$1"; local outprefix="$2"
  local n="$MAX_LINES_PER_CHUNK"
  awk -v n="$n" -v p="$outprefix" '
    { print > (p sprintf(".part%03d", int((NR-1)/n)+1) ".txt") }
  ' "$infile"
}

# Run llm with retries on 429 / transient errors.
# Usage: llm_run MODEL SYSTEM INFILE OUTFILE
llm_run() {
  local model="$1"
  local system="$2"
  local infile="$3"
  local outfile="$4"

  local attempt=1
  local tmp_err
  tmp_err="$(mktemp)"

  while true; do
    # Use a subshell so "set -e" doesn't kill us on failure
    if ( llm -m "$model" -s "$system" < "$infile" > "$outfile" ) 2> "$tmp_err"; then
      rm -f "$tmp_err"
      return 0
    fi

    # If not 429, fail fast
    if ! grep -q "Error code: 429" "$tmp_err"; then
      echo "ERROR: llm failed (model=$model). Stderr:" >&2
      cat "$tmp_err" >&2
      rm -f "$tmp_err"
      return 1
    fi

    if (( attempt > RETRY_MAX )); then
      echo "ERROR: Reached retry max ($RETRY_MAX) for model=$model due to 429 TPM." >&2
      cat "$tmp_err" >&2
      rm -f "$tmp_err"
      return 1
    fi

    # Backoff with jitter
    local sleep_s=$(( RETRY_BASE_SLEEP * attempt + (RANDOM % RETRY_JITTER) ))
    echo "WARN: 429 TPM for model=$model. Backing off ${sleep_s}s (attempt $attempt/$RETRY_MAX)..." >&2
    sleep "$sleep_s"
    attempt=$(( attempt + 1 ))
  done
}

# Create a bounded view of a large markdown file for summarization:
# head N + tail N with a marker in the middle.
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

# Safe synthesis: summarize each artifact to a brief, then final combine briefs.
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
    echo "- max ~350-500 lines output"
    echo "- include bullets, severities, and file paths when present"
    echo "- focus on actionable items"
    echo
    echo "Content:"
    cat "$bounded"
  } > "$prompt"

  llm_run "$model" "$system" "$prompt" "$outfile"
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

mkdirp "$OUT_DIR"
RUN_ID="$(timestamp)"
RUN_DIR="$OUT_DIR/$RUN_ID"
mkdirp "$RUN_DIR"

echo "==> Output: $RUN_DIR"
echo "==> Base..Head: $BASE_REF...$HEAD_REF"

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
head -n 500 "$RUN_DIR/diff_outline.txt" > "$RUN_DIR/diff_outline_head.txt" || true

# ====== HOLISTIC REVIEW ======
echo "==> Holistic synthesis..."
HOLISTIC_PROMPT="$RUN_DIR/prompt_holistic.txt"
{
  echo "You are a senior staff engineer doing a PR review for a Django/Wagtail app."
  echo
  echo "Context: mega-merge PR (many branches/PRs). Produce:"
  echo "- What changed (high-level)"
  echo "- Risk areas"
  echo "- Suggested review order"
  echo "- Suggested manual test plan"
  echo "- Conflicts with plan (if provided)"
  echo
  echo "=== DIFFSTAT ==="
  cat "$RUN_DIR/diffstat.txt"
  echo
  echo "=== DIR BREAKDOWN ==="
  echo "--- top-level dirs ---"
  cat "$RUN_DIR/dirs_top.txt"
  echo
  echo "--- top-level/second-level dirs ---"
  head -n 70 "$RUN_DIR/dirs_top2.txt"
  echo
  echo "=== COMMIT LOG (last 250) ==="
  tail -n 250 "$RUN_DIR/commit_log_compact.txt"
  echo
  echo "=== DIFF OUTLINE (first 500 lines) ==="
  cat "$RUN_DIR/diff_outline_head.txt"
  echo
  if [[ -n "$PLAN_PATH" ]]; then
    echo "=== IMPLEMENTATION PLAN (excerpt) ==="
    sed -n '1,320p' "$PLAN_PATH"
    echo
  fi
} > "$HOLISTIC_PROMPT"

llm_run \
  "$MODEL_HOLISTIC" \
  "Meticulous PR reviewer. Provide concrete, structured output." \
  "$HOLISTIC_PROMPT" \
  "$RUN_DIR/00_holistic_review.md"

# ====== File lists ======
PAYMENTS_FILES="$(grep -E '(^|/)(payments|billing|stripe|webhooks|checkout|orders|enroll|lms)(/|$)' "$RUN_DIR/files.txt" || true)"
MIGRATION_FILES="$(grep -E '/migrations/.*\.py$' "$RUN_DIR/files.txt" || true)"
TEST_FILES="$(grep -E '(^|/)(test_|tests/).*\.py$' "$RUN_DIR/files.txt" || true)"

pick_top_files() { echo "$1" | sed '/^$/d' | head -n "$2" || true; }
DEEP_FILELIST="$(pick_top_files "$PAYMENTS_FILES" "$MAX_FILES_PER_DEEP_PASS")"

# ====== SECURITY REVIEW (chunk full diff) ======
echo "==> Security-focused review..."
SEC_PROMPT="$RUN_DIR/prompt_security.txt"
{
  echo "Security review of a Django/Wagtail PR."
  echo "Return: Threat model, Findings (High/Med/Low), Fixes, Production checklist."
  echo
  if [[ -n "$PLAN_PATH" ]]; then
    echo "Plan security anchors:"
    echo "- authz checks on enrollment/payment endpoints"
    echo "- webhook signature verification + idempotency"
    echo "- per-request Stripe API key (no global state)"
    echo
    sed -n '1,240p' "$PLAN_PATH"
    echo
  fi
  echo "Start with diffstat + outline, then chunk findings will follow."
  echo
  echo "=== DIFFSTAT ==="
  cat "$RUN_DIR/diffstat.txt"
  echo
  echo "=== DIFF OUTLINE (first 500 lines) ==="
  cat "$RUN_DIR/diff_outline_head.txt"
} > "$SEC_PROMPT"

llm_run \
  "$MODEL_SECURITY" \
  "Security reviewer. Focus on authn/authz, input validation, secrets, webhooks, SSRF/open redirects, unsafe deserialization." \
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

  # Append to existing report
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
if [[ -n "$MIGRATION_FILES" ]]; then
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
  done <<< "$MIGRATION_FILES"
else
  echo "No migration files detected." >> "$RUN_DIR/02_data_integrity_review.md"
fi

# ====== PAYMENTS/STRIPE DEEP REVIEW ======
echo "==> Payments/Stripe deep review..."
: > "$RUN_DIR/03_payments_deep_review.md"
if [[ -n "$DEEP_FILELIST" ]]; then
  while read -r f; do
    [[ -z "$f" ]] && continue
    git diff "$BASE_REF...$HEAD_REF" -- "$f" > "$RUN_DIR/_file.tmp" || true
    [[ ! -s "$RUN_DIR/_file.tmp" ]] && continue

    prompt="$RUN_DIR/_pay_prompt.txt"
    {
      echo "PR review this file diff."
      echo "Focus: authorization, eligibility checks, idempotency keys,"
      echo "webhook signature verification, state transitions, and transaction.atomic usage."
      echo "Flag any global Stripe key usage; prefer per-request key."
      echo
      echo "File: $f"
      echo
      cat "$RUN_DIR/_file.tmp"
    } > "$prompt"

    llm_run \
      "$MODEL_DEEP" \
      "Senior Django/Stripe engineer. Provide PR-style inline comments and concrete fixes." \
      "$prompt" \
      "$RUN_DIR/_pay_out.md"

    {
      echo "## $f"
      cat "$RUN_DIR/_pay_out.md"
      echo -e "\n---\n"
    } >> "$RUN_DIR/03_payments_deep_review.md"
  done <<< "$DEEP_FILELIST"
else
  echo "No payments-related files selected for deep review (adjust patterns if needed)." >> "$RUN_DIR/03_payments_deep_review.md"
fi

# ====== TEST REVIEW ======
echo "==> Test review..."
: > "$RUN_DIR/04_tests_review.md"
if [[ -n "$TEST_FILES" ]]; then
  FOCUS_TESTS="$(echo "$TEST_FILES" | grep -E '(^|/)(payments|billing|stripe|lms)(/|$)' | head -n 30 || true)"
  [[ -z "$FOCUS_TESTS" ]] && FOCUS_TESTS="$(echo "$TEST_FILES" | head -n 30 || true)"

  while read -r tf; do
    [[ -z "$tf" ]] && continue
    git diff "$BASE_REF...$HEAD_REF" -- "$tf" > "$RUN_DIR/_test.tmp" || true
    [[ ! -s "$RUN_DIR/_test.tmp" ]] && continue

    prompt="$RUN_DIR/_test_prompt.txt"
    {
      echo "Review these test changes. Identify missing cases and flakiness risks."
      echo "Look for coverage of: permissions, payment flows, webhook signature/idempotency, state transitions."
      echo
      echo "File: $tf"
      echo
      cat "$RUN_DIR/_test.tmp"
    } > "$prompt"

    llm_run \
      "$MODEL_HOLISTIC" \
      "Pragmatic test reviewer. Focus on meaningful assertions and gaps." \
      "$prompt" \
      "$RUN_DIR/_test_out.md"

    {
      echo "## $tf"
      cat "$RUN_DIR/_test_out.md"
      echo -e "\n---\n"
    } >> "$RUN_DIR/04_tests_review.md"
  done <<< "$FOCUS_TESTS"
else
  echo "No tests detected." >> "$RUN_DIR/04_tests_review.md"
fi

# ====== TPM-SAFE FINAL SYNTHESIS (MAP-REDUCE) ======
echo "==> Final synthesis (TPM-safe map-reduce)..."

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "holistic" \
  "$RUN_DIR/00_holistic_review.md" \
  "$RUN_DIR/10_brief_holistic.md" || true

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "security" \
  "$RUN_DIR/01_security_review.md" \
  "$RUN_DIR/11_brief_security.md" || true

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "migrations" \
  "$RUN_DIR/02_data_integrity_review.md" \
  "$RUN_DIR/12_brief_migrations.md" || true

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "payments" \
  "$RUN_DIR/03_payments_deep_review.md" \
  "$RUN_DIR/13_brief_payments.md" || true

summarize_to_brief \
  "$MODEL_SYNTHESIS" \
  "Summarize into a bounded brief for final PR synthesis. Keep it actionable." \
  "tests" \
  "$RUN_DIR/04_tests_review.md" \
  "$RUN_DIR/14_brief_tests.md" || true

FINAL_PROMPT="$RUN_DIR/prompt_final.txt"
{
  echo "Create ONE final GitHub PR review comment for a mega-merge PR."
  echo
  echo "Format:"
  echo "- Executive summary (what this PR accomplishes)"
  echo "- Key wins"
  echo "- Top risks (ranked)"
  echo "- Blocking issues (if any)"
  echo "- Security notes"
  echo "- Data integrity / migration notes"
  echo "- Suggested follow-ups (small, concrete)"
  echo "- Manual test plan (step-by-step)"
  echo
  if [[ -n "$PLAN_PATH" ]]; then
    echo "Plan anchor (very brief):"
    sed -n '1,80p' "$PLAN_PATH"
    echo
  fi
  echo "Use these bounded briefs (authoritative):"
  echo
  echo "=== Brief: Holistic ==="
  cat "$RUN_DIR/10_brief_holistic.md"
  echo
  echo "=== Brief: Security ==="
  cat "$RUN_DIR/11_brief_security.md"
  echo
  echo "=== Brief: Migrations ==="
  cat "$RUN_DIR/12_brief_migrations.md"
  echo
  echo "=== Brief: Payments ==="
  cat "$RUN_DIR/13_brief_payments.md"
  echo
  echo "=== Brief: Tests ==="
  cat "$RUN_DIR/14_brief_tests.md"
  echo
} > "$FINAL_PROMPT"

# Try best synthesis model; if it fails, fallback.
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
