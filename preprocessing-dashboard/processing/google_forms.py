import streamlit as st
import pandas as pd
import numpy as np
import io

def google_forms_processor(df_raw):
    df_cleaned = df_raw.copy()
    df_cleaned.columns = [str(col).strip() for col in df_cleaned.columns]
    
    # DETEKSI & PARSING OTOMATIS MULTIPLE ANSWERS (MA)
    columns_to_process = list(df_cleaned.columns)
    for col in columns_to_process:
        if "timestamp" in col.lower():
            continue
            
        sample_values = df_cleaned[col].dropna().astype(str)
        if not sample_values.empty:
            comma_count = sample_values.str.count(',').mean()
            if comma_count > 0.2 and df_cleaned[col].dtype == 'object':
                all_options = set()
                for val in sample_values:
                    options = [opt.strip() for opt in val.split(',')]
                    all_options.update(options)
                
                for option in all_options:
                    if option:
                        clean_opt = option.replace(" ", "_").replace("/", "_").lower()[:20]
                        child_col_name = f"{col}_{clean_opt}"
                        df_cleaned[child_col_name] = df_cleaned[col].apply(
                            lambda x: 1 if pd.notna(x) and option in str(x) else 0
                        )
                df_cleaned.drop(columns=[col], inplace=True)
    return df_cleaned


