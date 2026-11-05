import os

import pytest

os.environ.setdefault("POLICYLAB_PROVIDER", "mock")
os.environ.pop("ANTHROPIC_API_KEY", None)

from policylab.codebook import load_codebook  # noqa: E402
from policylab.retrieval import HybridRetriever  # noqa: E402
from policylab.store import load_corpus  # noqa: E402


@pytest.fixture(scope="session")
def corpus():
    return load_corpus()


@pytest.fixture(scope="session")
def bm25(corpus):
    return HybridRetriever(corpus)


@pytest.fixture(scope="session")
def codebook():
    return load_codebook()
