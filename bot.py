"""
Teto Dayo — Fun Commands Bot
"""
import os
import sys

import discord
from discord.ext import commands

INTENTS = discord.Intents.default()
INTENTS.members = True
INTENTS.message_content = True
INTENTS.guilds = True


class TetoBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=INTENTS, help_command=None)

    async def setup_hook(self) -> None:
        await self.load_extension("cogs.fun")
        await self.tree.sync()
        print("[Teto Dayo] Slash commands synced.")

    async def on_ready(self) -> None:
        print(f"[Teto Dayo] Logged in as {self.user} (ID: {self.user.id})")  # type: ignore[union-attr]
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing, name="with chaos 🎉"
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


bot = TetoBot()

if __name__ == "__main__":
    token = os.environ.get("TETO_TOKEN")
    if not token:
        print("[Teto Dayo] Error: TETO_TOKEN is not set.", file=sys.stderr)
        sys.exit(1)
    bot.run(token, log_handler=None)
