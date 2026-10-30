use std::env;
use std::io::Write;
/// يحمّل `.env` / `saqr.env` من مجلد التشغيل فقط — مع override لضمان قراءة المفاتيح.
pub fn load_env_files() {
    let Some(cwd) = env::current_dir().ok() else {
        eprintln!("[SAQR] WARN: cannot read current directory for .env");
        return;
    };

    let mut loaded_any = false;
    // saqr.env أولاً ثم .env (الأحدث يغلّب)
    for name in ["saqr.env", ".env"] {
        let path = cwd.join(name);
        if !path.is_file() {
            continue;
        }
        match dotenvy::from_path_override(&path) {
            Ok(()) => {
                loaded_any = true;
                eprintln!("[SAQR] env loaded (override): {}", path.display());
            }
            Err(e) => eprintln!("[SAQR] env parse error {}: {e}", path.display()),
        }
    }

    if !loaded_any {
        eprintln!("[SAQR] WARN: no saqr.env or .env in {}", cwd.display());
    }

    log_env_presence();
}

fn log_env_presence() {
    let keys = [
        "SAQR_MODE",
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
    ];
    for k in keys {
        let ok = env::var(k).map(|v| !v.trim().is_empty()).unwrap_or(false);
        eprintln!(
            "[SAQR] {k}: {}",
            if ok { "OK (set)" } else { "MISSING/empty" }
        );
    }
    let _ = std::io::stderr().flush();
}
