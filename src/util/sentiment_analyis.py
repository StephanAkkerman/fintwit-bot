##> Imports
# > Standard libaries
from __future__ import annotations

# > Third party libraries
import pandas as pd
import numpy as np
import discord

# Load model
model = pd.read_pickle("models/sentiment_model.pkl")
feature_selector = model["Feature Selector"][0]
vectorizer = model["Vectorizer"][0]
classifier = model["Classifier"][0]


def classify_sentiment(text: str) -> np.ndarray:
    """
    Uses the text of a tweet to classify the sentiment of the tweet.

    Parameters
    ----------
    text : str
        The text of the tweet.

    Returns
    -------
    np.ndarray
        The probability of the tweet being bullish, neutral, or bearish.
    """

    x = feature_selector.transform(vectorizer.transform([text]))
    return classifier.predict_proba(x.toarray())[0]

def add_sentiment(e : discord.Embed, text: str) -> tuple[discord.Embed, str]:
    """
    Adds sentiment to a discord embed, based on the given text.

    Parameters
    ----------
    e : discord.Embed
        The embed to add the sentiment to.
    text : str
        The text to classify the sentiment of.

    Returns
    -------
    tuple[discord.Embed, str]
        discord.Embed
            The embed with the sentiment added.
        str
            The sentiment of the tweet.
    """
    
    sentiment = classify_sentiment(text)
    prediction = ("🐻 - Bearish", "🦆 - Neutral", "🐂 - Bullish")[np.argmax(sentiment)]
    e.add_field(
        name="Sentiment",
        value=f"{prediction} ({round(max(sentiment*100),2)}%)",
        inline=False,
    )
    prediction.split(" - ")[0]
    
    return e, prediction