def calculate_column_metrics(df, col, settings):
    data_series = df[col].dropna()
    total_valid = len(data_series)
    
    if total_valid == 0:
        return None, "Kolom tidak memiliki data valid (kosong)."
        
    if settings['type'] == "Open":
        return data_series.head(5), "Open"
        
    counts = data_series.value_counts()
    df_res = pd.DataFrame({
        'Jawaban/Kategori': counts.index,
        'Absolute Count': counts.values
    })
    df_res['Percentage'] = (df_res['Absolute Count'] / total_valid) * 100
    
    show_cols = ['Jawaban/Kategori']
    if "Absolute Count (Tanpa Blank)" in settings['metrics']:
        show_cols.append('Absolute Count')
    if "Percentage Count (Tanpa Blank)" in settings['metrics']:
        show_cols.append('Percentage')
        
    df_final = df_res[show_cols]
    
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
        df_raw.to_excel(writer, sheet_name='1_Raw_Data_Awal', index=False)
        df_processed.to_excel(writer, sheet_name='2_Data_Preprocessed', index=False)
        
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
    st.info("💡 Sistem akan memandu Anda melalui tahapan Pembersihan Data secara berurutan.")
    
    state_key = f"gf_init_loaded_{selected_sheet}"
    if state_key not in st.session_state or st.sidebar.button("🔄 Reset Data Mentah", key="reset_gf_data"):
        df_init = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
        st.session_state[state_key] = df_init.copy()
        st.session_state['gf_raw_df'] = df_init.copy()
        st.session_state['gf_processed_df'] = google_forms_processor(df_init)
        st.session_state['gf_deleted_dup_count'] = 0
        if 'gf_step1_cleared' in st.session_state: del st.session_state['gf_step1_cleared']
        if 'gf_step2_cleared' in st.session_state: del st.session_state['gf_step2_cleared']
    
    df_working = st.session_state['gf_processed_df']
    all_columns = list(df_working.columns)
    
    with st.container(border=True):
        col_info1, col_info2 = st.columns([3, 1])
        with col_info1:
            st.markdown("##### 📊 **Pratinjau Data Kuesioner (Google Forms)**")
            st.caption("Nama kolom dibersihkan otomatis & pertanyaan *Multiple Answers* telah dipecah menjadi kolom biner.")
        with col_info2:
            st.metric(label="Total Baris Data", value=f"{len(df_working)}")
        st.dataframe(df_working.head(5), use_container_width=True)

    # =========================================================
    # TAHAP 1: PEMERIKSAAN & HAPUS DUPLIKASI
    # =========================================================
    st.divider()
    st.write("### 👥 1. Tahapan Pemeriksaan Duplikasi")
    
    duplicate_keys = st.multiselect(
        "Pilih kolom acuan / kunci unik responden (misal: Nomor HP / Respondent ID):",
        options=all_columns,
        key="gf_dup_cols"
    )
    
    if duplicate_keys:
        temp_keys_df = df_working[duplicate_keys].astype(str)
        is_empty = temp_keys_df.apply(lambda col: col.str.strip().isin(['', 'nan', 'None', 'null', '<NA>'])).any(axis=1)
        valid_mask = ~is_empty
        
        dup_mask_first = df_working.duplicated(subset=duplicate_keys, keep='first')
        dup_count = (dup_mask_first & valid_mask).sum()
        
        if dup_count > 0:
            st.warning(f"⚠️ Terdeteksi **{dup_count}** baris data duplikat (ekstra) berdasarkan kolom pilihan Anda.")
            st.write("#### 🔍 Preview Data Duplikat:")
                
            all_dups_mask = df_working.duplicated(subset=duplicate_keys, keep=False)
            df_all_dups = df_working[all_dups_mask & valid_mask].sort_values(by=duplicate_keys)
            
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
                if st.button("🔥 Eksekusi Hapus Duplikat", type="primary", use_container_width=True):
                    keep_val = 'first' if "pertama" in keep_option.lower() else 'last'
                    
                    df_empty = df_working[~valid_mask]
                    df_valid = df_working[valid_mask]
                    
                    before_count = len(df_valid)
                    df_valid_dedup = df_valid.drop_duplicates(subset=duplicate_keys, keep=keep_val)
                    
                    df_working = pd.concat([df_empty, df_valid_dedup]).sort_index()
                    st.session_state['gf_processed_df'] = df_working
                    st.session_state['gf_deleted_dup_count'] += (before_count - len(df_valid_dedup))
                    st.rerun()
        else:
            st.success("✅ Aman! Tidak ditemukan data duplikat (dengan isian) pada kombinasi kolom ini.")

    if st.session_state.get('gf_deleted_dup_count', 0) > 0:
        st.info(f"📊 **Log Pembersihan:** Sebanyak **{st.session_state['gf_deleted_dup_count']} baris** data duplikat telah dihapus.")

    # Checkpoint Tahap 1
    st.write("")
    if st.checkbox("✅ Lanjutkan ke Tahap 2: Penyaringan Data", key="chk_gf_step1"):
        st.session_state['gf_step1_cleared'] = True
    else:
        st.session_state['gf_step1_cleared'] = False

    if st.session_state.get('gf_step1_cleared', False):

        # =========================================================
        # TAHAP 2: PENYARINGAN (FILTERING) RESPONDEN
        # =========================================================
        st.divider()
        st.write("### 🎯 2. Tahapan Penyaringan (Filtering) Data")
        
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

        # Checkpoint Tahap 2
        st.write("")
        if st.checkbox("✅ Lanjutkan ke Tahap 3: Analisis & Ekspor Data", key="chk_gf_step2"):
            st.session_state['gf_step2_cleared'] = True
        else:
            st.session_state['gf_step2_cleared'] = False

        if st.session_state.get('gf_step2_cleared', False):

            # =========================================================
            # TAHAP 3: PERHITUNGAN AGREGASI DATA & EXPORT
            # =========================================================
            st.divider()
            st.write("### 📈 3. Tahapan Analisis Distribusi Frekuensi & Ekspor Data")
            
            # Opsi Ekspor Data Bersih Langsung
            st.write("#### 💾 Opsi 1: Unduh Data Bersih Saja")
            csv_cleaned = df_working.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Unduh File Data Bersih Saja (.csv)",
                data=csv_cleaned,
                file_name=f"cleaned_gf_{selected_sheet}.csv",
                mime="text/csv",
                key="btn_download_only_clean"
            )
            
            st.markdown("---")
            st.write("#### 📊 Opsi 2: Lakukan Perhitungan Otomatis & Ekspor Paket Lengkap")
            
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
                st.markdown("##### Preview Tabel Ringkasan Hasil")
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
                final_excel_data = generate_final_excel(
                    st.session_state['gf_raw_df'], 
                    df_working, 
                    calc_settings
                )
                
                st.download_button(
                    label="🎉 Download Paket Data Lengkap & Report (.xlsx)",
                    data=final_excel_data,
                    file_name=f"final_report_gf_{selected_sheet}.xlsx",
                    mime="application/vnd.ms-excel",
                    key="btn_download_all",
                    use_container_width=True,
                    type="primary"
                )
