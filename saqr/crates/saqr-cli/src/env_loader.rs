use std::path::PathBuf;

/// يحمّل `.env` / `saqr.env` من مسارات التشغيل (Windows bundle + dev).
pub fn load_env_files() {
    let mut candidates: Vec<PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join(".env"));
        candidates.push(cwd.join("saqr.env"));
        candidates.push(cwd.join("bin").join(".env"));
    }
    candidates.push(PathBuf::from(".env"));
    candidates.push(PathBuf::from("saqr.env"));
    candidates.push(PathBuf::from("/workspace/.env"));
    candidates.push(PathBuf::from("/workspace/saqr.env"));

    for path in candidates {
        if path.is_file() {
            let _ = dotenvy::from_path(&path);
            tracing::info!("Loaded env from {}", path.display());
        }
    }
    dotenvy::dotenv().ok();
}
