import streamlit as st
import pandas as pd

# =====================================
# CONFIG (Wajib di taruh paling atas!)
# =====================================
st.set_page_config(
    page_title="Dashboard Pengolahan Data",
    layout="wide"
)

# Import modul flow kuesioner (Router Utama)
from processing.survey_monkey import run_survey_monkey_flow
from processing.google_forms import run_google_forms_flow

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
        key="selected_sheet_main"
    )
    
    # =====================================
    # 3. PERCABANGAN LOGIK PLATFORM
    # =====================================
    if platform == "Survey Monkey":
        # Memanggil fungsi flow Survey Monkey
        run_survey_monkey_flow(uploaded_file, selected_sheet)
    else:
        # Memanggil fungsi flow Google Forms
        run_google_forms_flow(uploaded_file, selected_sheet)

else:
    st.info("📥 Silakan unggah file kuesioner Excel (.xlsx) Anda terlebih dahulu untuk memulai.")
