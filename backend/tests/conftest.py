from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import settings


@pytest.fixture(autouse=True)
def disable_management_rbac_for_general_tests():
    old_rbac_value = settings.ui_auth_enforce_permissions
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "ui_auth_enforce_permissions", False)
    object.__setattr__(settings, "single_account_mode", False)
    try:
        yield
    finally:
        object.__setattr__(settings, "ui_auth_enforce_permissions", old_rbac_value)
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)
