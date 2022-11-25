##> Imports
# > Standard libaries
from __future__ import annotations

# > Third party libraries
import discord
from transformers import BertTokenizer, BertForSequenceClassification, pipeline
import nltk
import numpy as np
from nltk.sentiment.vader import SentimentIntensityAnalyzer


# Load model
try:
    finbert = BertForSequenceClassification.from_pretrained('./models')
    tokenizer = BertTokenizer.from_pretrained("yiyanghkust/finbert-tone")
    nlp = pipeline("text-classification", model=finbert, tokenizer=tokenizer)
    use_finbert = True
except Exception as e:
    use_finbert = False
    print("Did not load premium model...")

def classify_sentiment(text: str) -> tuple[str,str]:
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
    
    pred = nlp(text)[0]
    label = pred['label']
    
    if label == "Positive":
        label = "🐂 - Bullish"
        emoji = "🐂"
    elif label == "Neutral":
        label = "🦆 - Neutral"
        emoji = "🦆"
    elif label == "Negative":
        label = "🐻 - Bearish"
        emoji = "🐻"
        
    #score = round(score*100, 2)
        
    return label, emoji

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
    
    # Remove quote tweet formatting
    if use_finbert:
        prediction, emoji = classify_sentiment(text.split('\n\n> [@')[0])
    else:
        try:
            analyzer = SentimentIntensityAnalyzer()
            sentiment = analyzer.polarity_scores(text)
        except LookupError:
            # Download the NLTK packages
            nltk.download("vader_lexicon")

            # Try again
            analyzer = SentimentIntensityAnalyzer()
            sentiment = analyzer.polarity_scores(text)
            
        neg = sentiment['neg']
        neu = sentiment['neu']
        pos = sentiment['pos']
            
        # Pick the highest value
        prediction = ['🐻 - Bearish', '🦆 - Neutral', '🐂 - Bullish'][np.argmax([neg, neu, pos])]
        emoji = prediction[0]
    
    e.add_field(
        name="Sentiment",
        value=f"{prediction}",
        inline=False,
    )
    
    return e, emoji