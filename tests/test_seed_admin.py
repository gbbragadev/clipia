"""Test the admin seed script idempotency and output."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_seed_creates_admin_when_absent(tmp_path, monkeypatch):
    """When no admin user exists, creates one and writes credentials file."""
    cred_file = tmp_path / ".admin-credentials.local"

    # Import the module fresh so we can patch its internals
    seed_module = importlib.import_module("scripts.seed_admin")
    monkeypatch.setattr(seed_module, "CREDENTIALS_PATH", cred_file)

    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch.object(seed_module, "async_session", return_value=mock_session):
        await seed_module.seed_admin()

    assert cred_file.exists()
    content = cred_file.read_text()
    assert "admin@gui" in content or "gbbraga.dev@gmail.com" in content
    assert "password" in content.lower()
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited()


@pytest.mark.asyncio
async def test_seed_is_idempotent_when_admin_exists(tmp_path, monkeypatch):
    """When admin already exists, does not recreate and does not write file."""
    cred_file = tmp_path / ".admin-credentials.local"

    seed_module = importlib.import_module("scripts.seed_admin")
    monkeypatch.setattr(seed_module, "CREDENTIALS_PATH", cred_file)

    existing_user = MagicMock()
    existing_user.email = "gbbraga.dev@gmail.com"
    existing_user.id = "fake-uuid"

    mock_session = MagicMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_user)))
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    with patch.object(seed_module, "async_session", return_value=mock_session):
        await seed_module.seed_admin()

    assert not cred_file.exists()
    mock_session.add.assert_not_called()
