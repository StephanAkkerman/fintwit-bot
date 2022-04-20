from math import log, floor
import datetime

import discord


def human_format(number):
    """ 
    Takes a number and returns a human readable string
    
    https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python/45846841
    """
    # https://idlechampions.fandom.com/wiki/Large_number_abbreviations
    units = ["", "K", "M", "B", "t", "q"]
    k = 1000.0
    try:
        magnitude = int(floor(log(number, k)))
    except ValueError:
        magnitude = 0
        print("Could not get magnitude for number:", number)
    return "%.2f%s" % (number / k ** magnitude, units[magnitude])

def format_embed_length(data):
    # Data is a list containing lists of strings divided by white spaces
    
    for x in range(len(data)):
        if len(data[x]) > 1024:
            data[x] = data[x][:1024].split("\n")[:-1]
            # Fix everything that is not x
            for y in range(len(data)):
                if x != y:
                    data[y] = "\n".join(data[y].split("\n")[:len(data[x])])
                    
            data[x] = "\n".join(data[x])
            
    return data

# Used in gainers, losers loops
async def format_embed(df, type, source):
        """
        Takes a dataframe that has the columns:
        Symbol
        Price
        % Change
        Volume        
        """
        
        if source == 'binance':
            url = "https://www.binance.com/en/altcoins/gainers-losers"
            color = 0xF0B90B
            icon_url = "https://public.bnbstatic.com/20190405/eb2349c3-b2f8-4a93-a286-8f86a62ea9d8.png"
        elif source == 'yahoo':
            url = "https://finance.yahoo.com/" + type
            color = 0x720E9E
            icon_url = "https://s.yimg.com/cv/apiv2/myc/finance/Finance_icon_0919_250x252.png"
        
        e = discord.Embed(
            title=f"Top {len(df)} {type}",
            url=url,
            description="",
            color=color
        )
        
        df = df.astype({'Symbol' : str, 'Price' : float, '% Change' : float, 'Volume' : float})
        
        df = df.round({"Price": 3,"% Change": 2, "Volume":0})
        
        # Format the percentage change
        if len(df) > 15:
            df["% Change"] = df["% Change"].apply(
            lambda x: f" (+{x}%)" if x > 0 else f"({x}%)"
        )  
        else:
            df["% Change"] = df["% Change"].apply(
                lambda x: f" (+{x}% 📈)" if x > 0 else f"({x}% 📉)"
            )        
        
        # Post symbol, current price (weightedAvgPrice) + change, volume
        df['Price'] = df['Price'].astype(str) + df['% Change']

        # Format volume
        df['Volume'] = df['Volume'].apply(lambda x: "$" + human_format(x))
        
        ticker = "\n".join(df["Symbol"].tolist())
        prices = "\n".join(df["Price"].tolist())
        vol = "\n".join(df["Volume"].astype(str).tolist())
        
        # Prevent possible overflow        
        ticker, prices, vol = format_embed_length([ticker, prices, vol])
        
        e.add_field(
            name="Coin", value=ticker, inline=True,
        )

        e.add_field(
            name="Price", value=prices, inline=True,
        )

        e.add_field(
            name="Volume", value=vol, inline=True,
        )
        
        # Set datetime and binance icon
        e.set_footer(text=f"Today at {datetime.datetime.now().strftime('%H:%M')}",
                    icon_url=icon_url
        )
        
        return e