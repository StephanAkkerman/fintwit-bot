##> Imports
# > Standard libaries
from __future__ import annotations

import re
from typing import Iterable, Mapping

# > Third party libraries
import discord
from transformers import AutoTokenizer, BertForSequenceClassification, pipeline

MODEL_NAME = "StephanAkkerman/FinTwitBERT-sentiment"

# FinTwitBERT is a BERT model, so anything past 512 tokens is dropped. Long
# posts are split into segments (see `split_segments`) and each segment is
# classified separately, so nothing past the cut-off is silently ignored.
MAX_LENGTH = 512

# Sentence and paragraph boundaries. Tweets are not clean enough prose for a
# real sentence tokeniser to be worth the dependency; segments only need to be
# small enough that one of them rarely holds two opposing calls.
segment_re = re.compile(r"(?<=[.!?])\s+|[\n;]+")

# Shorter than this is not a claim about anything ("Edit:", "TL;DR").
MIN_SEGMENT_CHARS = 12

# Above/below this mean signed score a text reads bullish/bearish. Any single
# segment clears it: a 3-class argmax is never less confident than 1/3.
SENTIMENT_THRESHOLD = 0.15

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

# Built on first use instead of at import, so importing this module (or the
# modules that import it) does not block on loading half a gigabyte of BERT.
_pipe = None


def get_pipe():
    """
    Loads the FinTwitBERT sentiment pipeline, once per process.

    Returns
    -------
    transformers.Pipeline
        The text-classification pipeline, truncating at the model's limit.
    """

    global _pipe

    if _pipe is None:
        model = BertForSequenceClassification.from_pretrained(
            MODEL_NAME,
            num_labels=3,
            id2label={0: "NEUTRAL", 1: "BULLISH", 2: "BEARISH"},
            label2id={"NEUTRAL": 0, "BULLISH": 1, "BEARISH": 2},
            cache_dir="models/",
        )
        model.config.problem_type = "single_label_classification"
        tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME,
            cache_dir="models/",
            add_special_tokens=True,
        )
        model.eval()
        _pipe = pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=MAX_LENGTH,
        )

    return _pipe


def preprocess_text(tweet: str) -> str:
    # Replace URLs with URL token
    tweet = re.sub(r"http\S+", "[URL]", tweet)

    # Replace @mentions with @USER token
    tweet = re.sub(r"@\S+", "@USER", tweet)

    return tweet


def split_segments(text: str) -> list[str]:
    """
    Splits a text into sentence-sized segments.

    Parameters
    ----------
    text : str
        The text to split.

    Returns
    -------
    list[str]
        The segments, in order. A short text yields a single segment, which
        makes the segmented path identical to classifying the text as a whole.
    """

    segments = [
        segment.strip()
        for segment in segment_re.split(text or "")
        if len(segment.strip()) >= MIN_SEGMENT_CHARS
    ]

    return segments or ([text.strip()] if text and text.strip() else [])


def signed_score(label: str, score: float) -> float:
    """
    Signs a confidence by direction, so scores can be averaged.

    Parameters
    ----------
    label : str
        One of NEUTRAL, BULLISH, BEARISH.
    score : float
        The model's confidence in that label.

    Returns
    -------
    float
        Positive when bullish, negative when bearish, zero when neutral.
    """

    if label == "BULLISH":
        return float(score)
    if label == "BEARISH":
        return -float(score)
    return 0.0


def label_from_score(score: float) -> str:
    """
    Turns a mean signed score back into a label.

    Parameters
    ----------
    score : float
        A signed score, or the mean of several.

    Returns
    -------
    str
        One of NEUTRAL, BULLISH, BEARISH.
    """

    if score > SENTIMENT_THRESHOLD:
        return "BULLISH"
    if score < -SENTIMENT_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"


def classify_segments(segments: list[str]) -> list[float]:
    """
    Classifies each segment, in one batched pass.

    Parameters
    ----------
    segments : list[str]
        The segments to classify.

    Returns
    -------
    list[float]
        The signed score of each segment, in the same order.
    """

    if not segments:
        return []

    predictions = get_pipe()([preprocess_text(segment) for segment in segments])

    return [
        signed_score(prediction.get("label"), prediction.get("score", 0.0))
        for prediction in predictions
    ]


def alias_pattern(alias: str) -> re.Pattern:
    """
    Builds the pattern that finds a symbol's surface form in a segment.

    Parameters
    ----------
    alias : str
        A cashtag, hashtag or name as it appears in the text, e.g. BTC or
        BITCOIN.

    Returns
    -------
    re.Pattern
        Matches the alias with an optional $ or # in front. Short aliases are
        matched case-sensitively, because a two-letter ticker is otherwise
        indistinguishable from an ordinary word ("IT", "ON").
    """

    flags = re.IGNORECASE if len(alias) >= 4 else 0

    return re.compile(rf"[$#]?\b{re.escape(alias)}\b", flags)


