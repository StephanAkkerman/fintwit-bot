import pandas as pd

# Load model
model = pd.read_pickle("models/sentiment_model.pkl")
feature_selector = model["Feature Selector"][0]
vectorizer = model["Vectorizer"][0]
classifier = model["Classifier"][0]

def classify_sentiment(text):
    
    x = feature_selector.transform(vectorizer.transform([text]))
    return classifier.predict_proba(x.toarray())[0]