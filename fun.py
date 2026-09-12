"""Teto Dayo — Fun commands."""
import random
import re
import asyncio
from typing import Literal

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

COLOR_PRIMARY = 0xFF6B9D
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245

EIGHT_BALL_ANSWERS = [
    # Positive
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    # Neutral
    "Reply hazy, try again.", "Ask again later.",
    "Better not tell you now.", "Cannot predict now.", "Concentrate and ask again.",
    # Negative
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]


class Fun(commands.Cog):
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

    # ──────────────────────────── 8BALL ────────────────────────────
    @app_commands.command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="Your question for the 8-ball")
    async def eightball(self, interaction: discord.Interaction, question: str) -> None:
        answer = random.choice(EIGHT_BALL_ANSWERS)
        embed = discord.Embed(title="🎱 Magic 8-Ball", color=COLOR_PRIMARY)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=f"*{answer}*", inline=False)
        await interaction.response.send_message(embed=embed)

    # ──────────────────────────── COINFLIP ────────────────────────────
    @app_commands.command(name="coinflip", description="Flip a coin")
    async def coinflip(self, interaction: discord.Interaction) -> None:
        result = random.choice(["Heads 🪙", "Tails 🔵"])
        embed = discord.Embed(title="🪙 Coin Flip", description=f"**{result}**", color=COLOR_PRIMARY)
        await interaction.response.send_message(embed=embed)

    # ──────────────────────────── ROLL ────────────────────────────
    @app_commands.command(name="roll", description="Roll dice — e.g. 2d6, d20, 3d8")
    @app_commands.describe(dice="Dice notation like 2d6 (default: 1d6)")
    async def roll(self, interaction: discord.Interaction, dice: str = "1d6") -> None:
        match = re.fullmatch(r"(\d+)?d(\d+)", dice.strip().lower())
        if not match:
            await interaction.response.send_message("❌ Invalid dice notation. Use something like `2d6` or `d20`.", ephemeral=True)
            return
        count = int(match.group(1) or 1)
        sides = int(match.group(2))
        if count < 1 or count > 100 or sides < 2 or sides > 1000:
            await interaction.response.send_message("❌ Count must be 1–100 and sides must be 2–1000.", ephemeral=True)
            return
        rolls = [random.randint(1, sides) for _ in range(count)]
        embed = discord.Embed(title=f"🎲 Rolling {dice}", color=COLOR_PRIMARY)
        if count <= 20:
            embed.add_field(name="Rolls", value=", ".join(str(r) for r in rolls), inline=False)
        embed.add_field(name="Total", value=str(sum(rolls)), inline=True)
        embed.add_field(name="Min/Max", value=f"{min(rolls)} / {max(rolls)}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ──────────────────────────── JOKE ────────────────────────────
    @app_commands.command(name="joke", description="Get a random joke")
    async def joke(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            async with self.session.get(
                "https://v2.jokeapi.dev/joke/Any?blacklistFlags=nsfw,racist,sexist",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()
        except Exception:
            await interaction.followup.send("❌ Couldn't fetch a joke right now. Try again later.")
            return

        embed = discord.Embed(title="😂 Random Joke", color=COLOR_PRIMARY)
        if data.get("type") == "twopart":
            embed.add_field(name="Setup", value=data["setup"], inline=False)
            embed.add_field(name="Punchline", value=f"||{data['delivery']}||", inline=False)
        else:
            embed.description = data.get("joke", "No joke found.")
        await interaction.followup.send(embed=embed)

    # ──────────────────────────── RPS ────────────────────────────
    @app_commands.command(name="rps", description="Play rock, paper, scissors against Teto")
    @app_commands.describe(choice="Your choice")
    async def rps(
        self,
        interaction: discord.Interaction,
        choice: Literal["rock", "paper", "scissors"],
    ) -> None:
        bot_choice = random.choice(["rock", "paper", "scissors"])
        icons = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        outcomes = {
            ("rock", "scissors"): "win",
            ("paper", "rock"): "win",
            ("scissors", "paper"): "win",
        }
        if choice == bot_choice:
            result, color = "It's a tie!", COLOR_PRIMARY
        elif outcomes.get((choice, bot_choice)):
            result, color = "You win! 🎉", COLOR_SUCCESS
        else:
            result, color = "Teto wins! 😈", COLOR_ERROR

        embed = discord.Embed(title="✂️ Rock Paper Scissors", description=result, color=color)
        embed.add_field(name="Your choice", value=f"{icons[choice]} {choice.title()}", inline=True)
        embed.add_field(name="Teto's choice", value=f"{icons[bot_choice]} {bot_choice.title()}", inline=True)
        await interaction.response.send_message(embed=embed)

    # ──────────────────────────── SAY ────────────────────────────
    @app_commands.command(name="say", description="Make Teto say something")
    @app_commands.describe(message="What Teto should say", ephemeral="Only visible to you? (default: No)")
    async def say(self, interaction: discord.Interaction, message: str, ephemeral: bool = False) -> None:
        await interaction.response.send_message("✅ Sent!", ephemeral=True)
        await interaction.channel.send(message)  # type: ignore[union-attr]

    # ──────────────────────────── MEME ────────────────────────────
    @app_commands.command(name="meme", description="Get a random meme")
    async def meme(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        try:
            async with self.session.get(
                "https://meme-api.com/gimme",
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                data = await resp.json()
        except Exception:
            await interaction.followup.send("❌ Couldn't fetch a meme right now. Try again later.")
            return

        if data.get("nsfw"):
            await interaction.followup.send("❌ Got an NSFW meme, skipping. Try again!")
            return

        embed = discord.Embed(title=data.get("title", "Random Meme"), color=COLOR_PRIMARY)
        embed.set_image(url=data.get("url"))
        embed.set_footer(text=f"r/{data.get('subreddit')} · 👍 {data.get('ups', 0)}")
        await interaction.followup.send(embed=embed)

    # ──────────────────────────── IMPERSONATE ────────────────────────────
    @app_commands.command(name="impersonate", description="Send a message as another member (via webhook)")
    @app_commands.describe(member="The member to impersonate", message="The message to send")
    @app_commands.checks.has_permissions(manage_webhooks=True)
    @app_commands.checks.bot_has_permissions(manage_webhooks=True)
    async def impersonate(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        message: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        assert isinstance(channel, discord.TextChannel)

        webhooks = await channel.webhooks()
        hook = next((w for w in webhooks if w.user == self.bot.user), None)
        if hook is None:
            hook = await channel.create_webhook(name="Teto Impersonator")

        await hook.send(
            content=message,
            username=member.display_name,
            avatar_url=member.display_avatar.url,
        )
        await interaction.followup.send("✅ Message sent!", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
