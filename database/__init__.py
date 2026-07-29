"""قاعدة البيانات والنسخ الاحتياطي — المرحلة 9."""

from database.backup_manager import BackupManager, BackupResult, BackupScheduler
from database.connection import DatabaseConnection, init_database
from database.gdrive_uploader import GDriveUploadResult, upload_backup
from database.repositories.config_repo import ConfigRepository
from database.repositories.operations_repo import OperationsRepository
from database.repositories.snapshot_repo import SnapshotRepository
from database.repositories.trade_repo import TradeRepository, TradeRow
from database.telegram_backup import (
    TelegramBackupResult,
    send_vault_intro,
    upload_backup_to_telegram,
)

__all__ = [
    "BackupManager",
    "BackupResult",
    "BackupScheduler",
    "ConfigRepository",
    "DatabaseConnection",
    "GDriveUploadResult",
    "OperationsRepository",
    "SnapshotRepository",
    "TelegramBackupResult",
    "TradeRepository",
    "TradeRow",
    "init_database",
    "send_vault_intro",
    "upload_backup",
    "upload_backup_to_telegram",
]
