PY := .venv/bin/python
RUNS ?= 1

.PHONY: setup test eval ablate demo doctor report check baseline dashboard clean

setup:
	python3 -m venv .venv && $(PY) -m pip install -q -e ".[dev]"

test:
	$(PY) -m pytest -q

## Full replay plus both ablations and the no-telemetry fault run, then the
## regression gate against evals/baseline.json. RUNS=3 adds flip-rate analysis.
eval:
	rm -rf evals/reports/run_*
	$(PY) -m evals.run --quiet --runs $(RUNS)
	$(PY) -m evals.run --quiet --ablate grounding
	$(PY) -m evals.run --quiet --ablate ownership
	$(PY) -m evals.run --quiet --no-telemetry
	$(PY) -m evals.report
	$(PY) -m evals.check
	$(PY) -m evals.dashboard

report:
	$(PY) -m evals.report

## Self-contained console page from the latest runs: replay, results, attacks, failures, integrations.
dashboard:
	$(PY) -m evals.dashboard
	open evals/reports/dashboard.html 2>/dev/null || true

check:
	$(PY) -m evals.check

## Freeze the current numbers as the baseline the gate compares against.
baseline:
	$(PY) -m evals.check --write-baseline

demo:
	$(PY) -m switchboard.demo

doctor:
	$(PY) -m switchboard.doctor

clean:
	rm -rf evals/reports/run_* wal.json state.json .switchboard-cache
