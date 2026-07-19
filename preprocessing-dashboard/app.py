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
   # =====================================
    # GOOGLE FORMS FLOW
    # =====================================
    else:
        # 1. Baca file Excel menjadi DataFrame Pandas berdasarkan sheet yang dipilih
        df_raw = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        
        # 2. Masukkan DataFrame ke fungsi pemroses dan tampung hasilnya
        df_cleaned = google_forms_processor(df_raw)
        
        # 3. Tampilkan hasilnya di dashboard Streamlit
        st.write("### Hasil Pre-processing Google Forms")
        st.dataframe(df_cleaned)
        
        # (Opsional) Tambahkan tombol download jika Anda ingin mengunduh hasilnya
        csv = df_cleaned.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Unduh Data Hasil Pembersihan (CSV)",
            data=csv,
            file_name=f"cleaned_{selected_sheet}.csv",
            mime="text/csv",
        )

else:
    st.info("📥 Silakan unggah file kuesioner Excel (.xlsx) Anda terlebih dahulu untuk memulai.")
