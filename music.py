"""Neru Dayo — Music commands (YouTube, Spotify, SoundCloud via yt-dlp)."""
import asyncio

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.music_manager import (
    GuildQueue,
    Track,
    fetch_tracks,
    get_queue,
    make_audio_source,
    remove_queue,
)

COLOR_PRIMARY = 0xFFD700
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._session: aiohttp.ClientSession | None = None

    async def cog_load(self) -> None:
        self._session = aiohttp.ClientSession()

    async def cog_unload(self) -> None:
        if self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    # ── Internal: start playing the next track ──
    def _play_next(self, guild: discord.Guild, text_channel: discord.TextChannel) -> None:
        q = get_queue(guild.id)
        vc = guild.voice_client
        if not vc or not isinstance(vc, discord.VoiceClient):
            return

        next_track = q.next()
        if next_track is None:
            q.current = None
            asyncio.run_coroutine_threadsafe(
                text_channel.send("✅ Queue finished — Neru is leaving the VC."),
                self.bot.loop,
            )
            asyncio.run_coroutine_threadsafe(vc.disconnect(), self.bot.loop)
            remove_queue(guild.id)
            return

        q.current = next_track

        try:
            source = make_audio_source(next_track, q.volume)

            def after(error: Exception | None) -> None:
                if error:
                    print(f"[Neru Dayo] Player error: {error}")
                self._play_next(guild, text_channel)

            vc.play(source, after=after)
        except Exception as e:
            print(f"[Neru Dayo] Failed to play {next_track.title}: {e}")
            asyncio.run_coroutine_threadsafe(
                text_channel.send(f"⚠️ Skipping **{next_track.title}** — couldn't start playback."),
                self.bot.loop,
            )
            self._play_next(guild, text_channel)
            return

        embed = discord.Embed(
            title="▶️ Now Playing",
            description=f"[{next_track.title}]({next_track.webpage_url})",
            color=COLOR_PRIMARY,
        )
        embed.add_field(name="Duration", value=next_track.duration_str(), inline=True)
        embed.add_field(name="Requested by", value=next_track.requester, inline=True)
        if next_track.thumbnail:
            embed.set_thumbnail(url=next_track.thumbnail)
        asyncio.run_coroutine_threadsafe(
            text_channel.send(embed=embed),
            self.bot.loop,
        )

    # ──────────────────────────── PLAY ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="play", description="Play music from YouTube, Spotify, or SoundCloud")
    @app_commands.describe(query="Song name, URL (YouTube/Spotify/SoundCloud), or search query")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        if not interaction.guild:
            return

        # Must be in a voice channel
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message("❌ You need to be in a voice channel first.", ephemeral=True)
            return

        await interaction.response.defer()

        vc = interaction.guild.voice_client
        if not vc:
            vc = await member.voice.channel.connect()
        elif vc.channel != member.voice.channel:
            await vc.move_to(member.voice.channel)

        # Fetch track(s)
        try:
            tracks = await fetch_tracks(query, self.session, str(interaction.user))
        except Exception as e:
            await interaction.followup.send(f"❌ Could not find anything for `{query}`.\n`{e}`")
            return

        if not tracks:
            await interaction.followup.send(f"❌ No results found for `{query}`.")
            return

        q = get_queue(interaction.guild.id)
        for t in tracks:
            q.add(t)

        if not vc.is_playing() and not vc.is_paused():
            text_channel = interaction.channel  # type: ignore[assignment]
            self._play_next(interaction.guild, text_channel)  # type: ignore[arg-type]
            await interaction.followup.send(f"▶️ Starting playback of **{tracks[0].title}**.")
        else:
            names = "\n".join(f"• {t.title}" for t in tracks)
            await interaction.followup.send(f"➕ Added to queue:\n{names}")

    # ──────────────────────────── PAUSE ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="pause", description="Pause the current song")
    async def pause(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None  # type: ignore[union-attr]
        if not vc or not vc.is_playing():
            await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            return
        vc.pause()
        await interaction.response.send_message("⏸️ Paused.")

    # ──────────────────────────── RESUME ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="resume", description="Resume the paused song")
    async def resume(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None  # type: ignore[union-attr]
        if not vc or not vc.is_paused():
            await interaction.response.send_message("❌ Nothing is paused right now.", ephemeral=True)
            return
        vc.resume()
        await interaction.response.send_message("▶️ Resumed.")

    # ──────────────────────────── SKIP ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None  # type: ignore[union-attr]
        if not vc or (not vc.is_playing() and not vc.is_paused()):
            await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            return
        vc.stop()  # triggers after() → _play_next
        await interaction.response.send_message("⏭️ Skipped.")

    # ──────────────────────────── STOP ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None  # type: ignore[union-attr]
        if not vc:
            await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)
            return
        await interaction.response.defer()
        q = get_queue(interaction.guild.id)  # type: ignore[union-attr]
        q.clear()
        vc.stop()
        await vc.disconnect()
        remove_queue(interaction.guild.id)  # type: ignore[union-attr]
        await interaction.followup.send("⏹️ Stopped and cleared the queue.")

    # ──────────────────────────── QUEUE ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="queue", description="Show the current music queue")
    async def queue(self, interaction: discord.Interaction) -> None:
        q = get_queue(interaction.guild.id)  # type: ignore[union-attr]
        embed = discord.Embed(title="🎵 Music Queue", color=COLOR_PRIMARY)

        if q.current:
            embed.add_field(
                name="▶️ Now Playing",
                value=f"[{q.current.title}]({q.current.webpage_url}) — {q.current.duration_str()} · {q.current.requester}",
                inline=False,
            )

        if q.tracks:
            lines = [
                f"`{i}.` [{t.title}]({t.webpage_url}) — {t.duration_str()} · {t.requester}"
                for i, t in enumerate(q.tracks[:15], 1)
            ]
            embed.add_field(name="Up Next", value="\n".join(lines), inline=False)
            if len(q.tracks) > 15:
                embed.set_footer(text=f"… and {len(q.tracks) - 15} more tracks")
        else:
            embed.description = "The queue is empty." if not q.current else ""

        await interaction.response.send_message(embed=embed)

    # ──────────────────────────── NOWPLAYING ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="nowplaying", description="Show the currently playing song")
    async def nowplaying(self, interaction: discord.Interaction) -> None:
        q = get_queue(interaction.guild.id)  # type: ignore[union-attr]
        if not q.current:
            await interaction.response.send_message("❌ Nothing is playing right now.", ephemeral=True)
            return
        t = q.current
        embed = discord.Embed(
            title="▶️ Now Playing",
            description=f"[{t.title}]({t.webpage_url})",
            color=COLOR_PRIMARY,
        )
        embed.add_field(name="Duration", value=t.duration_str(), inline=True)
        embed.add_field(name="Requested by", value=t.requester, inline=True)
        embed.add_field(name="Volume", value=f"{int(q.volume * 100)}%", inline=True)
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        await interaction.response.send_message(embed=embed)

    # ──────────────────────────── VOLUME ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="volume", description="Set the playback volume (0–200)")
    @app_commands.describe(level="Volume level (0 = mute, 100 = normal, 200 = max)")
    async def volume(
        self,
        interaction: discord.Interaction,
        level: app_commands.Range[int, 0, 200],
    ) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None  # type: ignore[union-attr]
        q = get_queue(interaction.guild.id)  # type: ignore[union-attr]
        q.volume = level / 100

        if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
            vc.source.volume = q.volume

        await interaction.response.send_message(f"🔊 Volume set to **{level}%**.")

    # ──────────────────────────── JOIN ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction) -> None:
        member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None  # type: ignore[union-attr]
        if not member or not member.voice or not member.voice.channel:
            await interaction.response.send_message("❌ You need to be in a voice channel first.", ephemeral=True)
            return

        await interaction.response.defer()

        vc = interaction.guild.voice_client  # type: ignore[union-attr]
        try:
            if vc:
                await vc.move_to(member.voice.channel)
            else:
                await member.voice.channel.connect()
        except Exception as e:
            await interaction.followup.send(f"❌ Couldn't join the voice channel: `{e}`")
            return

        await interaction.followup.send(f"🔊 Joined **{member.voice.channel.name}**.")

    # ──────────────────────────── LEAVE ────────────────────────────
    @app_commands.guild_only()
    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction) -> None:
        vc = interaction.guild.voice_client if interaction.guild else None  # type: ignore[union-attr]
        if not vc:
            await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)
            return
        await interaction.response.defer()
        q = get_queue(interaction.guild.id)  # type: ignore[union-attr]
        q.clear()
        await vc.disconnect()
        remove_queue(interaction.guild.id)  # type: ignore[union-attr]
        await interaction.followup.send("👋 Disconnected.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))
