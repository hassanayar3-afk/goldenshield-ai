from database.gdrive_uploader import upload_backup


def test_gdrive_missing_config():
    result = upload_backup("missing.db")
    assert result.uploaded is False
    assert "GDRIVE" in result.message or "غير موجود" in result.message
