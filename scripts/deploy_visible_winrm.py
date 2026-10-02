"""نشر حزمة التشغيل المرئية إلى Windows VPS عبر WinRM (عندما يكون SSH مغلقاً)."""
from __future__ import annotations

import base64
import os
from pathlib import Path

import sys

import winrm
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from deploy_visible_launch_package import PS, REMOTE, UPLOAD  # noqa: E402


def _session() -> winrm.Session:
    load_dotenv(ROOT / ".env", override=True)
    host = (os.getenv("WIN_HOST") or "").strip()
    user = (os.getenv("WIN_USER") or "Administrator").strip()
    password = os.getenv("WIN_PASSWORD") or ""
    if not (host and password):
        raise SystemExit("missing WIN_HOST or WIN_PASSWORD")
    url = f"http://{host}:5985/wsman"
    return winrm.Session(
        url,
        auth=(user, password),
        transport="basic",
        server_cert_validation="ignore",
        read_timeout_sec=300,
        operation_timeout_sec=120,
    )


def _upload_file(session: winrm.Session, local: Path, remote: str) -> None:
    raw = local.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    remote_ps = remote.replace("'", "''")
    chunk_size = 600
    chunks = [b64[i : i + chunk_size] for i in range(0, len(b64), chunk_size)] or [""]
    for idx, chunk in enumerate(chunks):
        chunk_esc = chunk.replace("'", "''")
        if idx == 0:
            ps = f"""
$path = '{remote_ps}'
$dir = Split-Path -Parent $path
if (-not (Test-Path $dir)) {{ New-Item -ItemType Directory -Force -Path $dir | Out-Null }}
if (Test-Path $path) {{ Remove-Item $path -Force }}
$acc = New-Object System.Text.StringBuilder
[void]$acc.Append('{chunk_esc}')
Set-Content -Path ($path + '.b64part') -Value $acc.ToString() -Encoding ASCII -NoNewline
"""
        else:
            ps = f"""
$acc = Get-Content -Path ('{remote_ps}' + '.b64part') -Raw -Encoding ASCII
$acc += '{chunk_esc}'
Set-Content -Path ('{remote_ps}' + '.b64part') -Value $acc -Encoding ASCII -NoNewline
"""
        r = session.run_ps(ps)
        if r.status_code != 0:
            err = (r.std_err or b"").decode("utf-8", errors="replace")
            raise RuntimeError(f"upload chunk failed {remote}: {err[-500:]}")
    fin = f"""
$path = '{remote_ps}'
$b64 = Get-Content -Path ($path + '.b64part') -Raw -Encoding ASCII
[IO.File]::WriteAllBytes($path, [Convert]::FromBase64String($b64))
Remove-Item ($path + '.b64part') -Force -EA SilentlyContinue
Write-Output ('WROTE ' + $path)
"""
    r = session.run_ps(fin)
    if r.status_code != 0:
        err = (r.std_err or b"").decode("utf-8", errors="replace")
        raise RuntimeError(f"upload finalize failed {remote}: {err[-500:]}")


def main() -> int:
    session = _session()
    probe = session.run_cmd("hostname")
    if probe.status_code != 0:
        print("WINRM probe failed")
        return 1
    print("HOST", probe.std_out.decode().strip())

    for rel in UPLOAD:
        local = ROOT / rel
        if not local.is_file():
            print("SKIP", rel)
            continue
        remote = REMOTE + "\\" + rel.replace("/", "\\")
        _upload_file(session, local, remote)
        print("UP", rel)

    remote_ps_path = r"C:\Users\Public\gs_deploy_visible_pkg.ps1"
    staging = ROOT / "storage" / "runtime" / "_winrm_deploy_staging.ps1"
    staging.parent.mkdir(parents=True, exist_ok=True)
    staging.write_text(PS, encoding="utf-8")
    _upload_file(session, staging, remote_ps_path)
    print("UP deploy_ps1")

    r = session.run_cmd(
        f'powershell -NoProfile -ExecutionPolicy Bypass -File "{remote_ps_path}"'
    )
    out = (r.std_out or b"").decode("utf-8", errors="replace")
    err = (r.std_err or b"").decode("utf-8", errors="replace")
    try:
        print(out)
    except UnicodeEncodeError:
        print(out.encode("ascii", "replace").decode("ascii"))
    if err.strip():
        print("STDERR:", err[-1500:])
    if r.status_code != 0:
        print("REMOTE_PS_EXIT", r.status_code)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
