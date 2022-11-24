# Standard libraries
import datetime
import pandas as pd
import time
import inspect

# > Discord dependencies
import discord
from discord.ext import commands
from discord.ext.tasks import loop

# Local dependencies
import util.vars
from util.vars import config, get_json_data
from util.disc_util import get_channel, get_tagged_users, get_guild
from util.afterhours import afterHours
from util.db import clean_old_db, merge_and_update
from util.formatting import human_format

class UW(commands.Cog):
    """
    This class contains the cog for posting the latest Unusual Whales alerts.
    It can be enabled / disabled in the config under ["LOOPS"]["UNUSUAL_WHALES"].

    Methods
    -------
    set_emojis() -> None
        This function gets and sets the emojis for the UW alerts.
    UW_data() -> dict:
        Get the alerts data of the last 5 minutes.
    alerts() -> None
        This function posts the Unusual Whales alerts on Discord.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emoji_dict = {}
        self.guild = get_guild(bot)

        self.channel = get_channel(
            self.bot, config["LOOPS"]["UNUSUAL_WHALES"]["CHANNEL"]
        )
        
        self.overview_channel = get_channel(
            self.bot, config["LOOPS"]["UNUSUAL_WHALES"]["OVERVIEW_CHANNEL"], config["CATEGORIES"]["OPTIONS"]
        )
        
        self.volume_channel = get_channel(
            self.bot, config["LOOPS"]["UNUSUAL_WHALES"]["VOLUME_CHANNEL"]
        )
        
        self.spacs_channel = get_channel(
            self.bot, config["LOOPS"]["UNUSUAL_WHALES"]["SPACS_CHANNEL"]
        )
        
        self.shorts_channel = get_channel(
            self.bot, config["LOOPS"]["UNUSUAL_WHALES"]["SHORTS_CHANNEL"]
        )

        self.alerts.start()
        self.volume.start()
        self.spacs.start()
        self.shorts.start()

    @loop(minutes=5)
    async def alerts(self) -> None:
        """
        This function posts the Unusual Whales alerts on Discord.

        Returns
        -------
        None
        """

        # Check if the market is open
        #if afterHours():
        #   return

        # Get the emojis if not already done
        if self.emoji_dict == {}:
            # Get the emojis and store them in emoji_dict
            self.emoji_dict = await get_json_data(
                "https://phx.unusualwhales.com/api/tags/all", {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36"}
            )   
            
        # start_date and expiry_start_data depends on how often the function is called
        last_5_min = int((time.time() - (5 * 60)) * 1000)
        
        # Check the last 5 minutes on the API
        url = f"https://phx.unusualwhales.com/api/option_quotes?offset=0&sort=timestamp&search=&sector=&tag=&end_date=9999999999999&start_date={last_5_min}&expiry_start_date={last_5_min}&expiry_end_date=9999999999999&min_ask=0&max_ask=9999999999999&volume_direction=desc&expiry_direction=desc&alerted_direction=desc&oi_direction=desc&normal=true"

        # Use the token in the header
        headers = {
            "authorization": config["LOOPS"]["UNUSUAL_WHALES"]["TOKEN"],
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
        }

        data = await get_json_data(url, headers)
        df = pd.DataFrame(data)

        if df.empty:
            return

        # Only keep the important information
        df = df[
            [
                "timestamp",
                "id",
                "ticker_symbol",
                "option_type",
                "strike_price",  # Also named underlying
                "expires_at",
                "stock_price",
                "bid",
                "ask",
                "min_ask",
                "max_ask",
                "volume",
                "implied_volatility",
                "sector",
                "tags",
                "tier",
                "is_recommended",
                "open_interest",
                "delta",
                "theta",
            ]
        ]

        # Calculate the percentual difference between current price and strike price
        df["strike_price"] = df["strike_price"].astype(float)
        df["stock_price"] = df["stock_price"].astype(float)
        df["difference"] = (
            (df["strike_price"] - df["stock_price"]) / df["stock_price"] * 100
        )
        df["difference"] = df["difference"].round(2)
        df["difference"] = df["difference"].astype(str) + "%"

        # Convert IV to percent
        df["implied_volatility"] = df["implied_volatility"].astype(float)
        df["IV"] = df["implied_volatility"] * 100
        df["IV"] = df["IV"].round(2)
        df["IV"] = df["IV"].astype(str) + "%"

        # Get the timestamp convert to datetime and local time
        df["alert_time"] = pd.to_datetime(df["timestamp"], utc=True)
        df["alert_time"] = df["alert_time"].dt.tz_convert(
            datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        )
        df["alert_time"] = df["alert_time"].dt.strftime("%I:%M %p")

        # Round theta and delta
        df["theta"] = df["theta"].astype(float)
        df["theta"] = df["theta"].round(3)
        df["delta"] = df["delta"].astype(float)
        df["delta"] = df["delta"].round(3)

        # For each ticker in the df send a message
        for _, row in df.iterrows():

            # Only use the first letter of the option type
            option_type = row["option_type"][0].upper()

            emojis = ""
            for tag in row["tags"]:
                try:
                    emojis += self.emoji_dict[tag]["emoji"]
                # In case emoji_dict is empty
                except KeyError:
                    print(f"Could not find emoji for {tag}")

            # Create the embed
            e = discord.Embed(
                title=f"${row['ticker_symbol']} {row['expires_at']} {option_type} ${row['strike_price']}",
                url=f"https://unusualwhales.com/alerts/{row['id']}",
                # Use inspect.cleandoc() to remove the indentation
                description=inspect.cleandoc(
                    f"""
                    {emojis}
                    Bid-Ask: ${row['bid']} - ${row['ask']}
                    Interest: {row['open_interest']}
                    Volume: {row['volume']}
                    IV: {row['IV']}
                    % Diff: {row["difference"]}
                    Underlying: ${row['stock_price']}
                    Θ | Δ: {row['theta']} | {row['delta']}
                    Sector: {row['sector']}
                    Tier: {row['tier']}
                    Recommended: {row['is_recommended']}
                    {emojis}
                    """
                ),
                color=0xE40414 if option_type == "P" else 0x3CC474,
                timestamp=datetime.datetime.now(datetime.timezone.utc),
            )

            e.set_footer(
                # Use the time the alert was created in the footer
                text=f"Alerted at {row['alert_time']}",
                icon_url="https://docs.unusualwhales.com/images/banner.png",
            )

            await self.channel.send(
                content=get_tagged_users([row["ticker_symbol"]]), embed=e
            )
            
            # Add the data to the database
            update_options_db(row['ticker_symbol'], row['expires_at'], option_type, row['strike_price'], row['volume'], emojis)
        
            await self.options_overview()
            
    async def options_overview(self):
        
        if util.vars.options_db.empty:
            return
        
        # Gather the data for the summary
        num_calls = len(util.vars.options_db[util.vars.options_db['option_type'] == 'C'])
        num_puts = len(util.vars.options_db[util.vars.options_db['option_type'] == 'P'])
        
        num_bears = len(util.vars.options_db[util.vars.options_db["bull/bear"] == 'bear'])
        num_bulls = len(util.vars.options_db[util.vars.options_db["bull/bear"] == 'bull'])
        
        # Top row of the embed shows an summary of P/C ratio, Bullish/Bearish
        e = discord.Embed(
            title=f"Options Overview",
            description="",
            color=self.guild.self_role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        
        most_mentioned = util.vars.options_db['ticker'].value_counts()
        
        e.add_field(name="Calls - Puts", value=f"{num_calls} - {num_puts}", inline=True)
        e.add_field(name="Bullish - Bearish", value=f"{num_bulls} - {num_bears}", inline=True)
        e.add_field(name="Most Active Ticker", value=f"{most_mentioned.index[0]} ({most_mentioned.iloc[0]})", inline=True)
        
        # Sort by volume
        util.vars.options_db["volume"] = util.vars.options_db["volume"].astype(int)
        util.vars.options_db = util.vars.options_db.sort_values(by=['volume'], ascending=False)
        
        # First show the top 10 bullish options, ranked by count and volume
        bullish = util.vars.options_db[util.vars.options_db["bull/bear"] == 'bull']
                                    
        # Then show the top 10 bearish options
        bearish = util.vars.options_db[util.vars.options_db["bull/bear"] == 'bear']
        
        if not bullish.empty:
            bull_counts, bull_options, bull_volumes = self.get_top20(bullish)
            e.add_field(name="Bullish", value="\n".join(bull_counts), inline=True)
            e.add_field(name="Options", value="\n".join(bull_options), inline=True)
            e.add_field(name="Volume", value="\n".join(bull_volumes), inline=True)
        
        if not bearish.empty:
            bear_counts, bear_options, bear_volumes = self.get_top20(bearish)
            e.add_field(name="Bearish", value="\n".join(bear_counts), inline=True)
            e.add_field(name="Options", value="\n".join(bear_options), inline=True)
            e.add_field(name="Volume", value="\n".join(bear_volumes), inline=True)
        
        await self.overview_channel.purge(limit=1)
        await self.overview_channel.send(embed=e)
        
    def get_top20(self, df):        
        counts = []
        options = []
        volumes = []
        
        for _, row in df.head(20).iterrows():
            counts.append(f"${row['ticker']}")
            options.append(f"{row['expiration']} {row['option_type']} ${row['strike_price']}")
            volumes.append(str(row['volume']))
            
        return counts, options, volumes
    
    async def get_UW_data(self, url):
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
        }
        
        data = await get_json_data(url, headers)
        df = pd.DataFrame(data)
        
        if df.empty:
            return
        
        # Get the timestamp convert to datetime and local time
        df["alert_time"] = pd.to_datetime(df["timestamp"], utc=True)

        # Filter df on last 15 minutes
        df = df[df["alert_time"] > datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)]

        if df.empty:
            return

        df["alert_time"] = df["alert_time"].dt.tz_convert(
            datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
        )
        
        # Format to string
        df["alert_time"] = df["alert_time"].dt.strftime("%I:%M %p")            
        
        return df

    def make_UW_embed(self, row):
        e = discord.Embed(
            title=f"${row['ticker_symbol']}",
            url=f"https://unusualwhales.com/stock/{row['ticker_symbol']}",
            description="",
            color=self.guild.self_role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )

        e.add_field(name="Volume", value=f"${human_format(float(row['volume']))}", inline=True)
        e.add_field(name="Average 30d Volume", value=f"${human_format(float(row['avg_volume_last_30_days']))}", inline=True)
        e.add_field(name="Volume Deviation", value=f"{round(float(row['volume_dev_from_norm']))}", inline=True)
        e.add_field(name="Price", value=f"${row['bid_price']}", inline=True)

        e.set_footer(
            # Use the time the alert was created in the footer
            text=f"Alerted at {row['alert_time']}",
            icon_url="https://docs.unusualwhales.com/images/banner.png",
        )
        
        return e

    @loop(minutes=15)
    async def volume(self):
        url = "https://phx.unusualwhales.com/api/stock_feed"
        df = await self.get_UW_data(url)
        
        if df:
            # Iterate over each row and post the alert
            for _, row in df.iterrows():
                e = self.make_UW_embed(row)        
                await self.volume_channel.send(embed=e)
                
    @loop(minutes=15)
    async def spacs(self):
        url = "https://phx.unusualwhales.com/api/warrant_alerts"        
        df = await self.get_UW_data(url)
        
        if df:
            # Iterate over each row and post the alert
            for _, row in df.iterrows():
                e = self.make_UW_embed(row)
                await self.spacs_channel.send(embed=e)
            
    @loop(hours=24)
    async def shorts(self):
        url = "https://phx.unusualwhales.com/api/short_interest_low"
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.54 Safari/537.36",
        }
        
        data = await get_json_data(url, headers)
        df = pd.DataFrame(data["data"])
        
        if df.empty:
            return
        
        # Cast to float
        df["short_interest"] = df["short_interest"].astype(float)
        
        # Sort on short_interest
        df = df.sort_values(by="short_interest", ascending=False)
        df["float_shares"] = df["float_shares"].astype(float)
        df["float_shares"] = df["float_shares"].apply(lambda x: human_format(x))
        
        df["outstanding"] = df["outstanding"].astype(float)
        df["outstanding"] = df["outstanding"].apply(lambda x: human_format(x))
        
        df["short_interest"] = df["short_interest"].astype(str)
        
        # Combine both in 1 string
        df["float - outstanding"] = df["float_shares"] + " - " + df["outstanding"]
        
        top20 = df.head(20)
        
        symbols = "\n".join(top20["symbol"].tolist())
        float_oustanding = "\n".join(top20["float - outstanding"].tolist())
        short_interest = "\n".join(top20["short_interest"].tolist())
        
        # Only show the top 20 as embed
        e = discord.Embed(
            title=f"Top Short Interest Reported",
            url=f"https://unusualwhales.com/shorts",
            description="",
            color=self.guild.self_role.color,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        
        e.set_footer(
            # Use the time the alert was created in the footer
            text="\u200b",
            icon_url="https://docs.unusualwhales.com/images/banner.png",
        )
        
        e.add_field(name="Symbol", value=symbols, inline=True)
        e.add_field(name="Float - Outstanding", value=float_oustanding, inline=True)
        e.add_field(name="Short Interest", value=short_interest, inline=True)
        
        await self.shorts_channel.purge(limit=1)
        await self.shorts_channel.send(embed=e)
        
            
def update_options_db(ticker, expiration, option_type, strike, volume, emojis):
    
    if '🐻' in emojis:
        emoji = 'bear'
    elif '🐂' in emojis:
        emoji = 'bull'
    else:
        emoji = 'none'
    
    option_dict = {
        "ticker": ticker,
        "expiration": expiration,
        "option_type": option_type,
        "strike_price": strike,
        "volume": volume,
        "bull/bear": emoji
    }
    
    # Convert it to a dataframe
    option_db = pd.DataFrame([option_dict])

    # Add timestamp
    option_db["timestamp"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    type_dict = {
       "ticker": str,
       "expiration": str,
       "option_type": str,
       "strike_price": float,
       "volume": int,
       "bull/bear": str,
       "timestamp" : str,
    }

    # Clean the old db
    clean_old_db(util.vars.options_db, type_dict, 1)
    util.vars.options_db = merge_and_update(util.vars.options_db, option_db, "options")


def setup(bot: commands.Bot) -> None:
    bot.add_cog(UW(bot))
