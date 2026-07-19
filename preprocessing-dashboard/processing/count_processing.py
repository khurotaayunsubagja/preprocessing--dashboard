import pandas as pd
import numpy as np

def count_abs(series):
    """Menghitung frekuensi absolut (jumlah kemunculan) dari setiap nilai"""
    clean_series = series.dropna()
    if clean_series.empty:
        return pd.DataFrame(columns=['Jawaban', 'Jumlah (ABS)'])
        
    result = clean_series.value_counts().reset_index()
    result.columns = ['Jawaban', 'Jumlah (ABS)']
    return result

def count_percentage(series):
    """Menghitung persentase kemunculan nilai dengan aman untuk segala format kuesioner"""
    clean_series = series.dropna()
    
    if clean_series.empty:
        return pd.DataFrame(columns=['Jawaban', 'Persentase (%)'])
        
    # Jika data terdeteksi berupa angka 1 dan 0 (Pecahan kolom Multiple Answers)
    if set(clean_series.unique()).issubset({0, 1, 0.0, 1.0}):
        total_respondents = len(series)  # Pembagi adalah total responden aktif di survey
        total_positive = clean_series[clean_series == 1].count()
        pct = round((total_positive / total_respondents) * 100, 2)
        
        return pd.DataFrame({
            'Jawaban': ['Memilih Opsi Ini', 'Tidak Memilih'],
            'Persentase (%)': [pct, round(100 - pct, 2)]
        })
    
    # Perhitungan standar untuk Single Answer (SA)
    result = clean_series.value_counts(normalize=True).reset_index()
    result.columns = ['Jawaban', 'Persentase (%)']
    result['Persentase (%)'] = round(result['Persentase (%)'] * 100, 2)
    return result