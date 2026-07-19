import pandas as pd

def calculate_average(series):
    """Menghitung rata-rata nilai numerik skala survei"""
    clean_series = series.dropna()
    clean_numeric = pd.to_numeric(clean_series, errors='coerce').dropna()
    
    if clean_numeric.empty:
        return 0.0
        
    average = clean_numeric.mean()
    return round(average, 2)