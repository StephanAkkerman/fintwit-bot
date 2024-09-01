from api.http_client import get_json_data


async def get_treemap():
    return await get_json_data(
        "https://coin360.com/site-api/coins?currency=USD&period=24h&ranking=top100"
    )
