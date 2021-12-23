import pandas as pd

def classify_sentiment(text):
    # Load model
    model = pd.read_pickle("sentiment_model.pkl")
    feature_selector = model["Feature Selector"][0]
    vectorizer = model["Vectorizer"][0]
    classifier = model["Classifier"][0]

    x = feature_selector.transform(vectorizer.transform([text]))
    return (classifier.predict(x.toarray())[0])

