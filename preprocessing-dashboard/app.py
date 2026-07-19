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
from processing.google_forms import (
    google_forms_processor, 
    calculate_column_metrics, 
    generate_final_excel
)

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
    # GOOGLE FORMS FLOW (Optimized UI/UX)
    # =====================================
    else:
        st.subheader("📑 Google Forms Data Pre-processing Flow")
        st.caption("Kelola data mentah survei Anda secara terarah melalui tahapan pembersihan otomatis hingga kalkulasi statistik.")
        
        # --- LANGKAH 1 & 2: Baca Data & Jalankan Otomatisasi Awal ---
        if 'gf_raw_df' not in st.session_state:
            df_init = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
            st.session_state['gf_raw_df'] = df_init.copy()
            st.session_state['gf_processed_df'] = google_forms_processor(df_init)
        
        df_working = st.session_state['gf_processed_df']
        all_columns = list(df_working.columns)
        
        # Preview Data Awal dalam Card Komponen yang adaptif terhadap tema
        with st.container(border=True):
            col_info1, col_info2 = st.columns([3, 1])
            with col_info1:
                st.markdown("##### 📊 **Pratinjau Data Kuesioner**")
                st.caption("Nama kolom dibersihkan otomatis & kolom kuesioner bertipe *Multiple Answers* berhasil dipecah.")
            with col_info2:
                st.metric(label="Total Baris Data", value=f"{len(df_working)}")
                
            st.dataframe(df_working.head(8), use_container_width=True)
        
        st.write("")

        # --- LANGKAH 3 & 4: Deteksi & Hapus Data Duplikat ---
        st.markdown("### 🔍 **Tahap 1: Eliminasi Data Duplikat**")
        with st.container(border=True):
            duplicate_keys = st.multiselect(
                "Pilih kolom acuan / kunci unik responden (misal: Nomor HP / Respondent ID):",
                options=all_columns,
                key="gf_dup_cols"
            )
            
            if duplicate_keys:
                dup_count = df_working.duplicated(subset=duplicate_keys).sum()
                
                if dup_count > 0:
                    st.warning(f"Terdeteksi **{dup_count}** baris data duplikat berdasarkan kolom pilihan Anda.")
                    
                    col_dup1, col_dup2 = st.columns([2, 1])
                    with col_dup1:
                        keep_option = st.selectbox(
                            "Tentukan baris yang ingin dipertahankan:",
                            options=["Pertahankan baris pertama (First)", "Pertahankan baris terakhir (Last)"],
                            key="gf_dup_keep"
                        )
                    with col_dup2:
                        st.write("")
                        st.write("")
                        if st.button("🔥 Hapus Data Duplikat", type="primary", use_container_width=True, key="btn_drop_dup"):
                            keep_val = 'first' if "pertama" in keep_option.lower() else 'last'
                            df_working = df_working.drop_duplicates(subset=duplicate_keys, keep=keep_val)
                            st.session_state['gf_processed_df'] = df_working
                            st.success(f"Berhasil! Sisa data saat ini: {len(df_working)} baris.")
                            st.rerun()
                else:
                    st.success("Data aman! Tidak ditemukan baris duplikat pada kombinasi kolom ini.")
            else:
                st.caption("💡 *Pilih kolom kunci di atas untuk mendeteksi data duplikat secara langsung.*")

        st.write("")

        # --- LANGKAH 5: Filtering Data ---
        st.markdown("### 🎯 **Tahap 2: Penyaringan (Filtering) Responden**")
        with st.container(border=True):
            filter_cols = st.multiselect(
                "Pilih kolom kriteria untuk menyaring data (Maksimal 3 kolom):",
                options=all_columns,
                max_selections=3,
                key="gf_filter_select"
            )
            
            if filter_cols:
                df_filtered = df_working.copy()
                # Grid responsif horizontal untuk filter box
                filter_boxes = st.columns(len(filter_cols))
                
                for idx, col in enumerate(filter_cols):
                    with filter_boxes[idx]:
                        unique_vals = df_working[col].dropna().unique().tolist()
                        selected_vals = st.multiselect(
                            f"Kategori filter [{col}]:",
                            options=unique_vals,
                            default=unique_vals,
                            key=f"gf_filter_val_{col}"
                        )
                        df_filtered = df_filtered[df_filtered[col].isin(selected_vals)]
                
                st.write("")
                if st.button("⚡ Terapkan Filter Aktif", key="btn_apply_filter", type="secondary"):
                    st.session_state['gf_processed_df'] = df_filtered
                    st.success(f"Filter diterapkan! Sisa data saat ini: {len(df_filtered)} baris.")
                    st.rerun()
            else:
                st.caption("💡 *Saat ini sistem memproses 100% data aktif tanpa penyaringan tambahan.*")

        st.write("")

        # --- LANGKAH 6: Konfirmasi Kelanjutan & Opsi Download ---
        st.markdown("### 🛠️ **Tahap 3: Konfirmasi & Arah Kerja**")
        with st.container(border=True):
            action_choice = st.radio(
                "Tentukan kelanjutan proses manajemen data Anda:",
                options=[
                    "📥 Selesai sampai tahapan ini & unduh hasil Pre-processing data bersih", 
                    "🚀 Lanjutkan ke modul Perhitungan / Analisis Statistik Kuesioner"
                ],
                key="gf_action_choice"
            )
            
            if "Selesai" in action_choice:
                csv_cleaned = df_working.to_csv(index=False).encode('utf-8')
                st.write("")
                st.download_button(
                    label="📥 Unduh File Data Bersih (.csv)",
                    data=csv_cleaned,
                    file_name=f"cleaned_{selected_sheet}.csv",
                    mime="text/csv",
                    key="btn_download_only_clean",
                    use_container_width=True
                )
        
        st.write("")

        # --- LANGKAH 7, 8 & 9: Perhitungan & Paket Download Akhir ---
        if "Lanjutkan" in action_choice:
            st.markdown("---")
            st.subheader("📊 Modul Perhitungan & Analisis Data")
            st.caption("Pilih variabel dan tentukan metrik agregasi untuk memunculkan tabel rekapitulasi.")
            
            # Langkah 7: Setup Form Pengaturan
            st.markdown("##### **1. Pemilihan Variabel Analisis**")
            columns_to_analyze = st.multiselect(
                "Pilih pertanyaan kuesioner yang ingin dihitung nilai metriknya:",
                options=all_columns,
                key="gf_cols_calc"
            )
            
            if columns_to_analyze:
                calc_settings = {}
                for col in columns_to_analyze:
                    with st.container(border=True):
                        st.markdown(f"⚙️ **Konfigurasi Variabel:** `{col}`")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            col_type = st.selectbox(f"Tipe Pertanyaan:", options=["Single Answer", "Multiple Answer", "Open"], key=f"type_{col}")
                        with c2:
                            routing = st.text_input(f"Base Routing:", value="All Responden", key=f"route_{col}")
                        with c3:
                            metrics = st.multiselect(f"Matriks Output:", options=["Average (Tanpa Blank)", "Percentage Count (Tanpa Blank)", "Absolute Count (Tanpa Blank)"], default=["Percentage Count (Tanpa Blank)"], key=f"metrics_{col}")
                        
                        calc_settings[col] = {"type": col_type, "routing": routing, "metrics": metrics}
                
                # --- LANGKAH 8: Preview Perhitungan ---
                st.write("")
                st.markdown("##### **2. Preview Tabel Ringkasan Hasil**")
                
                for col, settings in calc_settings.items():
                    with st.container(border=True):
                        head_col1, head_col2 = st.columns([3, 1])
                        with head_col1:
                            st.markdown(f"📝 **Kolom:** `{col}`")
                        with head_col2:
                            st.markdown(f"`Routing: {settings['routing']}`")
                        
                        result_data, meta = calculate_column_metrics(df_working, col, settings)
                        
                        if result_data is None:
                            st.caption(meta)
                        elif meta == "Open":
                            st.caption("Pratinjau Jawaban Eksploratif (Tipe Open Text):")
                            st.dataframe(result_data, use_container_width=True)
                        else:
                            if meta.get("average") is not None:
                                avg = meta["average"]
                                display_val = f"{avg:.2f}" if isinstance(avg, (int, float)) else str(avg)
                                st.metric(label="Nilai Rata-rata (Average)", value=display_val)
                                
                            st.dataframe(result_data, use_container_width=True)
                
                # --- LANGKAH 9: Download Paket File Lengkap ---
                st.write("")
                st.markdown("##### **3. Kompilasi Laporan Akhir kuesioner**")
                
                final_excel_data = generate_final_excel(
                    st.session_state['gf_raw_df'], 
                    df_working, 
                    calc_settings
                )
                
                st.download_button(
                    label="🎉 Download Paket Data Lengkap & Report (.xlsx)",
                    data=final_excel_data,
                    file_name=f"final_report_{selected_sheet}.xlsx",
                    mime="application/vnd.ms-excel",
                    key="btn_download_all",
                    use_container_width=True
                )
            else:
                st.info("Pilih minimal satu kolom kuesioner di atas untuk memulai kalkulasi.")

else:
    st.info("📥 Silakan unggah file kuesioner Excel (.xlsx) Anda terlebih dahulu untuk memulai.")
