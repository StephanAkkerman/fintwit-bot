import pandas as pd
import numpy as np

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
