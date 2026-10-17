"""فحص وصول الوكيل السحابي إلى Windows VPS (SSH + WinRM)."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=True)


def tcp(host: str, port: int, timeout: float = 8.0) -> str:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        return "OPEN"
    except Exception as exc:
        return type(exc).__name__
    finally:
        s.close()


def main() -> int:
    host = (os.getenv("WIN_HOST") or "").strip()
    if not host:
        print("WIN_HOST missing")
        return 1
    print("WIN_HOST set", "pkey", bool(os.getenv("WIN_SSH_PRIVATE_KEY") or os.getenv("SSH_PRIVATE_KEY")))
    print("PORT_22", tcp(host, 22))
    print("PORT_5985", tcp(host, 5985))
    print("PORT_3389", tcp(host, 3389, timeout=5))

    try:
        from scripts._win_ssh import WindowsSSHError, connect_windows_ssh

        ssh = connect_windows_ssh(timeout=25)
        _, stdout, _ = ssh.exec_command("hostname", timeout=20)
        print("SSH_OK", stdout.read().decode("utf-8", errors="replace").strip())
        ssh.close()
    except WindowsSSHError as exc:
        print("SSH_FAIL", str(exc)[:240])
    except Exception as exc:
        print("SSH", type(exc).__name__)

    password = (os.getenv("WIN_PASSWORD") or "").strip()
    user = (os.getenv("WIN_USER") or "").strip()
    if password and user:
        try:
            import winrm

            if tcp(host, 5985, timeout=5) != "OPEN":
                print("WINRM skip (port 5985 not reachable)")
                raise RuntimeError("winrm_unreachable")
            session = winrm.Session(
                f"http://{host}:5985/wsman",
                auth=(user, password),
                transport="basic",
                server_cert_validation="ignore",
                read_timeout_sec=30,
                operation_timeout_sec=20,
            )
            r = session.run_cmd("hostname")
            if r.status_code == 0:
                print("WINRM_OK", (r.std_out or b"").decode().strip())
            else:
                print("WINRM_FAIL", r.status_code)
        except ImportError:
            print("WINRM skip (pip install pywinrm)")
        except RuntimeError as exc:
            if str(exc) != "winrm_unreachable":
                print("WINRM", type(exc).__name__)
        except Exception as exc:
            print("WINRM", type(exc).__name__)
    else:
        print("WINRM skip (no WIN_PASSWORD)")

    print(
        "NEXT: إن فشل SSH — أضف WIN_SSH_PRIVATE_KEY. "
        "إن فشل WinRM — فعّل PS Remoting وافتح 5985 في الجدار الناري."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
