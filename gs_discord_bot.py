#!/usr/bin/env python3
"""GoldenShield Sovereign Discord Bot — control plane via Mobile API + snapshot mirror."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import discord
from discord import ui
from dotenv import load_dotenv

ROOT = Path(os.getenv("GOLDENSHIELD_OFFICIAL_ROOT", r"C:\GoldenShield_Binance")).resolve()
RUNTIME = ROOT / "storage" / "runtime"
LOG_DIR = ROOT / "storage" / "logs"
SNAPSHOT_PATH = RUNTIME / "binance_snapshot.json"
HEALTH_URL = os.getenv("GS_MOBILE_HEALTH_URL", "http://127.0.0.1:8790/api/health").strip()
API_BASE = os.getenv("GS_MOBILE_API_BASE", "http://127.0.0.1:8790").strip().rstrip("/")

LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [gs_discord_bot] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "gs_discord_bot.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("gs_discord_bot")


def _load_env() -> None:
    env_path = ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path, override=False)
    os.environ.setdefault("GOLDENSHIELD_OFFICIAL_ROOT", str(ROOT))


def _api_token() -> str:
    return (
        os.getenv("MOBILE_API_TOKEN")
        or os.getenv("GS_MASTER_API_TOKEN")
        or os.getenv("MOBILE_MASTER_TOKEN")
        or ""
    ).strip()


def _read_snapshot() -> dict:
    try:
        if SNAPSHOT_PATH.is_file():
            data = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        log.warning("snapshot read: %s", exc)
    return {}


def _fmt_money(v: float | None) -> str:
    try:
        n = float(v)
        return f"${n:,.2f}"
    except (TypeError, ValueError):
        return "—"


class ControlView(ui.View):
    def __init__(self, bot: "GoldenShieldDiscordBot") -> None:
        super().__init__(timeout=None)
        self._bot = bot

    @ui.button(label="Refresh Status", style=discord.ButtonStyle.primary, custom_id="gs:refresh")
    async def refresh_btn(self, interaction: discord.Interaction, _button: ui.Button) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        embed = await self._bot.build_status_embed()
        await interaction.followup.send(embed=embed, ephemeral=True)

    @ui.button(label="Emergency Stop", style=discord.ButtonStyle.danger, custom_id="gs:panic")
    async def panic_btn(self, interaction: discord.Interaction, _button: ui.Button) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        result = await self._bot.api_act({"act": "panic"})
        ok = bool(result.get("ok"))
        msg = result.get("message") or result.get("error") or str(result)
        await interaction.followup.send(
            "● PANIC " + ("OK" if ok else "FAIL") + f"\n{msg[:500]}",
            ephemeral=True,
        )
        await self._bot.publish_status()

    @ui.button(label="Close All", style=discord.ButtonStyle.secondary, custom_id="gs:close_all")
    async def close_all_btn(self, interaction: discord.Interaction, _button: ui.Button) -> None:
        await interaction.response.defer(thinking=True, ephemeral=True)
        result = await self._bot.api_act({"act": "close_all"})
        ok = bool(result.get("ok"))
        msg = result.get("message") or result.get("error") or str(result)
        await interaction.followup.send(
            "Close All: " + ("OK" if ok else "FAIL") + f"\n{msg[:500]}",
            ephemeral=True,
        )
        await self._bot.publish_status()


class GoldenShieldDiscordBot(discord.Client):
    def __init__(self, *, channel_id: int) -> None:
        intents = discord.Intents.default()
        intents.message_content = False
        super().__init__(intents=intents)
        self.channel_id = channel_id
        self._session: aiohttp.ClientSession | None = None
        self._status_message: discord.Message | None = None
        self._live = False

    async def setup_hook(self) -> None:
        self.add_view(ControlView(self))
        self.loop.create_task(self._health_loop())

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20),
                headers={"X-GS-Token": _api_token(), "Content-Type": "application/json"},
            )
        return self._session

    async def fetch_health(self) -> dict:
        try:
            session = await self._get_session()
            async with session.get(HEALTH_URL) as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as exc:
            log.warning("health fetch: %s", exc)
        return {"ok": False}

    async def api_act(self, body: dict) -> dict:
        token = _api_token()
        if not token:
            return {"ok": False, "error": "MOBILE_API_TOKEN missing in .env"}
        try:
            session = await self._get_session()
            async with session.post(f"{API_BASE}/api/act", json=body) as resp:
                data = await resp.json(content_type=None)
                if isinstance(data, dict):
                    data.setdefault("ok", resp.status < 400)
                    return data
                return {"ok": resp.status < 400, "raw": data}
        except Exception as exc:
            log.exception("api_act: %s", exc)
            return {"ok": False, "error": str(exc)}

    async def build_status_embed(self) -> discord.Embed:
        health = await self.fetch_health()
        snap = _read_snapshot()
        api_ok = bool(health.get("ok"))
        spinal = health.get("spinal") if isinstance(health.get("spinal"), dict) else {}
        equity = snap.get("equity")
        free = snap.get("free_cash")
        open_pos = snap.get("open_positions")
        source = snap.get("source") or "—"
        snap_age = spinal.get("snapshot_age_sec")
        if snap_age is None and SNAPSHOT_PATH.is_file():
            snap_age = round(
                datetime.now(timezone.utc).timestamp() - SNAPSHOT_PATH.stat().st_mtime, 1
            )

        status_dot = "● LIVE" if api_ok and self._live else "○ DEGRADED"
        color = discord.Color.green() if api_ok else discord.Color.red()
        embed = discord.Embed(
            title=f"GoldenShield Control {status_dot}",
            description="Sovereign Discord control · Mobile API + snapshot mirror",
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Mobile API", value="OK (8790)" if api_ok else "DOWN", inline=True)
        embed.add_field(name="Equity", value=_fmt_money(equity), inline=True)
        embed.add_field(name="Free USDT", value=_fmt_money(free), inline=True)
        embed.add_field(name="Open positions", value=str(open_pos if open_pos is not None else "—"), inline=True)
        embed.add_field(name="Balance source", value=str(source)[:32], inline=True)
        embed.add_field(
            name="Snapshot age (s)",
            value=str(snap_age if snap_age is not None else "—"),
            inline=True,
        )
        if not api_ok:
            embed.set_footer(text="Check Ensure-GsMobileApi / GoldenShieldWatchdog on VPS")
        return embed

    async def publish_status(self) -> None:
        channel = self.get_channel(self.channel_id)
        if channel is None:
            try:
                channel = await self.fetch_channel(self.channel_id)
            except Exception as exc:
                log.error(
                    "channel %s not found — invite bot to server & check DISCORD_CHANNEL_ID: %s",
                    self.channel_id,
                    exc,
                )
                return
        if not isinstance(channel, discord.TextChannel):
            log.error("channel %s is not a text channel", self.channel_id)
            return
        embed = await self.build_status_embed()
        view = ControlView(self)
        if self._status_message is None:
            async for msg in channel.history(limit=15):
                if msg.author.id == self.user.id and msg.embeds:
                    title = (msg.embeds[0].title or "") if msg.embeds else ""
                    if "GoldenShield Control" in title:
                        self._status_message = msg
                        break
        try:
            if self._status_message:
                await self._status_message.edit(embed=embed, view=view)
            else:
                self._status_message = await channel.send(embed=embed, view=view)
        except Exception as exc:
            log.warning("publish_status edit/send: %s", exc)
            self._status_message = await channel.send(embed=embed, view=view)

    async def _health_loop(self) -> None:
        await self.wait_until_ready()
        while not self.is_closed():
            health = await self.fetch_health()
            self._live = bool(health.get("ok"))
            try:
                await self.publish_status()
            except Exception as exc:
                log.warning("status loop: %s", exc)
            await asyncio.sleep(float(os.getenv("GS_DISCORD_STATUS_SEC", "45") or 45))

    async def on_ready(self) -> None:
        log.info("Discord connected as %s — ● LIVE gateway", self.user)
        try:
            await self.publish_status()
        except Exception as exc:
            log.exception("publish_status on_ready: %s", exc)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        await super().close()


def main() -> int:
    _load_env()
    token = (os.getenv("DISCORD_BOT_TOKEN") or "").strip()
    channel_raw = (os.getenv("DISCORD_CHANNEL_ID") or os.getenv("DISCORD_CONTROL_CHANNEL_ID") or "").strip()
    if not token:
        log.error("DISCORD_BOT_TOKEN missing in .env")
        return 2
    if not channel_raw.isdigit():
        log.error("DISCORD_CHANNEL_ID missing or invalid")
        return 2
    channel_id = int(channel_raw)
    bot = GoldenShieldDiscordBot(channel_id=channel_id)
    try:
        bot.run(token, log_handler=None)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
