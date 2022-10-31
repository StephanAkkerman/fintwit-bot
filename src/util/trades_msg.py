##> Imports
import datetime
import ccxt.pro
import pandas as pd

# > Discord dependencies
import discord

# Local dependencies
import util.vars
import util.trades_msg
from util.db import get_db, update_db
from util.vars import stables
from util.exchange_data import get_data, get_usd_price, get_buying_price
from util.formatting import format_change


async def on_msg(msg: list, 
                 exchange : ccxt.pro.Exchange, 
                 trades_channel : discord.TextChannel, 
                 row : pd.Series, 
                 user : discord.User) -> None:
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
    sym = msg['symbol'] #BNB/USDT
    orderType = msg['type'] # market, limit, stop, stop limit
    side = msg['side'] # buy, sell
    price = round(msg['price'],4)
    amount = round(msg['amount'],4)
    cost = round(msg['cost'],4) # If /USDT, then this is the USD value
    
    # Get the value in USD
    usd = price
    base = sym.split('/')[0]
    quote = sym.split('/')[1]                
    if quote not in stables:
        usd = await get_usd_price(exchange, base)
        
    # Get profit / loss if it is a sell
    profit_loss = None
    if side == 'sell':
        buying_price = await get_buying_price(exchange, sym, True)
        if buying_price != 0:
            price_change = price - buying_price
            
            if price_change != 0:
                percent_change = round((price_change / buying_price) * 100, 2)
            else:
                percent_change = 0
                
            percent_change = format_change(percent_change)
            profit_loss = f"${round(price_change * amount, 2)} ({percent_change})"
        
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
        profit_loss
    )

    # Assets db: asset, owned (quantity), exchange, id, user
    assets_db = get_db("assets")

    # Drop all rows for this user and exchange
    updated_assets_db = assets_db.drop(
        assets_db[
            (assets_db["id"] == row['id']) & (assets_db["exchange"] == exchange.id)
        ].index
    )

    assets_db = pd.concat(
        [updated_assets_db, await get_data(row)]
    ).reset_index(drop=True)

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
    profit_loss : str = None,
) -> None:
    """
    Formats the Discord embed that will be send to the dedicated trades channel.

    Parameters
    ----------
    exchange : str
        The name of the exchange, currently only supports "binance" and "kucoin".
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

    e = discord.Embed(
        title=f"{orderType.capitalize()} {side.lower()} {quantity} {symbol}",
        description="",
        color=0xF0B90B if exchange == "binance" else 0x24AE8F,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    # Set the embed fields
    e.set_author(name=user.name, icon_url=user.display_avatar.url)

    # If the quote is USD, then the price is the USD value
    if symbol.endswith("USDT") or symbol.endswith("USD") or symbol.endswith("BUSD"):
        price = f"${price}"

    e.add_field(
        name="Price",
        value=price,
        inline=True,
    )

    if profit_loss:
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

    e.set_footer(
        text="\u200b",
        icon_url="https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png"
        if exchange == "binance"
        else "https://yourcryptolibrary.com/wp-content/uploads/2021/12/Kucoin-exchange-logo-1.png",
    )

    await channel.send(embed=e)

    # Tag the person
    if orderType.upper() != "MARKET":
        await channel.send(f"<@{user.id}>")