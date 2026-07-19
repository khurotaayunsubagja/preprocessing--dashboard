import pandas as pd


def load_excel(uploaded_file):

    excel_file = pd.ExcelFile(uploaded_file)

    return excel_file


def load_sheet(uploaded_file, sheet_name):

    df = pd.read_excel(
        uploaded_file,
        sheet_name=sheet_name
    )

    return df