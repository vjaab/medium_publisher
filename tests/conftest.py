import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture(autouse=True)
def setup_test_env():
    import os
    os.environ['LLM_API_KEY'] = 'test-key'
    os.environ['SEARCH_API_KEY'] = 'test-key'
    os.environ['MEDIUM_TOKEN'] = 'test-token'
    os.environ['DRY_RUN'] = 'true'
    yield