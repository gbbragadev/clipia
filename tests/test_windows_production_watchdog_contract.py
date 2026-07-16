import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def _script(name: str) -> str:
    path = SCRIPTS / name
    assert path.exists(), f"missing operational script: {path}"
    return path.read_text(encoding="utf-8")


def _run_powershell(script: str, *, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _core_preamble() -> str:
    core = SCRIPTS / "watchdog-production-core.ps1"
    return f"$ErrorActionPreference = 'Stop'; . '{core}'"


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
    assert "Send-Alert" in script


def test_watchdog_has_no_personal_default_alert_recipient():
    script = _script("watchdog-production.ps1")

    assert "5545998296112" not in script


@pytest.mark.parametrize("root_path", [".playwright-cli/session.json", "outputs/report.json"])
def test_local_qa_ignores_apply_only_at_repository_root(root_path: str):
    root_result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", root_path],
        cwd=REPO_ROOT,
        check=False,
    )
    nested_result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", f"app/{root_path}"],
        cwd=REPO_ROOT,
        check=False,
    )

    assert root_result.returncode == 0
    assert nested_result.returncode == 1


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell unavailable")
def test_null_deep_health_recovers_containers_restarts_backend_and_rechecks():
    command = textwrap.dedent(
        f"""
        {_core_preamble()}
        $events = [System.Collections.Generic.List[string]]::new()
        $healthy = [pscustomobject]@{{
            status = 'healthy'
            checks = [pscustomobject]@{{
                database = [pscustomobject]@{{ status = 'up' }}
                redis = [pscustomobject]@{{ status = 'up' }}
                celery = [pscustomobject]@{{ status = 'up' }}
                storage = [pscustomobject]@{{ status = 'up'; writable = $true }}
            }}
        }}
        $result = Repair-NullDeepHealth -EnsureContainers {{
            [void]$events.Add('containers')
            return $true
        }} -RestartBackend {{
            [void]$events.Add('backend')
        }} -GetDeepHealth {{
            [void]$events.Add('health')
            return $healthy
        }} -WaitForBackend {{
            [void]$events.Add('wait')
        }}
        if (($events -join ',') -ne 'containers,backend,wait,health') {{
            throw "unexpected recovery order: $($events -join ',')"
        }}
        if (-not (Test-DeepHealthPayload -Health $result)) {{
            throw 'rechecked health was not returned'
        }}
        """
    )

    completed = _run_powershell(command)

    assert completed.returncode == 0, completed.stderr or completed.stdout


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell unavailable")
@pytest.mark.parametrize(
    ("storage_status", "writable"),
    [("down", "$true"), ("up", "$false")],
)
def test_deep_health_rejects_degraded_or_read_only_storage(storage_status: str, writable: str):
    command = textwrap.dedent(
        f"""
        {_core_preamble()}
        $health = [pscustomobject]@{{
            status = 'healthy'
            checks = [pscustomobject]@{{
                database = [pscustomobject]@{{ status = 'up' }}
                redis = [pscustomobject]@{{ status = 'up' }}
                celery = [pscustomobject]@{{ status = 'up' }}
                storage = [pscustomobject]@{{ status = '{storage_status}'; writable = {writable} }}
            }}
        }}
        if (Test-DeepHealthPayload -Health $health) {{
            throw 'invalid storage health was accepted'
        }}
        """
    )

    completed = _run_powershell(command)

    assert completed.returncode == 0, completed.stderr or completed.stdout


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell unavailable")
def test_frontend_pointer_must_match_build_served_by_origin(tmp_path: Path):
    frontend = tmp_path / "frontend"
    storage = tmp_path / "storage"
    build = frontend / ".next-releases" / "release-a"
    build.mkdir(parents=True)
    storage.mkdir()
    (build / "BUILD_ID").write_text("build-a\n", encoding="ascii")
    (storage / "frontend-active-build.txt").write_text(".next-releases/release-a\n", encoding="ascii")
    root = str(tmp_path).replace("'", "''")
    command = textwrap.dedent(
        f"""
        {_core_preamble()}
        $requested = $null
        $matches = Test-FrontendActiveBuild -Root '{root}' -ProbeBuild {{
            param($BuildId)
            $script:requested = $BuildId
            return $false
        }}
        if ($matches) {{ throw 'mismatched served build was accepted' }}
        if ($requested -ne 'build-a') {{ throw "wrong BUILD_ID probed: $requested" }}
        """
    )

    completed = _run_powershell(command)

    assert completed.returncode == 0, completed.stderr or completed.stdout


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell unavailable")
def test_stop_port_owner_refuses_unrelated_process_without_stopping_it():
    command = textwrap.dedent(
        f"""
        {_core_preamble()}
        $stopped = [System.Collections.Generic.List[int]]::new()
        $threw = $false
        try {{
            Stop-PortOwnerSafely -Port 3003 -Root 'C:\\Dev\\clipia' `
                -GetConnections {{ @([pscustomobject]@{{ OwningProcess = 4242 }}) }} `
                -GetProcessById {{ param($ProcessId) [pscustomobject]@{{ ProcessId = $ProcessId; CommandLine = 'python unrelated.py' }} }} `
                -StopProcess {{ param($ProcessId) [void]$stopped.Add($ProcessId) }}
        }} catch {{
            $threw = $true
        }}
        if (-not $threw) {{ throw 'unrelated process was not rejected' }}
        if ($stopped.Count -ne 0) {{ throw 'unrelated process was stopped' }}
        """
    )

    completed = _run_powershell(command)

    assert completed.returncode == 0, completed.stderr or completed.stdout


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
    [
        "watchdog-production-core.ps1",
        "watchdog-production.ps1",
        "install-production-watchdog.ps1",
    ],
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
