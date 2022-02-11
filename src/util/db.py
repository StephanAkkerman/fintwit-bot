import os
import pandas as pd

def get_db(database_name):
    """ 
    @param database_name: string, name of the database to get
    
    Get the database saved under data/database_name.pkl
    If it does not exist return an empty dataframe
    """
    
    pickle_loc = f"data/{database_name}.pkl"
    
    if os.path.exists(pickle_loc):
        return pd.read_pickle(pickle_loc)
    else:
        # If it does not exist return an empty dataframe
        return pd.DataFrame()
    
def update_db(db, database_name):
    """ 
    @param db: pandas dataframe, database to use for updating old database
    @param database_nameable: string, name of the database to update
    
    Update the database saved under data/database_name.pkl using db as the new database
    """
    
    pickle_loc = f"data/{database_name}.pkl"
    db.to_pickle(pickle_loc)