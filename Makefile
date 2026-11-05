# Policy Surveillance AI Lab
PY ?= python

.PHONY: help install install-ml corpus index test lint eval eval-ci site app demo gold clean

help:
	@echo "make install     install runtime + dev dependencies"
	@echo "make install-ml  add the local embedding model (CPU torch + sentence-transformers)"
	@echo "make corpus      rebuild the corpus from the Federal Register API + GovInfo (network)"
	@echo "make index       build the local embedding index for hybrid search"
	@echo "make test        lint + unit tests (mock LLM, no API key)"
	@echo "make eval        run the evaluation (offline baseline) -> eval/results.md"
	@echo "make site        build the static GitHub Pages site -> _site/"
	@echo "make app         run the Streamlit app"

install:
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -m pip install -e . --no-deps

install-ml:
	$(PY) -m pip install torch --index-url https://download.pytorch.org/whl/cpu
	$(PY) -m pip install -r requirements-ml.txt

corpus:
	$(PY) -m policylab.corpus

index:
	$(PY) -m policylab.retrieval

lint:
	ruff check .
	ruff format --check policylab tests app

test: lint
	POLICYLAB_PROVIDER=mock $(PY) -m pytest

eval:
	POLICYLAB_PROVIDER=mock $(PY) -m policylab.evaluation --provider mock

# CI variant: BM25 only, no model download
eval-ci:
	POLICYLAB_PROVIDER=mock $(PY) -m policylab.evaluation --provider mock --no-embeddings

site:
	$(PY) -m policylab.site

app:
	streamlit run app/streamlit_app.py

demo:
	$(PY) -m policylab.demo

gold:
	$(PY) eval/gold/starter_drafts.py

clean:
	rm -rf _site .pytest_cache .ruff_cache data/index
