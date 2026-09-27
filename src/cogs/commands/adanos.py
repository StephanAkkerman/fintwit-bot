"""Opt-in Adanos sentiment slash command."""

import asyncio
import os
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from discord.commands.context import ApplicationContext
from discord.ext import commands

from api.adanos import format_stock_sentiment, get_stock_sentiment
from constants.config import config
from util.disc import conditional_role_decorator, log_command_usage


class Adanos(commands.Cog):
    """Show aggregated stock sentiment without changing the Finviz command."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.slash_command(
        description="Show optional Adanos sentiment for a US stock."
    )
    @discord.option(
        "ticker", type=str, description="US stock ticker, e.g. AAPL", required=True
    )
    @discord.option(
        "source",
        type=str,
        choices=["reddit", "x", "news", "polymarket"],
        required=False,
    )
    @log_command_usage
    @conditional_role_decorator(config["COMMANDS"]["ADANOS"]["ROLE"])
    async def adanos(
        self, ctx: ApplicationContext, ticker: str, source: str = "reddit"
    ) -> None:
        await ctx.response.defer(ephemeral=True)
        api_key = os.getenv("ADANOS_API_KEY", "").strip()
        if not api_key:
            await ctx.followup.send(
                "Adanos is not configured by the bot operator.", ephemeral=True
            )
            return

        end = datetime.now(timezone.utc).date()
        start = end - timedelta(days=6)
        try:
            data = await get_stock_sentiment(ticker, source, start, end, api_key)
        except (TypeError, ValueError) as exc:
            await ctx.followup.send(str(exc), ephemeral=True)
            return
        except aiohttp.ClientResponseError as exc:
            if exc.status == 403:
                message = (
                    "This Adanos source or date window is unavailable on this API plan."
                )
            elif exc.status == 429:
                message = "Adanos rate limit reached; try again later."
            elif exc.status == 401:
                message = "The bot operator's Adanos API key was rejected."
            else:
                message = f"Adanos returned HTTP {exc.status}."
            await ctx.followup.send(message, ephemeral=True)
            return
        except (aiohttp.ClientError, asyncio.TimeoutError):
            await ctx.followup.send(
                "Adanos is temporarily unavailable.", ephemeral=True
            )
            return

        await ctx.followup.send(
            format_stock_sentiment(data, ticker, source, start, end), ephemeral=True
        )


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Adanos(bot))
