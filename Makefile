# AEGIS -- common tasks.  Usage:  make <target>
PY ?= python

.PHONY: help install test demo run dashboard docker

help:
	@echo "targets:"
	@echo "  install    pip install control-plane requirements"
	@echo "  test       run all control-plane + pipeline + model checks"
	@echo "  demo       narrate the full attack -> quarantine story"
	@echo "  run        start the control plane on :8000"
	@echo "  dashboard  start the dashboard dev server on :5174"
	@echo "  docker     build + run the control plane in Docker"

install:
	$(PY) -m pip install -r control-plane/requirements.txt

test:
	cd control-plane && $(PY) verify_approvals.py && $(PY) verify_auth.py && $(PY) verify_mfa.py && $(PY) verify_oauth.py
	$(PY) e2e_pipeline.py
	cd fpga-scorer && $(PY) build.py && $(PY) eval_report.py

demo:
	$(PY) run_demo.py

run:
	cd control-plane && uvicorn main:app --port 8000

dashboard:
	cd dashboard && npm install && npm run dev

docker:
	docker compose up --build
