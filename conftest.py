import pytest

import boa.interpret


@pytest.fixture(scope="session", autouse=True)
def _disable_boa_disk_cache():
    boa.interpret.disable_cache()
