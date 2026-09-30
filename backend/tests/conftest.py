import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def avoid_unrequested_registration_network(monkeypatch, request):
    # Provider/parser tests must not accidentally fan out email fixtures to
    # 100+ real services. The dedicated adapter tests inject their own runtime.
    if request.node.path.name != "test_registered_accounts.py":
        monkeypatch.setattr("modules.registered_accounts.scan_registered_accounts",
                            lambda email: {"status": "skipped", "services": [], "checked": 0, "attempted": 0})
