```python
import pandas as pd
import numpy as np
import io


# ============================================================
# 1. GOOGLE FORMS PROCESSOR
# ============================================================

def google_forms_processor(df_raw):

    df_cleaned = df_raw.copy()

    # Bersihkan spasi pada nama kolom
    df_cleaned.columns = [
        str(col).strip()
        for col in df_cleaned.columns
    ]

    # ========================================================
    # TAHAP 1: DETEKSI & PARSING MULTIPLE ANSWERS (MA)
    # ========================================================

    columns_to_process = list(df_cleaned.columns)

    for col in columns_to_process:

        if "timestamp" in col.lower():
            continue

        # Ambil sampel data yang tidak kosong
        sample_values = (
            df_cleaned[col]
            .dropna()
            .astype(str)
        )

        if not sample_values.empty:

            # Hitung rata-rata jumlah koma per baris
            comma_count = (
                sample_values
                .str.count(',')
                .mean()
            )

            # Jika rata-rata koma > 0.2,
            # dianggap sebagai Multiple Answer
            if (
                comma_count > 0.2
                and df_cleaned[col].dtype == 'object'
            ):

                all_options = set()

                for val in sample_values:

                    options = [
                        opt.strip()
                        for opt in val.split(',')
                    ]

                    all_options.update(options)

                # Buat kolom dummy untuk setiap opsi
                for option in all_options:

                    if option:

                        clean_opt = (
                            option
                            .replace(" ", "_")
                            .replace("/", "_")
                            .lower()[:20]
                        )

                        child_col_name = (
                            f"{col}_{clean_opt}"
                        )

                        df_cleaned[child_col_name] = (
                            df_cleaned[col].apply(
                                lambda x:
                                    1
                                    if (
                                        pd.notna(x)
                                        and option in str(x)
                                    )
                                    else 0
                            )
                        )

                # Hapus kolom MA original
                df_cleaned.drop(
                    columns=[col],
                    inplace=True
                )

    return df_cleaned


# ============================================================
# 2. DUPLICATE CHECKING
# ============================================================

def check_duplicates(
    df,
    subset_columns=None
):

    """
    Mengecek seluruh data yang memiliki duplikat.

    subset_columns:
        None = mengecek berdasarkan seluruh kolom
        list = mengecek berdasarkan kolom tertentu

    keep=False digunakan agar SEMUA baris dalam
    kelompok duplikat ditampilkan, termasuk baris pertama.
    """

    # Jika tidak memilih kolom tertentu
    if (
        subset_columns is None
        or len(subset_columns) == 0
    ):

        duplicate_mask = df.duplicated(
            keep=False
        )

    # Jika memilih kolom tertentu
    else:

        duplicate_mask = df.duplicated(
            subset=subset_columns,
            keep=False
        )

    # Ambil SEMUA baris yang terindikasi duplikat
    df_duplicates = df.loc[
        duplicate_mask
    ].copy()

    # Tambahkan index asli
    df_duplicates.insert(
        0,
        "_Original_Index",
        df_duplicates.index
    )

    return df_duplicates


# ============================================================
# 3. DELETE SELECTED DUPLICATES
# ============================================================

def delete_selected_duplicates(
    df,
    selected_indices
):

    """
    Menghapus baris yang dipilih user dari dataframe.

    selected_indices:
        list berisi index asli dataframe
        yang ingin dihapus.
    """

    # Jika tidak ada data yang dipilih
    if (
        selected_indices is None
        or len(selected_indices) == 0
    ):
        return df.copy()

    # Hapus berdasarkan original index
    df_updated = df.drop(
        index=selected_indices
    ).copy()

    # Reset index setelah penghapusan
    df_updated.reset_index(
        drop=True,
        inplace=True
    )

    return df_updated


# ============================================================
# 4. CALCULATE COLUMN METRICS
# ============================================================

def calculate_column_metrics(
    df,
    col,
    settings
):

    """
    Menghitung statistik berdasarkan tipe pertanyaan
    dan metrik yang dipilih user.
    """

    data_series = df[col].dropna()

    total_valid = len(data_series)

    if total_valid == 0:

        return (
            None,
            "Kolom tidak memiliki data valid (kosong)."
        )

    # --------------------------------------------------------
    # OPEN QUESTION
    # --------------------------------------------------------

    if settings['type'] == "Open":

        return (
            data_series.head(5),
            "Open"
        )

    # --------------------------------------------------------
    # SINGLE / MULTIPLE
    # --------------------------------------------------------

    counts = data_series.value_counts()

    df_res = pd.DataFrame({

        'Jawaban/Kategori': counts.index,

        'Absolute Count': counts.values

    })

    df_res['Percentage'] = (
        df_res['Absolute Count']
        / total_valid
    ) * 100

    # --------------------------------------------------------
    # FILTER KOLOM BERDASARKAN METRICS
    # --------------------------------------------------------

    show_cols = [
        'Jawaban/Kategori'
    ]

    if (
        "Absolute Count (Tanpa Blank)"
        in settings['metrics']
    ):

        show_cols.append(
            'Absolute Count'
        )

    if (
        "Percentage Count (Tanpa Blank)"
        in settings['metrics']
    ):

        show_cols.append(
            'Percentage'
        )

    df_final = df_res[
        show_cols
    ]

    # --------------------------------------------------------
    # AVERAGE
    # --------------------------------------------------------

    avg_val = None

    if (
        "Average (Tanpa Blank)"
        in settings['metrics']
    ):

        try:

            numeric_series = pd.to_numeric(
                data_series,
                errors='coerce'
            )

            avg_val = numeric_series.mean()

        except:

            avg_val = "Bukan Angka"

    return (
        df_final,
        {
            "type": "Categorical",
            "average": avg_val
        }
    )


# ============================================================
# 5. GENERATE FINAL EXCEL
# ============================================================

def generate_final_excel(
    df_raw,
    df_processed,
    calc_settings
):

    """
    Membuat file Excel:

    1. Raw Data Awal
    2. Data Hasil Preprocessing
    3. Hasil Perhitungan Analisis
    """

    buffer = io.BytesIO()

    with pd.ExcelWriter(
        buffer,
        engine='xlsxwriter'
    ) as writer:

        # ----------------------------------------------------
        # Sheet 1: Raw Data Awal
        # ----------------------------------------------------

        df_raw.to_excel(
            writer,
            sheet_name='1_Raw_Data_Awal',
            index=False
        )

        # ----------------------------------------------------
        # Sheet 2: Data Hasil Preprocessing
        # ----------------------------------------------------

        df_processed.to_excel(
            writer,
            sheet_name='2_Data_Preprocessed',
            index=False
        )

        # ----------------------------------------------------
        # Sheet 3: Perhitungan Data
        # ----------------------------------------------------

        summary_rows = []

        for col, settings in calc_settings.items():

            summary_rows.append({

                "Pertanyaan/Kolom": col,

                "Tipe": settings['type'],

                "Base Routing": settings['routing'],

                "Matriks di-input":
                    ", ".join(
                        settings['metrics']
                    )

            })

        df_summary = pd.DataFrame(
            summary_rows
        )

        df_summary.to_excel(
            writer,
            sheet_name='3_Perhitungan_Data',
            index=False
        )

    return buffer.getvalue()
```
