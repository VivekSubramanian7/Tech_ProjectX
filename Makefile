.PHONY: test enum scan eval lint-engine dev

export PYTHONPATH := engine:eval

test:
	pytest eval engine/tests -q

enum:
	python enum/generate.py

eval:
	python eval/run_eval.py

scan:
	python scripts/run_scan.py $(if $(PATH),--path "$(PATH)",)

lint-engine:
	cd engine && ruff check app tests && mypy app

dev:
	powershell -ExecutionPolicy Bypass -File launch.ps1
