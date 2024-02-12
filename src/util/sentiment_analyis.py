##> Imports
# > Standard libaries
from __future__ import annotations

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
    "StephanAkkerman/FinTwitBERT-sentiment", cache_dir="models/"
)
model.eval()
pipe = pipeline("text-classification", model=model, tokenizer=tokenizer)

label_to_emoji = {
    "NEUTRAL": "🦆",
    "BULLISH": "🐂",
    "BEARISH": "🐻",
}


def classify_sentiment(text: str) -> tuple[str, str]:
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

    label = pipe(text)[0].get("label")
    emoji = label_to_emoji[label]

    label = f"{emoji} - {label.capitalize()}"

    return label, emoji


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
    prediction, emoji = classify_sentiment(text.split("\n\n> [@")[0])

    e.add_field(
        name="Sentiment",
        value=f"{prediction}",
        inline=False,
    )

    return e, emoji
