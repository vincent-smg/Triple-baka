"""
Miku Dayo — Security, Moderation & Verification Bot
"""
import asyncio
import os
import sys

import discord
from discord.ext import commands

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True
INTENTS.guilds = True
INTENTS.moderation = True


class MikuBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self) -> None:
        for cog in ("cogs.moderation", "cogs.info", "cogs.verification"):
            await self.load_extension(cog)
        await self.tree.sync()
        print("[Miku Dayo] Slash commands synced.")

    async def on_ready(self) -> None:
        print(f"[Miku Dayo] Logged in as {self.user} (ID: {self.user.id})")  # type: ignore[union-attr]
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="over the server 👁️"
            )
        )

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: discord.app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "❌ You don't have permission to use this command."
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            msg = "❌ I'm missing the permissions needed to do that."
        else:
            msg = f"❌ An error occurred: {error}"
        try:
            await interaction.response.send_message(msg, ephemeral=True)
        except discord.InteractionResponded:
            await interaction.followup.send(msg, ephemeral=True)


bot = MikuBot()

if __name__ == "__main__":
    token = os.environ.get("MIKU_TOKEN")
    if not token:
        print("[Miku Dayo] Error: MIKU_TOKEN is not set.", file=sys.stderr)
        sys.exit(1)
    bot.run(token, log_handler=None)
