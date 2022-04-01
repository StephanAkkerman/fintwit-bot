import pandas as pd
import sqlite3


def get_db(database_name):
    """ 
    @param database_name: string, name of the database to get
    
    Get the database saved under data/database_name.pkl
    If it does not exist return an empty dataframe
    """
    db_loc = f"data/{database_name}.db"
    cnx = sqlite3.connect(db_loc)

    try:
        return pd.read_sql_query(f"SELECT * FROM {database_name}", cnx)
    except Exception:
        print(f"No {database_name}.db found, returning empty db")
        return pd.DataFrame()


def update_db(db, database_name):
    """ 
    @param db: pandas dataframe, database to use for updating old database
    @param database_nameable: string, name of the database to update
    
    Update the database saved under data/database_name.pkl using db as the new database
    """

    db_loc = f"data/{database_name}.db"
    db.to_sql(database_name, sqlite3.connect(db_loc), if_exists="replace", index=False)
