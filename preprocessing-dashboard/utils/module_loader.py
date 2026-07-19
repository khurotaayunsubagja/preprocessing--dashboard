import importlib
import sys
import os
import streamlit as st

def load_analysis_modules():
    """
    Fungsi untuk memuat seluruh modul pemrosesan data secara dinamis.
    Jika ada modul yang tidak ditemukan, dashboard akan otomatis berhenti (st.stop).
    """
    # Pastikan jalur sistem mengarah ke root project folder
    sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

    modules = {}

    try:
        count_module = importlib.import_module("processing.count_processing")
        modules['count_abs'] = count_module.count_abs
        modules['count_percentage'] = count_module.count_percentage
    except ModuleNotFoundError:
        st.error("Gagal memuat modul: **processing/count_processing.py**")
        st.stop()

    try:
        avg_module = importlib.import_module("processing.average_processing")
        modules['calculate_average'] = avg_module.calculate_average
    except ModuleNotFoundError:
        st.error("Gagal memuat modul: **processing/average_processing.py**")
        st.stop()

    try:
        nps_module = importlib.import_module("processing.nps_processing")
        modules['calculate_nps'] = nps_module.calculate_nps
    except ModuleNotFoundError:
        st.error("Gagal memuat modul: **processing/nps_processing.py**")
        st.stop()

    try:
        survey_monkey_module = importlib.import_module("processing.survey_monkey")
        modules['universal_survey_monkey_processor'] = survey_monkey_module.universal_survey_monkey_processor
    except ModuleNotFoundError:
        st.error("Gagal memuat modul: **processing/survey_monkey.py**")
        st.stop()

    try:
        google_forms_module = importlib.import_module("processing.google-forms")
        modules['google_forms_processor'] = google_forms_module.google_forms_processor
    except ModuleNotFoundError:
        st.error("Gagal memuat modul: **processing/google-forms.py**")
        st.stop()

    return modules