from __future__ import annotations

import json

import aiohttp
import tls_client

from constants.logger import logger


async def get_json_data(
    url: str,
    headers: dict = None,
    cookies: dict = None,
    json_data: dict = None,
    text: bool = False,
) -> dict:
    """
    Asynchronous function to get JSON data from a website.

    Parameters
    ----------
    url : str
        The URL to get the data from.
    headers : dict, optional
        The headers send with the get request, by default None.

    Returns
    -------
    dict
        The response as a dict.
    """

    try:
        async with aiohttp.ClientSession(headers=headers, cookies=cookies) as session:
            async with session.get(url, json=json_data) as r:
                if text:
                    return await r.text()
                else:
                    return await r.json()
    except aiohttp.ClientError as e:
        logger.error(f"Error with get request for {url}.\nError: {e}")
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {url}.\nError: {e}")
        logger.error(f"Response: {await r.text()}")
    return {}


async def post_json_data(
    url: str,
    headers: dict = None,
    data: dict = None,
    json: dict = None,
) -> dict:
    """
    Asynchronous function to post JSON data from a website.

    Parameters
    ----------
    url : str
        The URL to get the data from.
    headers : dict, optional
        The headers send with the post request, by default None.

    Returns
    -------
    dict
        The response as a dict.
    """

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, data=data, json=json) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logger.error(f"Error with POST request for {url}.\nError: {e}")

    return {}


session = tls_client.Session(
    client_identifier="chrome112", random_tls_extension_order=True
)
