import pandas as pd
import numpy as np

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