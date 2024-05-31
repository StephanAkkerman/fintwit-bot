##> Imports
import datetime

import ccxt.pro

# > Discord dependencies
import discord
import pandas as pd

import util.trades_msg

# Local dependencies
import util.vars
from util.db import get_db, update_db
from util.exchange_data import get_buying_price, get_data, get_usd_price
from util.formatting import format_change
from util.vars import stables


async def on_msg(
    msg: list,
    exchange: ccxt.pro.Exchange,
    trades_channel: discord.TextChannel,
    row: pd.Series,
    user: discord.User,
) -> None:
    """
    This function is used to handle the incoming messages from the binance websocket.

    Parameters
    ----------
    msg : str
        The message that is received from the binance websocket.

    Returns
    -------
    None
    """

    msg = msg[0]
    sym = msg["symbol"]  # BNB/USDT
    orderType = msg["type"]  # market, limit, stop, stop limit
    side = msg["side"]  # buy, sell
    price = float(round(msg["price"], 4))
    amount = float(round(msg["amount"], 4))
    cost = float(round(msg["cost"], 4))  # If /USDT, then this is the USD value

    # Get the value in USD
    usd = price
    base = sym.split("/")[0]
    quote = sym.split("/")[1]
    if quote not in stables:
        usd, change = await get_usd_price(exchange, base)

    # Get profit / loss if it is a sell
    buying_price = None
    if side == "sell":
        buying_price = await get_buying_price(exchange, sym, True)

    # Send it in the discord channel
    await util.trades_msg.trades_msg(
        exchange.id,
        trades_channel,
        user,
        sym,
        side,
        orderType,
        price,
        amount,
        round(usd * amount, 2),
        buying_price,
    )

    # Assets db: asset, owned (quantity), exchange, id, user
    assets_db = get_db("assets")

    # Drop all rows for this user and exchange
    updated_assets_db = assets_db.drop(
        assets_db[
            (assets_db["id"] == row["id"]) & (assets_db["exchange"] == exchange.id)
        ].index
    )

    assets_db = pd.concat([updated_assets_db, await get_data(row)]).reset_index(
        drop=True
    )

    update_db(assets_db, "assets")
    util.vars.assets_db = assets_db
    # Maybe post the updated assets of this user as well


async def trades_msg(
    exchange: str,
    channel: discord.TextChannel,
    user: discord.User,
    symbol: str,
    side: str,
    orderType: str,
    price: float,
    quantity: float,
    usd: float,
    buying_price: float = None,
) -> None:
    """
    Formats the Discord embed that will be send to the dedicated trades channel.

    Parameters
    ----------
    exchange : str
        The name of the exchange, currently only supports "binance", "kucoin" and "stocks".
    channel : discord.TextChannel
        The channel that the message will be sent to.
    user : discord.User
        The user that the message will be sent from.
    symbol : str
        The symbol that has been traded.
    side : str
        The side of the trade, either "BUY" or "SELL".
    orderType : str
        The type of order, for instance "LIMIT" or "MARKET".
    price : float
        The price of the trade.
    quantity : float
        The amount traded.
    usd : float
        The worth of the trade in US dollar.

    Returns
    -------
    None
    """

    # Same as in formatting.py
    if exchange == "binance":
        color = 0xF0B90B
        icon_url = (
            "https://upload.wikimedia.org/wikipedia/commons/5/57/Binance_Logo.png"
        )
        url = f"https://www.binance.com/en/trade/{symbol}"
    elif exchange == "kucoin":
        color = 0x24AE8F
        icon_url = "https://yourcryptolibrary.com/wp-content/uploads/2021/12/Kucoin-exchange-logo-1.png"
        url = f"https://www.kucoin.com/trade/{symbol}"
    else:
        color = 0x720E9E
        icon_url = (
            "https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png"
        )
        url = f"https://finance.yahoo.com/quote/{symbol}"

    e = discord.Embed(
        title=f"{orderType.capitalize()} {side.lower()} {quantity} {symbol}",
        description="",
        color=color,
        url=url,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    # Set the embed fields
    e.set_author(name=user.name, icon_url=user.display_avatar.url)

    # If the quote is USD, then the price is the USD value
    e.add_field(
        name="Price",
        value=f"${price}" if symbol.endswith(tuple(stables)) else price,
        inline=True,
    )

    if buying_price and buying_price != 0:
        price_change = price - buying_price

        if price_change != 0:
            percent_change = round((price_change / buying_price) * 100, 2)
        else:
            percent_change = 0

        percent_change = format_change(percent_change)
        profit_loss = f"${round(price_change * quantity, 2)} ({percent_change})"

        e.add_field(
            name="Profit / Loss",
            value=profit_loss,
            inline=True,
        )
    else:
        e.add_field(name="Amount", value=quantity, inline=True)

    # If we know the USD value, then add it
    if usd != 0:
        e.add_field(
            name="$ Worth",
            value=f"${usd}",
            inline=True,
        )

    e.set_footer(text="\u200b", icon_url=icon_url)

    await channel.send(embed=e)

    # Tag the person
    if orderType.upper() != "MARKET":
        await channel.send(f"<@{user.id}>")
