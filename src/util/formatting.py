from math import log, floor

def human_format(number):
    """ 
    Takes a number and returns a human readable string
    
    https://stackoverflow.com/questions/579310/formatting-long-numbers-as-strings-in-python/45846841
    """
    # https://idlechampions.fandom.com/wiki/Large_number_abbreviations
    units = ['', 'K', 'M', 'B', 't', 'q']
    k = 1000.0
    magnitude = int(floor(log(number, k)))
    return '%.2f%s' % (number / k**magnitude, units[magnitude])