import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def _script(name: str) -> str:
    path = SCRIPTS / name
    assert path.exists(), f"missing operational script: {path}"
    return path.read_text(encoding="utf-8")


def test_watchdog_covers_origin_dependencies_tunnel_and_alerting():
    script = _script("watchdog-production.ps1")

    assert "http://127.0.0.1:8005/health" in script
    assert "http://127.0.0.1:8005/health/deep" in script
    assert "http://127.0.0.1:3003/" in script
    assert "https://clipia.com.br/" in script
    assert "_run-backend.ps1" in script
    assert "_run-worker.ps1" in script
    assert "_run-frontend.ps1" in script
    assert "_run-tunnel.ps1" in script
    assert "CLIPIA_WPP_NUMBER" in script
    assert "5545998296112" in script
    assert "Send-Alert" in script


def test_watchdog_uses_deep_health_payload_instead_of_only_http_200():
    script = _script("watchdog-production.ps1")

    assert "ConvertFrom-Json" in script
    assert ".checks.database.status" in script
    assert ".checks.redis.status" in script
    assert ".checks.celery.status" in script
    assert 'status -ne "up"' in script


def test_backend_launcher_imports_production_host_policy_from_user_environment():
    script = _script("_run-backend.ps1")

    assert "METRICS_TOKEN" in script
    assert "TRUSTED_HOSTS" in script


def test_installer_registers_full_watchdog_every_two_minutes_and_retires_tunnel_only_task():
    script = _script("install-production-watchdog.ps1")

    assert "ClipIA Production Watchdog" in script
    assert "watchdog-production.ps1" in script
    assert "New-TimeSpan -Minutes 2" in script
    assert "StartWhenAvailable" in script
    assert "ClipIA Tunnel Watchdog" in script
    assert "Disable-ScheduledTask" in script


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell parser unavailable")
@pytest.mark.parametrize(
    "script_name",
    ["watchdog-production.ps1", "install-production-watchdog.ps1"],
)
def test_watchdog_scripts_parse(script_name):
    path = SCRIPTS / script_name
    assert path.exists(), f"missing operational script: {path}"
    command = (
        "$errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$null, [ref]$errors) > $null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
