import pandas as pd

from util.vars import get_json_data


async def get_data(keyword: str) -> pd.Dataframe:
    """
    Gets the data from StockTwits based on the passed keywords and returns a discord.Embed.

    Parameters
    ----------
    e : discord.Embed
        The discord.Embed where the data will be added to.
    keyword : str
        The specific keyword to get the data for. Options are: ts, m_day, wl_ct_day.

    Returns
    -------
    discord.Embed
        The discord.Embed with the data added to it.
    """

    # Keyword can be "ts", "m_day", "wl_ct_day"
    data = await get_json_data(
        "https://api.stocktwits.com/api/2/charts/" + keyword,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        },
    )

    # If no data could be found, return the embed
    if data == {}:
        return pd.DataFrame()

    table = pd.DataFrame(data["table"][keyword])
    stocks = pd.DataFrame(data["stocks"]).T
    stocks["stock_id"] = stocks.index.astype(int)
    full_df = pd.merge(stocks, table, on="stock_id")
    full_df.sort_values(by="val", ascending=False, inplace=True)

    # Set types
    full_df["price"] = full_df["price"].astype(float).fillna(0)
    full_df["change"] = full_df["change"].astype(float).fillna(0)
    full_df["symbol"] = full_df["symbol"].astype(str)
    full_df["name"] = full_df["name"].astype(str)

    # Format % change
    full_df["change"] = full_df["change"].apply(
        lambda x: f" (+{round(x,2)}% 📈)" if x > 0 else f" ({round(x,2)}% 📉)"
    )

    # Format price
    full_df["price"] = full_df["price"].apply(lambda x: round(x, 3))
    full_df["price"] = full_df["price"].astype(str) + full_df["change"]

    # Set values as string
    full_df["val"] = full_df["val"].astype(str)

    return full_df
