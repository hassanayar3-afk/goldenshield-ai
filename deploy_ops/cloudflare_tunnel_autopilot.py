#!/usr/bin/env python3
"""
Cloudflare Named Tunnel autopilot for violafashioniq.com -> 127.0.0.1:8790

Requires (one of):
  - CLOUDFLARE_API_TOKEN (cfut_/cfat_ scoped token) + optional CLOUDFLARE_ACCOUNT_ID
  - CLOUDFLARE_GLOBAL_API_KEY (cfk_ legacy) + CLOUDFLARE_EMAIL
  - Existing CLOUDFLARE_TUNNEL_TOKEN in .env
  - Prior `cloudflared tunnel login` cert at %USERPROFILE%\\.cloudflared\\cert.pem (CLI create path)

Does NOT log secrets. Writes CLOUDFLARE_TUNNEL_TOKEN to .env when obtained via API.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path as _Path

_root_guess = _Path(__file__).resolve().parents[1]
if str(_root_guess) not in sys.path:
    sys.path.insert(0, str(_root_guess))
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from deploy_ops.logging_config import configure_sovereign_logging

log = configure_sovereign_logging("gs_tunnel_autopilot")

TUNNEL_NAME = os.getenv("CLOUDFLARE_TUNNEL_NAME", "GoldenShield-Tunnel")
PUBLIC_HOST = os.getenv(
    "CLOUDFLARE_TUNNEL_HOSTNAME",
    (os.getenv("MOBILE_PUBLIC_BASE_URL") or "https://violafashioniq.com").replace("https://", "")
    .replace("http://", "")
    .strip("/")
    .split("/")[0],
)
LOCAL_SERVICE = (os.getenv("CLOUDFLARE_TUNNEL_LOCAL_URL") or "http://127.0.0.1:8790").strip()
CF_API = "https://api.cloudflare.com/client/v4"


@dataclass(frozen=True)
class CfAuth:
    mode: str  # bearer | global
    bearer: str = ""
    global_key: str = ""
    email: str = ""


def _root() -> Path:
    raw = (os.getenv("GOLDENSHIELD_OFFICIAL_ROOT") or r"C:\GoldenShield_Binance").strip()
    p = Path(raw)
    return p if p.is_dir() else Path.cwd()


def _load_dotenv(root: Path) -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(root / ".env", override=True)
        load_dotenv(root / "goldenshield.env", override=False)
    except Exception:
        pass


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            t = line.strip()
            if not t or t.startswith("#") or "=" not in t:
                continue
            k, v = t.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return out


def _harvest_from_backups(root: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    keys = {
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_GLOBAL_API_KEY",
        "CLOUDFLARE_EMAIL",
        "CLOUDFLARE_ACCOUNT_ID",
        "CLOUDFLARE_TUNNEL_TOKEN",
        "CLOUDFLARE_ZONE_ID",
    }
    backup_dir = root / "storage" / "runtime" / "secrets_harvest"
    paths = [root / ".env", root / "goldenshield.env"]
    if backup_dir.is_dir():
        paths.extend(sorted(backup_dir.glob("*.bak"), reverse=True))
    for p in paths:
        for k, v in _parse_env_file(p).items():
            if k in keys and v and k not in found:
                found[k] = v
    return found


def _set_env_line(root: Path, key: str, value: str) -> None:
    env_path = root / ".env"
    raw = env_path.read_text(encoding="utf-8", errors="replace") if env_path.is_file() else ""
    line = f"{key}={value}"
    pat = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    if pat.search(raw):
        raw = pat.sub(line, raw, count=1)
    else:
        raw = raw.rstrip() + f"\n{line}\n"
    env_path.write_text(raw, encoding="utf-8")
    os.environ[key] = value


def _resolve_cf_auth() -> CfAuth | None:
    raw = (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip()
    gkey = (os.getenv("CLOUDFLARE_GLOBAL_API_KEY") or "").strip()
    email = (os.getenv("CLOUDFLARE_EMAIL") or os.getenv("CLOUDFLARE_API_EMAIL") or "").strip()
    if raw.startswith("cfk_"):
        gkey = raw if not gkey else gkey
        raw = ""
    if gkey.startswith("cfk_"):
        if not email:
            return None
        return CfAuth(mode="global", global_key=gkey, email=email)
    if raw and not raw.startswith("cfk_"):
        return CfAuth(mode="bearer", bearer=raw)
    return None


def _cf_request(
    method: str,
    path: str,
    auth: CfAuth,
    body: dict | None = None,
) -> dict:
    url = f"{CF_API}{path}"
    data = None
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "User-Agent": "GoldenShield-Tunnel-Autopilot/1.0",
    }
    if auth.mode == "bearer":
        headers["Authorization"] = f"Bearer {auth.bearer}"
    else:
        headers["X-Auth-Email"] = auth.email
        headers["X-Auth-Key"] = auth.global_key
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"Cloudflare API {method} {path} HTTP {exc.code}: {err_body}") from exc


def _resolve_account_id(auth: CfAuth, hinted: str) -> str:
    if hinted:
        return hinted
    data = _cf_request("GET", "/accounts", auth)
    results = data.get("result") or []
    if not results:
        raise RuntimeError("No Cloudflare accounts visible for API token")
    if len(results) == 1:
        return str(results[0]["id"])
    raise RuntimeError("Multiple Cloudflare accounts — set CLOUDFLARE_ACCOUNT_ID in .env")


def _resolve_zone_id(auth: CfAuth, domain: str, hinted: str) -> str:
    if hinted:
        return hinted
    data = _cf_request("GET", f"/zones?name={domain}", auth)
    results = data.get("result") or []
    if not results:
        raise RuntimeError(f"Zone not found for {domain} — add domain to Cloudflare or set CLOUDFLARE_ZONE_ID")
    return str(results[0]["id"])


def _find_or_create_tunnel(auth: CfAuth, account_id: str) -> str:
    listed = _cf_request("GET", f"/accounts/{account_id}/cfd_tunnel", auth)
    for t in listed.get("result") or []:
        if str(t.get("name", "")).lower() == TUNNEL_NAME.lower():
            return str(t["id"])
    secret = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    created = _cf_request(
        "POST",
        f"/accounts/{account_id}/cfd_tunnel",
        auth,
        {
            "name": TUNNEL_NAME,
            "config_src": "cloudflare",
            "tunnel_secret": secret,
        },
    )
    return str((created.get("result") or {})["id"])


def _configure_ingress(auth: CfAuth, account_id: str, tunnel_id: str, hostname: str, service: str) -> None:
    _cf_request(
        "PUT",
        f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
        auth,
        {
            "config": {
                "ingress": [
                    {"hostname": hostname, "service": service},
                    {"service": "http_status:404"},
                ]
            }
        },
    )


def _fetch_tunnel_token(auth: CfAuth, account_id: str, tunnel_id: str) -> str:
    data = _cf_request("GET", f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/token", auth)
    tok = data.get("result")
    if isinstance(tok, str) and tok.strip():
        return tok.strip()
    raise RuntimeError("Empty tunnel token from Cloudflare API")


def _ensure_dns_cname(auth: CfAuth, zone_id: str, hostname: str, tunnel_id: str) -> None:
    target = f"{tunnel_id}.cfargotunnel.com"
    listed = _cf_request("GET", f"/zones/{zone_id}/dns_records?name={hostname}", auth)
    records = listed.get("result") or []
    for rec in records:
        if str(rec.get("type")) == "CNAME" and str(rec.get("content", "")).lower() == target.lower():
            return
        rid = rec.get("id")
        if rid and rec.get("type") in {"A", "AAAA", "CNAME"}:
            _cf_request("DELETE", f"/zones/{zone_id}/dns_records/{rid}", auth)
    _cf_request(
        "POST",
        f"/zones/{zone_id}/dns_records",
        auth,
        {
            "type": "CNAME",
            "name": hostname,
            "content": target,
            "proxied": True,
        },
    )


def _cloudflared_exe(root: Path) -> Path:
    deploy_ops_tools = root / "deploy_ops" / "tools" / "cloudflared.exe"
    bundled = root / "tools" / "cloudflared.exe"
    for candidate in (bundled, deploy_ops_tools):
        if candidate.is_file():
            return candidate
    found = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
    if found:
        return Path(found)
    deploy_ops_tools.parent.mkdir(parents=True, exist_ok=True)
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    log.info("Downloading cloudflared to %s", deploy_ops_tools)
    urllib.request.urlretrieve(url, deploy_ops_tools)  # noqa: S310
    return deploy_ops_tools


def _stop_cloudflared() -> None:
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -EA SilentlyContinue | "
                "Where-Object { $_.CommandLine -match 'cloudflared' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }",
            ],
            check=False,
            capture_output=True,
        )


def _start_cloudflared(root: Path, exe: Path, token: str) -> None:
    log_dir = root / "storage" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "cloudflare_tunnel.log"
    _stop_cloudflared()
    subprocess.Popen(  # noqa: S603
        [
            str(exe),
            "tunnel",
            "run",
            "--token",
            token,
            "--logfile",
            str(log_file),
            "--loglevel",
            "info",
        ],
        cwd=str(root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def _ensure_local_api(root: Path) -> bool:
    try:
        import urllib.request as u

        with u.urlopen("http://127.0.0.1:8790/api/health", timeout=5) as r:
            return r.status == 200
    except Exception:
        pass
    py = shutil.which("python") or shutil.which("python3") or "python"
    subprocess.Popen(  # noqa: S603
        [py, "-m", "terminal_app.server"],
        cwd=str(root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    for _ in range(12):
        time.sleep(2)
        try:
            import urllib.request as u

            with u.urlopen("http://127.0.0.1:8790/api/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            continue
    return False


def _restart_pm2(root: Path) -> None:
    eco = root / "deploy_ops" / "pm2.ecosystem.config.cjs"
    if not eco.is_file():
        return
    pm2 = shutil.which("pm2")
    if not pm2:
        log.warning("pm2 not in PATH — skipped PM2 restart")
        return
    subprocess.run([pm2, "start", str(eco), "--update-env"], cwd=str(root), check=False)  # noqa: S603
    subprocess.run([pm2, "restart", "GS-Tunnel", "GS-Gateway", "GS-MobileApi"], cwd=str(root), check=False)  # noqa: S603


def _public_health(url: str, attempts: int = 12) -> tuple[bool, str]:
    base = url.rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base
    health = f"{base}/api/health"
    last = ""
    for i in range(attempts):
        try:
            req = urllib.request.Request(health, headers={"User-Agent": "GoldenShield-Autopilot/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read(500).decode("utf-8", errors="replace")
                if resp.status == 200 and "ok" in body.lower():
                    return True, body
                last = f"HTTP {resp.status} {body[:120]}"
        except Exception as exc:
            last = str(exc)
        time.sleep(5)
    return False, last


def run_autopilot() -> dict:
    root = _root()
    os.chdir(root)
    _load_dotenv(root)
    harvested = _harvest_from_backups(root)
    for k, v in harvested.items():
        os.environ.setdefault(k, v)

    report: dict = {
        "ok": False,
        "hostname": PUBLIC_HOST,
        "local_service": LOCAL_SERVICE,
        "tunnel_name": TUNNEL_NAME,
        "steps": [],
    }

    static_url = (os.getenv("MOBILE_PUBLIC_BASE_URL") or f"https://{PUBLIC_HOST}/").strip()
    if not static_url.endswith("/"):
        static_url += "/"
    _set_env_line(root, "MOBILE_PUBLIC_BASE_URL", static_url.rstrip("/") + "/")
    _set_env_line(root, "GS_BAN_QUICK_TUNNEL", "true")
    _set_env_line(root, "CLOUDFLARE_TUNNEL_ENABLED", "true")
    report["steps"].append("env_static_url")

    exe = _cloudflared_exe(root)
    report["steps"].append("cloudflared_ready")

    run_token = (os.getenv("CLOUDFLARE_TUNNEL_TOKEN") or harvested.get("CLOUDFLARE_TUNNEL_TOKEN") or "").strip()
    cf_auth = _resolve_cf_auth()
    if not cf_auth and (os.getenv("CLOUDFLARE_API_TOKEN") or "").strip().startswith("cfk_"):
        report["error"] = "global_api_key_needs_email"
        report["hint"] = (
            "cfk_ is Global API Key (not Bearer token). Set CLOUDFLARE_EMAIL=your@cloudflare-login "
            "and CLOUDFLARE_GLOBAL_API_KEY=cfk_... OR create scoped API token (cfut_) with Tunnel+DNS Edit"
        )

    if not run_token and cf_auth:
        try:
            account_id = _resolve_account_id(cf_auth, (os.getenv("CLOUDFLARE_ACCOUNT_ID") or "").strip())
            zone_id = _resolve_zone_id(
                cf_auth,
                PUBLIC_HOST,
                (os.getenv("CLOUDFLARE_ZONE_ID") or harvested.get("CLOUDFLARE_ZONE_ID") or "").strip(),
            )
            tunnel_id = _find_or_create_tunnel(cf_auth, account_id)
            _configure_ingress(cf_auth, account_id, tunnel_id, PUBLIC_HOST, LOCAL_SERVICE)
            _ensure_dns_cname(cf_auth, zone_id, PUBLIC_HOST, tunnel_id)
            run_token = _fetch_tunnel_token(cf_auth, account_id, tunnel_id)
            _set_env_line(root, "CLOUDFLARE_TUNNEL_TOKEN", run_token)
            _set_env_line(root, "CLOUDFLARE_ACCOUNT_ID", account_id)
            _set_env_line(root, "CLOUDFLARE_ZONE_ID", zone_id)
            if cf_auth.mode == "global":
                _set_env_line(root, "CLOUDFLARE_GLOBAL_API_KEY", cf_auth.global_key)
                _set_env_line(root, "CLOUDFLARE_EMAIL", cf_auth.email)
            report["steps"].append("api_tunnel_provisioned")
        except Exception as exc:
            report["error"] = f"api_provision_failed:{exc}"
            log.error("API provision failed: %s", exc)

    if not run_token:
        cert = Path.home() / ".cloudflared" / "cert.pem"
        if cert.is_file() and exe.is_file():
            report["steps"].append("cert_found_cli_fallback")
            try:
                subprocess.run(  # noqa: S603
                    [str(exe), "tunnel", "create", TUNNEL_NAME],
                    cwd=str(root),
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                subprocess.run(  # noqa: S603
                    [str(exe), "tunnel", "route", "dns", TUNNEL_NAME, PUBLIC_HOST],
                    cwd=str(root),
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                report["steps"].append("cli_tunnel_created_needs_token")
            except Exception as exc:
                report["error"] = f"cli_fallback_failed:{exc}"
        else:
            report["error"] = report.get(
                "error",
                "missing_credentials: set CLOUDFLARE_API_TOKEN (+ optional ACCOUNT_ID) or CLOUDFLARE_TUNNEL_TOKEN",
            )
            report["hint"] = report.get(
                "hint",
                "Use cfut_ API token (Bearer) or cfk_ Global Key + CLOUDFLARE_EMAIL, "
                "or CLOUDFLARE_TUNNEL_TOKEN from Zero Trust dashboard",
            )
            print(json.dumps(report, indent=2))
            return report

    runtime = root / "storage" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "mobile_tunnel_url.txt").write_text(static_url + "\n", encoding="utf-8")
    report["steps"].append("tunnel_url_file")

    api_ok = _ensure_local_api(root)
    report["local_api"] = api_ok
    report["steps"].append("local_api_checked")

    _start_cloudflared(root, exe, run_token)
    report["steps"].append("cloudflared_started")
    try:
        _restart_pm2(root)
        report["steps"].append("pm2_restart_attempted")
    except Exception as exc:
        report["pm2_note"] = str(exc)

    live, detail = _public_health(static_url)
    report["public_health_ok"] = live
    report["public_health_detail"] = detail[:200]
    report["ok"] = live and api_ok
    print(json.dumps(report, indent=2))
    return report


def main() -> int:
    rep = run_autopilot()
    return 0 if rep.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
