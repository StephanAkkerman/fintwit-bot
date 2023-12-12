import datetime
import os

# > 3rd party dependencies
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib import ticker
import matplotlib.dates as mdates

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
from util.vars import get_json_data, data_sources
from util.formatting import human_format
from util.vars import config
from util.disc_util import get_channel


class Liquidations(commands.Cog):
    """
    This class contains the cog for posting the Liquidations chart.
    It can be enabled / disabled in the config under ["LOOPS"]["LIQUIDATIONS"].
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

        if config["LOOPS"]["LIQUIDATIONS"]["ENABLED"]:
            self.channel = get_channel(
                self.bot, config["LOOPS"]["LIQUIDATIONS"]["CHANNEL"]
            )
            self.post_liquidations.start()

    async def get_df(self):
        data = await get_json_data(
            "https://open-api.coinglass.com/public/v2/liquidation_history?time_type=all&symbol=all",
            headers={
                "accept": "application/json",
                "coinglassSecret": os.getenv("COINGLASS_API_KEY"),
            },
        )

        df = pd.DataFrame(data["data"])

        df.rename(
            {"buyVolUsd": "Shorts", "sellVolUsd": "Longs", "createTime": "time"},
            axis=1,
            inplace=True,
        )

        # Set correct column names
        df["date"] = pd.to_datetime(df["time"], unit="ms")

        # Set date as index
        df = df.set_index("date")
        return df

    @loop(hours=24)
    async def post_liquidations(self):
        """
        Copy chart like https://www.coinglass.com/LiquidationData

        Codes based on:
        https://github.com/OpenBB-finance/OpenBBTerminal/blob/main/openbb_terminal/cryptocurrency/due_diligence/coinglass_view.py
        """

        # Process dataframe
        df = await self.get_df()
        df_price = df[["price"]].copy()
        df_without_price = df.drop("price", axis=1)
        df_without_price["Shorts"] = df_without_price["Shorts"] * -1

        plt.style.use("dark_background")

        # This plot has 2 axes
        fig, ax1 = plt.subplots()
        ax2 = ax1.twinx()

        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
        plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=5))

        ax1.bar(
            df_without_price.index,
            df_without_price["Shorts"],
            label="Shorts",
            color="#d9024b",
        )

        ax1.bar(
            df_without_price.index,
            df_without_price["Longs"],
            label="Longs",
            color="#45bf87",
        )

        ax1.get_yaxis().set_major_formatter(
            ticker.FuncFormatter(lambda x, _: f"${human_format(x, absolute=True)}")
        )

        ax1.set_title("Total Liquidations")

        # Set price axis
        ax2.plot(df_price.index, df_price, color="#edba35", label="BTC Price")
        ax2.set_xlim([df_price.index[0], df_price.index[-1]])
        ax2.set_ylim(
            bottom=df_price.min().values * 0.95, top=df_price.max().values * 1.05
        )
        ax2.get_yaxis().set_major_formatter(lambda x, _: f"${human_format(x)}")

        # Add combined legend
        lines, labels = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(
            lines + lines2,
            labels + labels2,
            loc="upper center",
            fontsize="x-small",
            ncol=3,
        )

        # Add gridlines
        plt.grid(axis="y", color="grey", linestyle="-.", linewidth=0.5, alpha=0.5)

        # Remove spines
        ax1.spines["top"].set_visible(False)
        ax1.spines["bottom"].set_visible(False)
        ax1.spines["right"].set_visible(False)
        ax1.spines["left"].set_visible(False)
        ax1.tick_params(left=False, bottom=False, right=False)

        ax2.spines["top"].set_visible(False)
        ax2.spines["bottom"].set_visible(False)
        ax2.spines["right"].set_visible(False)
        ax2.spines["left"].set_visible(False)
        ax2.tick_params(left=False, bottom=False, right=False)

        # Fixes first and last bar not showing
        ax1.set_xlim(
            left=df_without_price.index[0] - datetime.timedelta(days=1),
            right=df_without_price.index[-1] + datetime.timedelta(days=1),
        )
        ax2.set_xlim(
            left=df_without_price.index[0] - datetime.timedelta(days=1),
            right=df_without_price.index[-1] + datetime.timedelta(days=1),
        )

        # Set correct size
        fig.set_size_inches(15, 6)

        # Convert to plot to a temporary image
        filename = "liquidations.png"
        plt.savefig(filename, bbox_inches="tight", dpi=300)
        plt.cla()
        plt.close()

        e = discord.Embed(
            title="Total Liquidations",
            description="",
            color=data_sources["coinglass"]["color"],
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            url="https://www.coinglass.com/LiquidationData",
        )
        file = discord.File(filename)
        e.set_image(url=f"attachment://{filename}")
        e.set_footer(
            text="\u200b",
            icon_url=data_sources["coinglass"]["icon"],
        )

        await self.channel.purge(limit=1)
        await self.channel.send(file=file, embed=e)

        # Delete yield.png
        os.remove(filename)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(Liquidations(bot))
