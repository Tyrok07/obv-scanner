import streamlit as st
import pandas as pd

from styles import get_css, get_banner_html
from data import (
    get_categories, search_coin, get_coin_chart, get_coin_info,
    get_current_price, get_watchlist, add_to_watchlist, remove_from_watchlist,
    get_fear_greed, get_btc_dominance
)
from indicators import (
    calculate_obv, obv_signal, obv_balance, calculate_all_indicators
)
from ai import get_guru_comment

st.set_page_config(page_title="OBV Pro Scanner", layout="wide", page_icon="🐋")
st.markdown(get_css(), unsafe_allow_html=True)
st.markdown(get_banner_html(), unsafe_allow_html=True)

if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()
if "scan_raw" not in st.session_state:
    st.session_state.scan_raw = []
if "tab2_state" not in st.session_state:
    st.session_state.tab2_state = None

categories = get_categories()
tabs = st.tabs(["📡 Piyasa Tarama", "🔍 Coin Ara", "⭐ Takip Listesi"])

with tabs[0]:
    st.subheader("📡 Piyasa Tarama")
    st.write("OBV, hacim ve fiyat hareketlerini birlikte tarayın.")

with tabs[1]:
    st.subheader("🔍 Tek Coin OBV Analizi")
    st.write("Coin adı veya sembolü yazın, detaylı analiz görün.")

with tabs[2]:
    st.subheader("⭐ Takip Listesi")
    st.write("Takipteki coinlerin performansını izleyin.")
