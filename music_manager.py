"""Per-guild music queue and player management for Neru Dayo."""
from __future__ import annotations

import asyncio
import os
import re
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import discord
import yt_dlp

YDL_OPTIONS: dict = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "noplaylist": False,
    "extract_flat": "in_playlist",
}

FFMPEG_OPTIONS: dict = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}


@dataclass
class Track:
    title: str
    url: str          # direct audio stream URL
    webpage_url: str  # original user-supplied URL
    requester: str
    duration: int     # seconds
    thumbnail: str = ""

    def duration_str(self) -> str:
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class GuildQueue:
    def __init__(self) -> None:
        self.tracks: list[Track] = []
        self.current: Optional[Track] = None
        self.volume: float = 0.5
        self.loop: bool = False
        self._lock = asyncio.Lock()

    def add(self, track: Track) -> None:
        self.tracks.append(track)

    def next(self) -> Optional[Track]:
        if self.loop and self.current:
            return self.current
        return self.tracks.pop(0) if self.tracks else None

    def clear(self) -> None:
        self.tracks.clear()
        self.current = None


# Singleton registry: guild_id → GuildQueue
_queues: dict[int, GuildQueue] = {}


def get_queue(guild_id: int) -> GuildQueue:
    if guild_id not in _queues:
        _queues[guild_id] = GuildQueue()
    return _queues[guild_id]


def remove_queue(guild_id: int) -> None:
    _queues.pop(guild_id, None)


# ──────────────────────────── Spotify resolver ────────────────────────────

_spotify_token: str = ""
_spotify_token_expiry: float = 0.0


async def _get_spotify_token(session: aiohttp.ClientSession) -> str:
    import time
    import base64

    global _spotify_token, _spotify_token_expiry
    if _spotify_token and time.time() < _spotify_token_expiry:
        return _spotify_token

    client_id = os.environ.get("SPOTIFY_CLIENT_ID", "")
    client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return ""

    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with session.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {creds}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data="grant_type=client_credentials",
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        data = await resp.json()
        _spotify_token = data.get("access_token", "")
        _spotify_token_expiry = time.time() + data.get("expires_in", 3600) - 60
    return _spotify_token


async def resolve_spotify(url: str, session: aiohttp.ClientSession) -> str:
    """Convert a Spotify track/album/playlist URL to a YouTube search query."""
    token = await _get_spotify_token(session)
    if not token:
        return f"ytsearch:{url}"

    track_match = re.search(r"spotify\.com/track/([A-Za-z0-9]+)", url)
    if track_match:
        track_id = track_match.group(1)
        async with session.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            data = await resp.json()
        name = data.get("name", "")
        artists = ", ".join(a["name"] for a in data.get("artists", []))
        return f"ytsearch:{name} {artists}"

    # Playlist / album: return first track only (full support can be added later)
    return f"ytsearch:{url}"


# ──────────────────────────── YT-DLP extraction ────────────────────────────

async def fetch_tracks(query: str, session: aiohttp.ClientSession, requester: str) -> list[Track]:
    """Resolve a search query or URL into a list of Track objects (async)."""
    loop = asyncio.get_event_loop()

    # Spotify URL → YouTube search
    if "spotify.com" in query:
        query = await resolve_spotify(query, session)

    def _extract() -> list[dict]:
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            info = ydl.extract_info(query, download=False)
            if info is None:
                return []
            entries = info.get("entries", [info])
            results = []
            for entry in entries[:1]:  # single track for now; playlist support below
                if entry is None:
                    continue
                # Re-extract if entry was flat
                if not entry.get("url") or entry.get("_type") == "url":
                    try:
                        entry = ydl.extract_info(entry.get("url") or entry.get("webpage_url", ""), download=False)
                    except Exception:
                        continue
                results.append(entry)
            return results

    entries = await loop.run_in_executor(None, _extract)
    tracks = []
    for e in entries:
        if e is None:
            continue
        # Pick the best audio URL
        audio_url = e.get("url", "")
        formats = e.get("formats", [])
        if formats:
            audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
            if audio_formats:
                audio_url = audio_formats[-1].get("url", audio_url)

        tracks.append(Track(
            title=e.get("title", "Unknown"),
            url=audio_url,
            webpage_url=e.get("webpage_url", query),
            requester=requester,
            duration=int(e.get("duration") or 0),
            thumbnail=e.get("thumbnail", ""),
        ))
    return tracks


def make_audio_source(track: Track, volume: float) -> discord.PCMVolumeTransformer:
    source = discord.FFmpegPCMAudio(track.url, **FFMPEG_OPTIONS)
    return discord.PCMVolumeTransformer(source, volume=volume)
