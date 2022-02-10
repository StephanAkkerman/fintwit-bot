import os
import pandas as pd

def get_db():
    pickle_loc = "data/portfolio.pkl"
    
    if os.path.exists(pickle_loc):
        return pd.read_pickle(pickle_loc)
    else:
        # If it does not exist return an empty dataframe
        return pd.DataFrame()
    
def update_db(db):
    pickle_loc = "data/portfolio.pkl"
    db.to_pickle(pickle_loc)