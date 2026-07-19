import pandas as pd


def check_column_type(series):

    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    return "text"