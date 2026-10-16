"""Telegram vault removed — Discord/GDrive backups only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelegramVaultResult:
    uploaded: bool
    message: str


def upload_backup_to_telegram(_path: str) -> TelegramVaultResult:
    return TelegramVaultResult(False, "telegram_removed")


def send_vault_intro() -> TelegramVaultResult:
    return TelegramVaultResult(False, "telegram_removed")
