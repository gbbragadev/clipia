import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _script(name: str) -> str:
    return (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")


def test_rebuild_uses_versioned_candidate_before_stopping_active_frontend():
    script = _script("restart-frontend.ps1")

    build_marker = "NEXT_DIST_DIR=$candidateDistDir"
    candidate_marker = "Start-FrontendProcess -Port $CandidatePort"
    stop_active_marker = "Stop-FrontendProduction"

    assert ".next-releases" in script
    assert build_marker in script
    assert candidate_marker in script
    assert "-Port 3004" in script
    assert script.index(build_marker) < script.index(candidate_marker)
    assert script.index(candidate_marker) < script.rindex(stop_active_marker)


def test_versioned_build_restores_next_generated_tsconfig_changes():
    script = _script("restart-frontend.ps1")

    assert "[System.IO.File]::ReadAllBytes($tsconfigPath)" in script
    assert "[System.IO.File]::WriteAllBytes($tsconfigPath, $tsconfigBytes)" in script
    assert script.index("[System.IO.File]::ReadAllBytes($tsconfigPath)") < script.index("& npm.cmd run build")


def test_promotion_is_pointer_based_smoked_and_rolls_back_on_failure():
    script = _script("restart-frontend.ps1")

    assert "frontend-active-build.txt" in script
    assert "Move-Item -LiteralPath $tempPointer" in script
    assert "Test-FrontendSmoke -Port $CandidatePort" in script
    assert "Test-FrontendSmoke -Port $ProductionPort" in script
    assert "Write-ActiveBuildPointer -DistDir $previousDistDir" in script
    assert "Rollback" in script
    assert "Remove-Item -LiteralPath $previousBuildPath -Recurse" not in script


def test_runtime_launcher_reads_active_pointer_and_keeps_legacy_fallback():
    launcher = _script("_run-frontend.ps1")

    assert "frontend-active-build.txt" in launcher
    assert '$activeDistDir = ".next"' in launcher
    assert "$env:NEXT_DIST_DIR = $activeDistDir" in launcher
    assert "npm.cmd run start -- -p 3003" in launcher


def test_windows_service_uses_pointer_aware_launcher():
    installer = _script("install-windows-services.ps1")

    assert "_run-frontend.ps1" in installer
    assert '-Exe "$powershellExe"' in installer
    assert '-Arguments "-NoProfile -ExecutionPolicy Bypass -File' in installer


def test_production_boot_stops_old_pointer_aware_loop_before_port_owner():
    startup = _script("start-production.ps1")

    launcher_marker = "*_run-frontend.ps1*"
    port_marker = "Get-NetTCPConnection -LocalPort 3003"
    assert launcher_marker in startup
    assert startup.index(launcher_marker) < startup.index(port_marker)


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell parser unavailable")
@pytest.mark.parametrize(
    "script_name",
    ["restart-frontend.ps1", "_run-frontend.ps1", "_run-frontend-once.ps1"],
)
def test_powershell_scripts_parse(script_name):
    path = REPO_ROOT / "scripts" / script_name
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
