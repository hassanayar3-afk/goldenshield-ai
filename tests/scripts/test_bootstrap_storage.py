"""اختبارات تهيئة قاعدة البيانات."""

from __future__ import annotations

from scripts.bootstrap_storage import bootstrap


def test_bootstrap_creates_database(tmp_path, monkeypatch):
    db_path = tmp_path / "storage" / "db" / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("ENV", "dev")

    from config.settings import load_settings

    load_settings("dev", reload=True)
    path = bootstrap(reload_settings=True)
    assert path == str(db_path)
    assert db_path.exists()
