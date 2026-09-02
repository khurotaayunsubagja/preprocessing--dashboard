import streamlit as st
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
        if summary_rows:
            df_summary = pd.DataFrame(summary_rows)
            df_summary.to_excel(writer, sheet_name='3_Perhitungan_Data', index=False)
        
    return buffer.getvalue()


# =====================================================================
# FUNGSI UTAMA UI STREAMLIT UNTUK GOOGLE FORMS
# =====================================================================
def run_google_forms_flow(uploaded_file, selected_sheet):
    st.subheader("📑 Google Forms Data Pre-processing Flow")
    st.caption("Kelola data mentah survei Anda secara terarah melalui tahapan pembersihan otomatis hingga kalkulasi statistik.")
    
    # Agar jika user mengganti sheet, data di-reset dengan benar (mirip logika Survey Monkey)
    state_key = f"gf_init_loaded_{selected_sheet}"
    
    if state_key not in st.session_state:
        df_init = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        st.session_state[state_key] = df_init.copy()
        st.session_state['gf_raw_df'] = df_init.copy()
        st.session_state['gf_processed_df'] = google_forms_processor(df_init)
    
    df_working = st.session_state['gf_processed_df']
    all_columns = list(df_working.columns)
    
    # Preview Data Awal
    with st.container(border=True):
        col_info1, col_info2 = st.columns([3, 1])
        with col_info1:
            st.markdown("##### 📊 **Pratinjau Data Kuesioner**")
            st.caption("Nama kolom dibersihkan otomatis & kolom kuesioner bertipe *Multiple Answers* berhasil dipecah.")
        with col_info2:
            st.metric(label="Total Baris Data", value=f"{len(df_working)}")
            
        st.dataframe(df_working.head(8), use_container_width=True)
    
    st.write("")

    # --- LANGKAH 1: Deteksi & Hapus Data Duplikat ---
    st.markdown("### 🔍 **Tahap 1: Eliminasi Data Duplikat**")
    with st.container(border=True):
        duplicate_keys = st.multiselect(
            "Pilih kolom acuan / kunci unik responden (misal: Nomor HP / Respondent ID):",
            options=all_columns,
            key="gf_dup_cols"
        )
        
        if duplicate_keys:
            # 1. Mencegah data kosong terhitung duplikat
            temp_keys_df = df_working[duplicate_keys].astype(str)
            is_empty = temp_keys_df.apply(lambda col: col.str.strip().isin(['', 'nan', 'None', 'null', '<NA>'])).any(axis=1)
            valid_mask = ~is_empty
            
            # 2. Hitung jumlah duplikat (hanya pada baris ekstra) khusus untuk data yang valid
            dup_mask_first = df_working.duplicated(subset=duplicate_keys, keep='first')
            dup_count = (dup_mask_first & valid_mask).sum()
            
            if dup_count > 0:
                st.warning(f"Terdeteksi **{dup_count}** baris data duplikat berdasarkan kolom pilihan Anda.")
                    
                st.write("👀 **Preview Data Duplikat (Baris dengan warna sama = data kembar):**")
                    
                all_dups_mask = df_working.duplicated(subset=duplicate_keys, keep=False)
                df_all_dups = df_working[all_dups_mask & valid_mask]
                    
                df_all_dups = df_all_dups.sort_values(by=duplicate_keys)
                
                # Logic Warna
                def highlight_groups(df_data):
                    colors = ['#FFF2CC', '#D9EAD3', '#C9DAF8', '#F4CCCC', '#E1D5E7', '#FCE5CD', '#D5E8D4', '#E6F4EA']
                    group_ids = df_data.groupby(duplicate_keys, sort=False).ngroup().tolist()
                    style_df = pd.DataFrame('', index=df_data.index, columns=df_data.columns)
                    for i in range(len(df_data)):
                        row_color = colors[group_ids[i] % len(colors)]
                        style_df.iloc[i] = f'background-color: {row_color}; color: black;'
                    return style_df

                styled_df = df_all_dups.style.apply(highlight_groups, axis=None)
                st.dataframe(styled_df, use_container_width=True)
                    
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
                        
                        df_empty = df_working[~valid_mask]
                        df_valid = df_working[valid_mask]
                        df_valid_dedup = df_valid.drop_duplicates(subset=duplicate_keys, keep=keep_val)
                        
                        df_working = pd.concat([df_empty, df_valid_dedup]).sort_index()
                        
                        st.session_state['gf_processed_df'] = df_working
                        st.success(f"Berhasil! Sisa data saat ini: {len(df_working)} baris.")
                        st.rerun()
            else:
                st.success("Data aman! Tidak ditemukan baris duplikat (dengan isian) pada kombinasi kolom ini.")
        else:
            st.caption("💡 *Pilih kolom kunci di atas untuk mendeteksi data duplikat secara langsung.*")
    
    st.write("")
    
    # --- LANGKAH 2: Filtering Data ---
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

    # --- LANGKAH 3: Konfirmasi Kelanjutan & Opsi Download ---
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

    # --- LANGKAH 4: Perhitungan & Paket Download Akhir ---
    if "Lanjutkan" in action_choice:
        st.markdown("---")
        st.subheader("📊 Modul Perhitungan & Analisis Data")
        st.caption("Pilih variabel dan tentukan metrik agregasi untuk memunculkan tabel rekapitulasi.")
        
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
