##> Imports
# > Standard libaries
from __future__ import annotations
import re

# > Third party libraries
import discord
from transformers import AutoTokenizer, BertForSequenceClassification, pipeline

# Load model
model = BertForSequenceClassification.from_pretrained(
    "StephanAkkerman/FinTwitBERT-sentiment",
    num_labels=3,
    id2label={0: "NEUTRAL", 1: "BULLISH", 2: "BEARISH"},
    label2id={"NEUTRAL": 0, "BULLISH": 1, "BEARISH": 2},
    cache_dir="models/",
)
model.config.problem_type = "single_label_classification"
tokenizer = AutoTokenizer.from_pretrained(
    "StephanAkkerman/FinTwitBERT-sentiment",
    cache_dir="models/",
    add_special_tokens=True,
)
model.eval()
pipe = pipeline("text-classification", model=model, tokenizer=tokenizer)

label_to_emoji = {
    "NEUTRAL": "🦆",
    "BULLISH": "🐂",
    "BEARISH": "🐻",
}

color_table = {
    "🦆": discord.Colour.lighter_grey(),
    "🐂": discord.Colour.green(),
    "🐻": discord.Colour.red(),
}


def preprocess_text(tweet: str) -> str:
    # Replace URLs with URL token
    tweet = re.sub(r"http\S+", "[URL]", tweet)

    # Replace @mentions with @USER token
    tweet = re.sub(r"@\S+", "@USER", tweet)

    return tweet


def classify_sentiment(text: str) -> str:
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

    label = pipe(preprocess_text(text))[0].get("label")
    emoji = label_to_emoji[label]

    return emoji


def add_sentiment(e: discord.Embed, text: str) -> tuple[discord.Embed, str]:
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
    emoji = classify_sentiment(text.split("\n\n> [@")[0])

    # Change color based on sentiment
    e.colour = color_table[emoji]

    return e, emoji
