.PHONY: validate links triage assess eval eval-compare site report test all

validate:          ## schema, dates, sourcing discipline, staleness
	python3 src/validate.py

links:             ## as above, plus check every source URL resolves
	python3 src/validate.py --links

triage:            ## run both worked inquiry examples
	python3 src/triage.py workflow/examples/INQ-2026-014.yaml
	@echo
	python3 src/triage.py workflow/examples/INQ-2026-031.yaml

assess:            ## run the worked readiness assessment
	python3 readiness/assess.py readiness/worked-example/au-smma-assessment.yaml

eval:              ## evaluate the current extraction prompt (needs Ollama)
	python3 toolkit/eval/run_eval.py --models llama3.2:3b,llama3.1:8b,gemma2:9b,mistral-nemo:12b,qwen2.5:14b

eval-compare:      ## re-run the superseded v1 prompt to reproduce the guardrail delta
	python3 toolkit/eval/run_eval.py --prompt toolkit/prompts/obligation_extraction_v1.md \
		--models llama3.2:3b,llama3.1:8b,gemma2:9b,mistral-nemo:12b,qwen2.5:14b

site:              ## regenerate the static tracker site into site/
	python3 src/build_site.py

report:            ## the monthly re-verification work item, printed locally
	python3 src/report.py --links --case-study

test:              ## run the test suite
	# PYTEST_DISABLE_PLUGIN_AUTOLOAD guards against unrelated pytest plugins in a
	# shared Anaconda environment failing at import before any test runs.
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest tests/

all: validate test site
