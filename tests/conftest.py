import pytest
from dotenv import load_dotenv

load_dotenv()

# The heuristic backend is always available, so live-pipeline tests never skip.
# Under a real model backend they cost a few cents each.
needs_api = pytest.mark.usefixtures()
