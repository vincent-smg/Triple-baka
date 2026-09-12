"""
Neru Dayo — Voice, Music & TTS Bot
"""
import os
import sys

import discord
from discord.ext import commands

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.voice_states = True


class NeruBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.music")
        await self.load_extension("cogs.voice")
        await self.tree.sync()
        print("[Neru Dayo] Slash commands synced.")

    async def on_ready(self) -> None:
        print(f"[Neru Dayo] Logged in as {self.user} (ID: {self.user.id})")  # type: ignore[union-attr]
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name="music 🎵"
            )
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        msg = f"❌ An error occurred: {error}"
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(msg, ephemeral=True)


bot = NeruBot()

if __name__ == "__main__":
    token = os.environ.get("NERU_TOKEN")
    if not token:
        print("[Neru Dayo] Error: NERU_TOKEN is not set.", file=sys.stderr)
        sys.exit(1)
    bot.run(token, log_handler=None)
