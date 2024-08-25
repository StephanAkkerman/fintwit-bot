from io import StringIO

import pandas as pd
from discord.ext import commands

from api.http_client import get_json_data


async def get_benzinga_data(stock: str) -> list:
    req = await get_json_data(
        f"https://www.benzinga.com/quote/{stock}/analyst-ratings", text=True
    )

    try:
        df = pd.read_html(StringIO(req))[0]
    except Exception:
        raise commands.UserInputError

    # Drop the 4rd row
    df = df.drop(3)

    # Drop 'Buy Now', 'Analyst Firm▲▼', 'Analyst & % Accurate▲▼','Get Alert' columns
    df = df.drop(
        columns=["Buy Now", "Analyst Firm▲▼", "Analyst & % Accurate▲▼", "Get Alert"]
    )

    return df
