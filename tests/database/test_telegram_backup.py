from database.telegram_backup import format_backup_caption, upload_backup_to_telegram


def test_format_backup_caption_contains_vault_branding():
    text = format_backup_caption(
        filename="goldenshield_20260101_120000.db",
        size_bytes=2048,
        env="dev",
        mode="paper",
    )
    assert "النسخ الاحتياطي" in text
    assert "goldenshield_20260101_120000.db" in text
    assert "paper" in text
    assert "restore_backup.py" in text


def test_upload_without_channel_id(monkeypatch, tmp_path):
    class _Settings:
        telegram_token = "dummy-token"
        telegram_backup_channel_id = None
        telegram_chat_id = None
        env = "dev"
        execution_mode = "paper"

    monkeypatch.setattr(
        "database.telegram_backup.get_settings",
        lambda: _Settings(),
    )
    db = tmp_path / "sample.db"
    db.write_bytes(b"sqlite")
    result = upload_backup_to_telegram(str(db))
    assert result.uploaded is False
    assert "غير مُعدّ" in result.message
