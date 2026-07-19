import streamlit as st
import pandas as pd
import io

def run_survey_monkey_flow(uploaded_file, selected_sheet, raw_column_choices):
    st.info("💡 Sistem akan memandu Anda melalui tahapan Pembersihan Data secara berurutan.")

# ---------------------------------------------------------
    # INITIALIZATION: Load Data Awal & Riwayat Log ke Session State
    # ---------------------------------------------------------
    # 🌟 KUNCI PERBAIKAN: Pastikan sm_metadata selalu diinisialisasi secara independen
    if 'sm_metadata' not in st.session_state:
        st.session_state['sm_metadata'] = {}

    if 'df_sm_working' not in st.session_state or st.sidebar.button("🔄 Reset Data Mentah", key="reset_sm_data"):
        st.session_state['df_sm_working'] = pd.read_excel(uploaded_file, sheet_name=selected_sheet, header=[0, 1])
        st.session_state['sm_deleted_dup_count'] = 0
        st.session_state['sm_metadata'] = {} # Reset metadata jika data mentah di-reset
        if 'df_base_before_filter' in st.session_state:
            del st.session_state['df_base_before_filter']
        if 'processed_df' in st.session_state:
            del st.session_state['processed_df']
        if 'step1_cleared' in st.session_state:
            del st.session_state['step1_cleared']

    df_current = st.session_state['df_sm_working']

    # =========================================================
    # TAHAP 1: PEMERIKSAAN & HAPUS DUPLIKASI
    # =========================================================
    st.divider()
    st.write("### 👥 1. Tahapan Pemeriksaan Duplikasi")
    
    col_dup_select = st.selectbox(
        "Pilih kolom yang mau diperiksa duplikasinya:",
        raw_column_choices,
        key="sm_dup_col"
    )
    
    idx_dup_target = raw_column_choices.index(col_dup_select)
    actual_dup_target_col = df_current.columns[idx_dup_target]
    
    dup_mask_init = df_current.duplicated(subset=[actual_dup_target_col], keep=False)
    duplicate_values = df_current[dup_mask_init][actual_dup_target_col].unique()
    
    df_only_duplicates = df_current[df_current[actual_dup_target_col].isin(duplicate_values)].copy()
    
    if (df_only_duplicates.empty) or (len(duplicate_values) == 0):
        st.success("✅ Aman! Tidak ditemukan data duplikat pada kolom terpilih.")
    else:
        st.warning(f"⚠️ Terdeteksi data memiliki nilai duplikat pada kolom **{col_dup_select}**.")
        
        if st.button("⚡ Bersihkan Otomatis Semua Duplikat (Pertahankan Data Pertama)", type="primary", key="btn_auto_clean_dup"):
            before_count = len(df_current)
            df_cleaned = df_current.drop_duplicates(subset=[actual_dup_target_col], keep='first').reset_index(drop=True)
            st.session_state['sm_deleted_dup_count'] += (before_count - len(df_cleaned))
            st.session_state['df_sm_working'] = df_cleaned
            st.rerun()
            
        st.write("#### 🔍 Preview Data Duplikat:")
        
        df_preview_style = df_only_duplicates.copy()
        df_preview_style.columns = [f"{c[0]} - {c[1]}" if "Unnamed" not in str(c[1]) else str(c[0]) for c in df_preview_style.columns]
        flat_target_col = df_preview_style.columns[idx_dup_target]
        df_preview_style = df_preview_style.sort_values(by=[flat_target_col])

        def highlight_duplicate_groups(data):
            colors = ['#FFF2CC', '#D9EAD3', '#C9DAF8', '#F4CCCC', '#E1D5E7', '#FCE5CD', '#D5E8D4', '#E6F4EA']
            unique_vals = data[flat_target_col].unique()
            val_to_color = {val: colors[idx % len(colors)] for idx, val in enumerate(unique_vals)}
            style_df = pd.DataFrame('', index=data.index, columns=data.columns)
            for row_idx in data.index:
                current_val = data.loc[row_idx, flat_target_col]
                row_color = val_to_color.get(current_val, '')
                style_df.loc[row_idx, :] = f'background-color: {row_color}; color: black;'
            return style_df

        st.dataframe(df_preview_style.style.apply(highlight_duplicate_groups, axis=None), use_container_width=True)
        
        label_to_index_map = {}
        for counter, idx in enumerate(df_preview_style.index):
            respondent_id = df_preview_style.loc[idx, flat_target_col]
            ui_label = f"[#{counter+1}] Hapus Baris Index ke-{idx} (ID Responden: {respondent_id})"
            label_to_index_map[ui_label] = idx

        selected_labels_to_drop = st.multiselect(
            "Pilih baris spesifik yang ingin Anda BUANG secara manual:",
            options=list(label_to_index_map.keys()),
            key="sm_multiselect_drop"
        )
        
        if st.button("🗑️ Eksekusi Hapus Baris Terpilih", type="secondary"):
            if selected_labels_to_drop:
                indices_to_drop = [label_to_index_map[label] for label in selected_labels_to_drop]
                st.session_state['sm_deleted_dup_count'] += len(indices_to_drop)
                df_cleaned = df_current.drop(index=indices_to_drop).reset_index(drop=True)
                st.session_state['df_sm_working'] = df_cleaned
                st.rerun()
            else:
                st.info("Pilih minimal satu baris index untuk dihapus.")

    if st.session_state['sm_deleted_dup_count'] > 0:
        st.info(f"📊 **Log Pembersihan:** Sebanyak **{st.session_state['sm_deleted_dup_count']} baris** data duplikat telah dihapus.")

    # Checkpoint untuk lanjut ke tahap berikutnya
    st.write("")
    if st.checkbox("✅ Lanjutkan ke Tahap 2: Filtering Data & Routing", key="chk_step1_clear"):
        st.session_state['step1_cleared'] = True
    else:
        st.session_state['step1_cleared'] = False

    if st.session_state.get('step1_cleared', False):

        # =========================================================
        # TAHAP 2: FILTERING DATA (RENAME, TYPE DATA, & ROUTING)
        # =========================================================
        st.divider()
        st.write("### 🔍 2. Tahapan Filtering Data (Metadata & Base Routing)")
        st.info("💡 Atur penamaan analisis, tipe data, serta basis routing/penyaringan kolom di sini.")

        # Pilih kolom yang mau dikonfigurasi metadata-nya
        target_meta_col = st.selectbox(
            "Pilih Kolom Pertanyaan untuk Dikonfigurasi:",
            raw_column_choices,
            key="sm_meta_col_select"
        )
        
        # Ambil state metadata lama atau buat baru jika belum ada
        if target_meta_col not in st.session_state['sm_metadata']:
            st.session_state['sm_metadata'][target_meta_col] = {
                "alias_name": target_meta_col,
                "data_type": "Single Choice",
                "base_routing_col": "-- Tanpa Routing (Total Data) --",
                "routing_value": []
            }
            
        meta_data = st.session_state['sm_metadata'][target_meta_col]

        # Form Input Spesifikasi Filtering Data
        col_m1, col_m2, col_m3 = st.columns(3)
        
        with col_m1:
            new_alias = st.text_input("✍️ Nama Kolom Baru (Alias Analisis):", value=meta_data["alias_name"])
            st.session_state['sm_metadata'][target_meta_col]["alias_name"] = new_alias

        with col_m2:
            new_type = st.selectbox(
                "📁 Tipe Data Pertanyaan:",
                options=["Single Choice", "Multiple Choice", "Open-Ended / Text", "Numeric"],
                index=["Single Choice", "Multiple Choice", "Open-Ended / Text", "Numeric"].index(meta_data["data_type"])
            )
            st.session_state['sm_metadata'][target_meta_col]["data_type"] = new_type

        with col_m3:
            routing_options = ["-- Tanpa Routing (Total Data) --"] + [c for c in raw_column_choices if c != target_meta_col]
            
            # Proteksi jika opsi indeks hilang/bergeser
            default_routing_idx = 0
            if meta_data["base_routing_col"] in routing_options:
                default_routing_idx = routing_options.index(meta_data["base_routing_col"])
                
            new_routing_col = st.selectbox(
                "🛣️ Base Routingan (Kolom Acuan Denominator):",
                options=routing_options,
                index=default_routing_idx
            )
            st.session_state['sm_metadata'][target_meta_col]["base_routing_col"] = new_routing_col

        # Jika ada Base Routing yang aktif, pilih nilai kriteria filter peroutingannya
        if new_routing_col != "-- Tanpa Routing (Total Data) --":
            idx_route = raw_column_choices.index(new_routing_col)
            actual_route_col = df_current.columns[idx_route]
            unique_route_vals = sorted(df_current[actual_route_col].dropna().astype(str).unique().tolist())
            
            saved_route_vals = [v for v in meta_data["routing_value"] if v in unique_route_vals]
            
            selected_route_vals = st.multiselect(
                f"Pilih nilai dari [{new_routing_col}] sebagai syarat pengisian target:",
                options=unique_route_vals,
                default=saved_route_vals
            )
            st.session_state['sm_metadata'][target_meta_col]["routing_value"] = selected_route_vals
        else:
            st.session_state['sm_metadata'][target_meta_col]["routing_value"] = []

        # Tampilkan ringkasan metadata yang telah disimpan
        with st.expander("📋 Lihat Seluruh Metadata & Ringkasan Routing Terdaftar"):
            st.json(st.session_state['sm_metadata'])

        # =========================================================
        # TAHAP 3: PERHITUNGAN AGREGASI DATA & EXPORT
        # =========================================================
        st.divider()
        st.write("### 📈 3. Tahapan Analisis Distribusi Frekuensi & Ekspor Data")
        
        col_analysis_select = st.selectbox(
            "Pilih Kolom Kuesioner untuk Dihitung Distribusinya:",
            raw_column_choices,
            key="sm_analysis_col"
        )
        
        idx_analysis = raw_column_choices.index(col_analysis_select)
        actual_analysis_col = df_current.columns[idx_analysis]
        
        # Ambil aturan metadata/routing untuk kolom yang sedang dianalisis
        analysis_meta = st.session_state['sm_metadata'].get(col_analysis_select, {
            "alias_name": col_analysis_select,
            "data_type": "Single Choice",
            "base_routing_col": "-- Tanpa Routing (Total Data) --",
            "routing_value": []
        })
        
        # --- APLIKASIKAN LOGIKA BASE ROUTING ---
        if analysis_meta["base_routing_col"] != "-- Tanpa Routing (Total Data) --" and analysis_meta["routing_value"]:
            idx_base = raw_column_choices.index(analysis_meta["base_routing_col"])
            actual_base_col = df_current.columns[idx_base]
            
            # Saring data yang dijadikan denominator (Base Routing)
            df_routed_base = df_current[df_current[actual_base_col].astype(str).isin(analysis_meta["routing_value"])]
            total_denominator = len(df_routed_base)
            routing_info_text = f"🛣️ *Menggunakan Base Routing dari kolom:* `{analysis_meta['base_routing_col']}` dengan nilai kriteria {analysis_meta['routing_value']} (Total Sample Base = {total_denominator} responden)."
        else:
            df_routed_base = df_current
            total_denominator = len(df_current)
            routing_info_text = f"🌍 *Tanpa Routing:* Menggunakan total populasi data bersih ({total_denominator} responden)."
            
        st.caption(routing_info_text)

        # Hitung Nilai Absolut
        freq_abs = df_routed_base[actual_analysis_col].value_counts(dropna=False)
        
        # KUNCI PERBAIKAN: Perhitungan persentase dibagi berdasarkan total_denominator dari Base Routing
        freq_pct = (freq_abs / total_denominator) * 100 if total_denominator > 0 else freq_abs * 0
        
        df_summary = pd.DataFrame({
            'Jumlah Absolut (Count)': freq_abs,
            'Persentase (%)': freq_pct
        })
        df_summary.index.name = "Kategori Jawaban"
        df_summary = df_summary.reset_index()
        
        # Tampilkan info Tipe Data & Nama Alias di atas tabel hasil
        st.markdown(f"**Nama Analisis (Alias):** `{analysis_meta['alias_name']}` | **Tipe Data:** `{analysis_meta['data_type']}`")
        st.write(f"#### 📊 Tabel Distribusi Frekuensi")
        st.dataframe(df_summary.style.format({'Persentase (%)': '{:.2f}%'}), use_container_width=True)
        
        # --- PROSES EXPORT DATA KE EXCEL MULTI-SHEET ---
        st.write("#### 💾 Ekspor Hasil Analisis")
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            # Sheet 1: Data Bersih
            df_export_clean = df_current.copy()
            df_export_clean.columns = [f"{c[0]} - {c[1]}" if not pd.isna(c[1]) and "Unnamed" not in str(c[1]) else str(c[0]) for c in df_export_clean.columns]
            df_export_clean.to_excel(writer, sheet_name="Data_Bersih_Final", index=False)
            
            # Sheet 2: Ringkasan Distribusi Terkini
            df_summary.to_excel(writer, sheet_name="Ringkasan_Distribusi", index=False)
            
            # Sheet 3: Kamus Metadata & Routing Rule
            df_meta_export = pd.DataFrame(st.session_state['sm_metadata']).T
            df_meta_export.index.name = "Kolom Asli"
            df_meta_export.reset_index().to_excel(writer, sheet_name="Metadata_Routing_Rules", index=False)
            
        buffer.seek(0)
        
        st.download_button(
            label="📥 Download Hasil Pembersihan & Analisis (.xlsx)",
            data=buffer,
            file_name="Hasil_Analisis_SurveyMonkey_Routed.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )