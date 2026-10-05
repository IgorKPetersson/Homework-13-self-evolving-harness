#!/usr/bin/env bash
# Full reproducible pipeline: clean state -> tests -> baseline -> evolution ->
# adversarial candidates -> tamper demo -> verification -> report.
set -euo pipefail
cd "$(dirname "$0")"
ITERATIONS="${ITERATIONS:-60}"
SEED="${SEED:-13}"

rm -rf state logs results
mkdir -p results

echo "== 1. pin trusted harness files"
python -m harness lock

echo "== 2. unit + integration tests"
python -m unittest discover -s tests -v 2>&1 | tee results/tests.txt | tail -3

echo "== 3. seed version + baseline measurement"
python -m harness init
python -m harness baseline > results/baseline.json

echo "== 4. evolution ($ITERATIONS iterations, seed $SEED)"
python -m harness evolve --iterations "$ITERATIONS" --seed "$SEED" | tee results/evolution_run.txt

echo "== 5. adversarial / malformed candidates (all must be rejected)"
python -m adversarial.make_memorizer adversarial/07_memorizer.py
for f in adversarial/0*.py; do
  python -m harness submit "$f"
done | tee results/adversarial.txt

echo "== 6. tamper demo: modified evaluator copy must refuse to run"
TMP="$(mktemp -d)"
cp -r harness "$TMP/"
sed -i 's/return "REJECT", "R6 no measurable improvement"/return "ACCEPT", "rigged"/' "$TMP/harness/selection.py"
( cd "$TMP" && python -m harness verify ) > results/tamper_demo.txt 2>&1 \
  && { echo "TAMPER NOT DETECTED"; exit 1; } || echo "tampered copy refused (see results/tamper_demo.txt)"
rm -rf "$TMP"

echo "== 7. ablation: adaptive vs non-adaptive proposer (isolated temp state)"
python ablation.py "$ITERATIONS" | tee results/ablation.txt

echo "== 8. verify audit chain + integrity, write report"
python -m harness verify | tee results/verify.txt
python -m harness report > /dev/null
cat results/evolution_report.md | head -8
