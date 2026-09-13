import os

import pytest
from dotenv import load_dotenv

load_dotenv()

needs_api = pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="ANTHROPIC_API_KEY not set")
