import streamlit as st
import pandas as pd
import os
import sys

# =====================================
# CONFIG (Wajib di taruh paling atas!)
# =====================================
st.set_page_config(
    page_title="Dashboard Pengolahan Data",
    layout="wide"
)

# Import modul flow kuesioner Anda
from processing.survey_monkey import run_survey_monkey_flow
from processing.google_forms import google_forms_processor

# Header Aplikasi
st.title("Dashboard Pengolahan Data Excel")
st.markdown(
    "### 👋 Hi Team Market Insight, yuk upload data mu dan lakukan pre processing disini!"
)
st.divider()

# ==========================================
# 1. PENGATURAN PLATFORM KUESIONER
# ==========================================
st.write("### Pengaturan Platform Kuesioner")
platform = st.radio(
    "Pilih Platform Asal Survey Kamu:",
    options=["Google Forms", "Survey Monkey"],
    key="survey_platform"
)

# ==========================================
# 2. SATU PINTU UNTUK PROSES UNGGAH FILE Excel
# ==========================================
uploaded_file = st.file_uploader("Unggah File Kuesioner (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # Mengambil daftar sheet dari file Excel yang diunggah
    excel_file = pd.ExcelFile(uploaded_file)
    sheet_names = excel_file.sheet_names
    
    selected_sheet = st.selectbox(
        "Silakan pilih Sheet/Tab data kuesioner Anda:", 
        options=sheet_names,
        key="sm_selected_sheet"
    )
    
    # =====================================
    # 3. PERCABANGAN LOGIK PLATFORM
    # =====================================
    if platform == "Survey Monkey":
        # Gunakan session state khusus tracking sheet survey monkey agar tidak reload konstan
        state_key = f"sm_init_loaded_{selected_sheet}"
        
        if state_key not in st.session_state:
            # Membaca file dengan format Multi-Index [0, 1] khusus Survey Monkey
            df_init = pd.read_excel(
                uploaded_file,
                sheet_name=selected_sheet,
                header=[0, 1]
            )
            st.session_state[state_key] = df_init
            # Inisialisasi df_sm_working untuk dipakai di internal flow
            st.session_state['df_sm_working'] = df_init.copy()
            st.session_state['sm_deleted_dup_count'] = 0
            st.session_state['sm_deleted_filter_count'] = 0
        else:
            df_init = st.session_state[state_key]

        # Membuat text gabungan kolom Multi-Index untuk dropdown pembersihan
        raw_column_choices = []
        for col in df_init.columns:
            main_txt = str(col[0]).strip()
            if not pd.isna(col[1]) and "Unnamed" not in str(col[1]):
                sub_txt = f" - {str(col[1]).strip()}"
            else:
                sub_txt = ""
            raw_column_choices.append(f"{main_txt}{sub_txt}")

        # Panggil flow Survey Monkey mandiri Anda
        run_survey_monkey_flow(
            uploaded_file,
            selected_sheet,
            raw_column_choices
        )

    # =====================================
    # GOOGLE FORMS FLOW
    # =====================================
    else:
        st.write("## 📑 Google Forms Data Pre-processing Flow")
        
        # --- LANGKAH 1 & 2: Baca Data & Jalankan Otomatisasi Awal ---
        if 'gf_raw_df' not in st.session_state:
            df_init = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            st.session_state['gf_raw_df'] = df_init.copy()
            # Memanggil fungsi pemroses utama dari google_forms.py
            st.session_state['gf_processed_df'] = google_forms_processor(df_init)
        
        df_working = st.session_state['gf_processed_df']
        
        st.write("### 1 & 2. Tampilan Data Awal (Setelah Auto-detect Multiple Answers)")
        st.dataframe(df_working.head(10))
        st.info(f"Total baris data saat ini: **{len(df_working)}** baris.")
        st.divider()

        # --- LANGKAH 3 & 4: Deteksi & Hapus Data Duplikat ---
        st.write("### 3 & 4. Tahap Pemeriksaan Data Duplikat")
        all_columns = list(df_working.columns)
        
        duplicate_keys = st.multiselect(
            "Pilih kolom yang mau dijadikan patokan untuk mengecek duplikat (misal: Nomor HP, Respondent ID):",
            options=all_columns,
            key="gf_dup_cols"
        )
        
        if duplicate_keys:
            dup_count = df_working.duplicated(subset=duplicate_keys).sum()
            st.warning(f"Terdeteksi **{dup_count}** data duplikat berdasarkan kolom yang Anda pilih.")
            
            keep_option = st.selectbox(
                "Pilih baris mana yang mau dipertahankan (sisanya akan dihapus):",
                options=["Pertahankan baris pertama (First)", "Pertahankan baris terakhir (Last)"],
                key="gf_dup_keep"
            )
            
            if st.button("Hapus Data Duplikat", type="primary", key="btn_drop_dup"):
                keep_val = 'first' if "pertama" in keep_option.lower() else 'last'
                df_working = df_working.drop_duplicates(subset=duplicate_keys, keep=keep_val)
                st.session_state['gf_processed_df'] = df_working
                st.success(f"Berhasil menghapus duplikat! Sisa data: {len(df_working)} baris.")
                st.rerun()
        else:
            st.info("Pilih satu atau beberapa kolom di atas untuk menganalisis data duplikat.")
        st.divider()

        # --- LANGKAH 5: Filtering Data (Maksimal 3 Kolom) ---
        st.write("### 5. Tahapan Filtering Data (Maksimal 3 Kolom)")
        
        filter_cols = st.multiselect(
            "Pilih kolom untuk filtering data (Maksimal 3):",
            options=all_columns,
            max_selections=3,
            key="gf_filter_select"
        )
        
        if filter_cols:
            df_filtered = df_working.copy()
            for col in filter_cols:
                unique_vals = df_working[col].dropna().unique().tolist()
                selected_vals = st.multiselect(
                    f"Pilih nilai untuk kolom [{col}] yang ingin dimasukkan dalam analisis:",
                    options=unique_vals,
                    default=unique_vals,
                    key=f"gf_filter_val_{col}"
                )
                df_filtered = df_filtered[df_filtered[col].isin(selected_vals)]
            
            if st.button("Terapkan Filter Data", key="btn_apply_filter"):
                st.session_state['gf_processed_df'] = df_filtered
                st.success(f"Filter berhasil diterapkan! Sisa data setelah filter: {len(df_filtered)} baris.")
                st.rerun()
        else:
            st.info("Data saat ini berjalan menggunakan data tanpa filter tambahan.")
        st.divider()

        # --- LANGKAH 6: Konfirmasi Kelanjutan & Opsi Download ---
        st.write("### 6. Konfirmasi Tahap Pre-processing")
        action_choice = st.radio(
            "Apakah Anda ingin melanjutkan ke tahapan Perhitungan Data?",
            options=["Tidak, selesai sampai sini dan unduh hasil Pre-processing", "Ya, lanjut ke Perhitungan Data"],
            key="gf_action_choice"
        )
        
        if "Tidak" in action_choice:
            csv_cleaned = df_working.to_csv(index=False).encode('utf-8')
            st.success("Tahap pre-processing Anda selesai! Silakan unduh file Anda di bawah ini:")
            st.download_button(
                label="📥 Unduh Data Hasil Preprocessing (CSV)",
                data=csv_cleaned,
                file_name=f"cleaned_{selected_sheet}.csv",
                mime="text/csv",
                key="btn_download_only_clean"
            )
        
        # --- LANGKAH 7, 8 & 9: Perhitungan & Paket Download Akhir ---
        else:
            st.divider()
            st.write("### 7. Pengaturan Perhitungan Analisis Data")
            
            columns_to_analyze = st.multiselect(
                "Pilih kolom/pertanyaan yang ingin dianalisis perhitungannya:",
                options=all_columns,
                key="gf_cols_calc"
            )
            
            if columns_to_analyze:
                calc_settings = {}
                for col in columns_to_analyze:
                    st.markdown(f"#### Pengaturan untuk Kolom: *{col}*")
                    col_type = st.selectbox(f"Tipe pertanyaan [{col}]:", options=["Single Answer", "Multiple Answer", "Open"], key=f"type_{col}")
                    routing = st.text_input(f"Base Routing untuk [{col}]:", value="All Responden", key=f"route_{col}")
                    metrics = st.multiselect(f"Pilih matriks:", options=["Average (Tanpa Blank)", "Percentage Count (Tanpa Blank)", "Absolute Count (Tanpa Blank)"], default=["Percentage Count (Tanpa Blank)"], key=f"metrics_{col}")
                    
                    calc_settings[col] = {"type": col_type, "routing": routing, "metrics": metrics}
                
                # --- LANGKAH 8: Preview Perhitungan (Memanggil Fungsi Baru di google_forms.py) ---
                st.divider()
                st.write("### 8. Preview Hasil Perhitungan Data")
                
                for col, settings in calc_settings.items():
                    st.write(f"**Hasil Analisis Kolom:** {col} *(Routing: {settings['routing']})*")
                    
                    result_data, meta = calculate_column_metrics(df_working, col, settings)
                    
                    if result_data is None:
                        st.warning(meta)
                    elif meta == "Open":
                        st.write("Tipe data Open text. Menampilkan 5 sampel jawaban teratas:")
                        st.dataframe(result_data)
                    else:
                        st.dataframe(result_data)
                        if meta.get("average") is not None:
                            avg = meta["average"]
                            st.metric(label=f"Rata-rata (Average) [{col}]", value=f"{avg:.2f}" if isinstance(avg, (int, float)) else str(avg))
                
                # --- LANGKAH 9: Download Paket File Lengkap ---
                st.divider()
                st.write("### 9. Unduh Semua Hasil Pemrosesan (All-in-One)")
                
                final_excel_data = generate_final_excel(
                    st.session_state['gf_raw_df'], 
                    df_working, 
                    calc_settings
                )
                
                st.download_button(
                    label="📥 Download Paket Data Lengkap (.xlsx)",
                    data=final_excel_data,
                    file_name=f"final_report_{selected_sheet}.xlsx",
                    mime="application/vnd.ms-excel",
                    key="btn_download_all"
                )
            else:
                st.info("Pilih minimal 1 kolom di atas untuk mulai melakukan konfigurasi perhitungan.")
  from processing.google_forms import (
    google_forms_processor, 
    calculate_column_metrics, 
    generate_final_excel
)

else:
    st.info("📥 Silakan unggah file kuesioner Excel (.xlsx) Anda terlebih dahulu untuk memulai.")