def attribute_segments(
    segments: list[str], aliases: Mapping[str, Iterable[str]]
) -> dict[str, list[int]]:
    """
    Works out which segments speak about which symbol.

    A segment naming a single symbol is evidence about that symbol; a segment
    naming several ("$BTC over $ETH any day") says nothing about either in
    particular, so it is only used for a symbol that has no segment of its own.

    Parameters
    ----------
    segments : list[str]
        The segments of the text.
    aliases : Mapping[str, Iterable[str]]
        Symbol to the surface forms it may appear as in the text.

    Returns
    -------
    dict[str, list[int]]
        Symbol to the indices of the segments it is scored from. A symbol that
        appears in no segment is absent.
    """

    # Which symbols each segment names.
    named: dict[int, set[str]] = {}
    for symbol, symbol_aliases in aliases.items():
        patterns = [alias_pattern(alias) for alias in symbol_aliases if alias]
        for index, segment in enumerate(segments):
            if any(pattern.search(segment) for pattern in patterns):
                named.setdefault(index, set()).add(symbol)

    attributed: dict[str, list[int]] = {}
    for symbol in aliases:
        owned = sorted(index for index, names in named.items() if symbol in names)
        exclusive = [index for index in owned if len(named[index]) == 1]
        chosen = exclusive or owned
        if chosen:
            attributed[symbol] = chosen

    return attributed


def classify_text(
    text: str, aliases: Mapping[str, Iterable[str]] | None = None
) -> tuple[str, dict[str, str]]:
    """
    Classifies a text as a whole and, optionally, per symbol.

    Long posts used to be classified in one go, which meant every ticker in
    them carried the same label — and everything past 512 tokens was dropped.
    The text is split into segments instead: the overall sentiment is the mean
    of them, and a symbol is scored from the segments that name only it.

    Parameters
    ----------
    text : str
        The text to classify.
    aliases : Mapping[str, Iterable[str]], optional
        Symbol to the surface forms it may appear as in the text. Without it
        only the overall sentiment is returned.

    Returns
    -------
    tuple[str, dict[str, str]]
        str
            The emoji of the overall sentiment.
        dict[str, str]
            The emoji per symbol. A symbol that is named in no segment falls
            back to the overall sentiment.
    """

    segments = split_segments(text)
    if not segments:
        return label_to_emoji["NEUTRAL"], {}

    scores = classify_segments(segments)
    overall = label_from_score(sum(scores) / len(scores))
    overall_emoji = label_to_emoji[overall]

    if not aliases:
        return overall_emoji, {}

    attributed = attribute_segments(segments, aliases)
    per_symbol = {}
    for symbol in aliases:
        indices = attributed.get(symbol)
        if not indices:
            per_symbol[symbol] = overall_emoji
            continue
        mean = sum(scores[index] for index in indices) / len(indices)
        per_symbol[symbol] = label_to_emoji[label_from_score(mean)]

    return overall_emoji, per_symbol


def classify_sentiment(text: str) -> str:
    """
    Uses the text of a tweet to classify the sentiment of the tweet.

    Parameters
    ----------
    text : str
        The text of the tweet.

    Returns
    -------
    str
        The emoji of the sentiment: 🐂, 🐻 or 🦆.
    """

    emoji, _ = classify_text(text)

    return emoji


def add_sentiment(
    e: discord.Embed, text: str, aliases: Mapping[str, Iterable[str]] | None = None
) -> tuple[discord.Embed, str, dict[str, str]]:
    """
    Adds sentiment to a discord embed, based on the given text.

    Parameters
    ----------
    e : discord.Embed
        The embed to add the sentiment to.
    text : str
        The text to classify the sentiment of.
    aliases : Mapping[str, Iterable[str]], optional
        Symbol to the surface forms it may appear as in the text, used to
        score each symbol from the part of the text that is about it.

    Returns
    -------
    tuple[discord.Embed, str, dict[str, str]]
        discord.Embed
            The embed with the sentiment added.
        str
            The sentiment of the tweet.
        dict[str, str]
            The sentiment per symbol, empty when no aliases were given.
    """

    # Remove quote tweet formatting
    emoji, per_symbol = classify_text(text.split("\n\n> [@")[0], aliases)

    # Change color based on sentiment
    e.colour = color_table[emoji]

    return e, emoji, per_symbol
