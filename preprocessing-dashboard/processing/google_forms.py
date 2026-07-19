import pandas as pd
import numpy as np
import io

def google_forms_processor(df_raw):
    df_cleaned = df_raw.copy()
    
    # Jalankan pembersihan teks spasi pada nama kolom asli
    df_cleaned.columns = [str(col).strip() for col in df_cleaned.columns]
    
    # --- TAHAP 1: DETEKSI & PARSING OTOMATIS MULTIPLE ANSWERS (MA) ---
    columns_to_process = list(df_cleaned.columns)
    
    for col in columns_to_process:
        if "timestamp" in col.lower():
            continue
            
        # Ambil sampel data yang tidak kosong
        sample_values = df_cleaned[col].dropna().astype(str)
        
        if not sample_values.empty:
            # Hitung rata-rata kemunculan koma per baris data
            comma_count = sample_values.str.count(',').mean()
            
            # Jika rata-rata koma > 0.2, terdeteksi sebagai Multiple Answers (MA)
            if comma_count > 0.2 and df_cleaned[col].dtype == 'object':
                all_options = set()
                for val in sample_values:
                    options = [opt.strip() for opt in val.split(',')]
                    all_options.update(options)
                
                # Buat kolom baru berdasarkan nama kolom asli + nama opsi jawaban
                for option in all_options:
                    if option:
                        clean_opt = option.replace(" ", "_").replace("/", "_").lower()[:20]
                        # Nama kolom tetap pakai pertanyaan asli di depan
                        child_col_name = f"{col}_{clean_opt}"
                        
                        df_cleaned[child_col_name] = df_cleaned[col].apply(
                            lambda x: 1 if pd.notna(x) and option in str(x) else 0
                        )
                
                # Hapus kolom utama aslinya setelah dipecah
                df_cleaned.drop(columns=[col], inplace=True)
                
    return df_cleaned


def calculate_column_metrics(df, col, settings):
    """
    Menghitung statistik berdasarkan tipe pertanyaan dan metrik yang dipilih user.
    Mengembalikan DataFrame hasil perhitungan dan dictionary metadata/informasi.
    """
    data_series = df[col].dropna()
    total_valid = len(data_series)
    
    if total_valid == 0:
        return None, "Kolom tidak memiliki data valid (kosong)."
        
    if settings['type'] == "Open":
        return data_series.head(5), "Open"
        
    # Hitung data kategori (Single / Multiple)
    counts = data_series.value_counts()
    df_res = pd.DataFrame({
        'Jawaban/Kategori': counts.index,
        'Absolute Count': counts.values
    })
    df_res['Percentage'] = (df_res['Absolute Count'] / total_valid) * 100
    
    # Filter kolom yang mau ditampilkan
    show_cols = ['Jawaban/Kategori']
    if "Absolute Count (Tanpa Blank)" in settings['metrics']:
        show_cols.append('Absolute Count')
    if "Percentage Count (Tanpa Blank)" in settings['metrics']:
        show_cols.append('Percentage')
        
    df_final = df_res[show_cols]
    
    # Hitung average jika diminta dan memungkinkan
    avg_val = None
    if "Average (Tanpa Blank)" in settings['metrics']:
        try:
            avg_val = pd.to_numeric(data_series, errors='coerce').mean()
        except:
            avg_val = "Bukan Angka"
            
    return df_final, {"type": "Categorical", "average": avg_val}


def generate_final_excel(df_raw, df_processed, calc_settings):
    """
    Membuat file Excel dalam bentuk memory buffer yang berisi:
    1. Raw Data Awal
    2. Data Hasil Preprocessing
    3. Hasil Perhitungan Analisis
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # Sheet 1: Raw Data Awal
        df_raw.to_excel(writer, sheet_name='1_Raw_Data_Awal', index=False)
        
        # Sheet 2: Data Hasil Preprocessing
        df_processed.to_excel(writer, sheet_name='2_Data_Preprocessed', index=False)
        
        # Sheet 3: Perhitungan Data
        summary_rows = []
        for col, settings in calc_settings.items():
            summary_rows.append({
                "Pertanyaan/Kolom": col,
                "Tipe": settings['type'],
                "Base Routing": settings['routing'],
                "Matriks di-input": ", ".join(settings['metrics'])
            })
        df_summary = pd.DataFrame(summary_rows)
        df_summary.to_excel(writer, sheet_name='3_Perhitungan_Data', index=False)
        
    return buffer.getvalue()
