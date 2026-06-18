import pandas as pd
import requests
import streamlit as st
from datetime import datetime

API_KEY = st.secrets["CG_API_KEY"]
BASE_URL = "https://api.coingecko.com/api/v3"
HEADERS = {"accept": "application/json", "x-cg-demo-api-key": API_KEY}

SB_URL = st.secrets["SUPABASE_URL"]
SB_KEY = st.secrets["SUPABASE_KEY"]
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation",
}

@st.cache_data(ttl=3600)
def get_categories():
    try:
        r = requests.get(f"{BASE_URL}/coins/categories/list", headers=HEADERS, timeout=10)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=300)
def search_coin(query):
    try:
        r = requests.get(f"{BASE_URL}/search", headers=HEADERS, params={"query": query}, timeout=10)
        if r.status_code == 200:
            return r.json().get("coins", [])
    except Exception:
        pass
    return []

@st.cache_data(ttl=300)
def get_coin_chart(coin_id, days=35):
    try:
        r = requests.get(
            f"{BASE_URL}/coins/{coin_id}/market_chart",
            headers=HEADERS,
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

@st.cache_data(ttl=300)
def get_coin_info(coin_id):
    try:
        r = requests.get(
            f"{BASE_URL}/coins/{coin_id}",
            headers=HEADERS,
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
            },
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

def get_current_price(coin_id):
    try:
        r = requests.get(
            f"{BASE_URL}/simple/price",
            headers=HEADERS,
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json().get(coin_id, {})
            return data.get("usd", 0), data.get("usd_24h_change", 0)
    except Exception:
        pass
    return 0, 0

def get_watchlist():
    try:
        r = requests.get(f"{SB_URL}/rest/v1/takip_listesi?select=*", headers=SB_HEADERS, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []

def add_to_watchlist(coin_id, coin_adi, sembol, fiyat, sinyal):
    try:
        check = requests.get(f"{SB_URL}/rest/v1/takip_listesi?coin_id=eq.{coin_id}", headers=SB_HEADERS, timeout=10)
        if check.status_code == 200 and check.json():
            return False, "zaten_var"
        r = requests.post(
            f"{SB_URL}/rest/v1/takip_listesi",
            headers=SB_HEADERS,
            json={
                "coin_id": coin_id,
                "coin_adi": coin_adi,
                "sembol": sembol,
                "baslangic_fiyat": fiyat,
                "baslangic_sinyal": sinyal,
                "eklenme_tarihi": datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            timeout=10,
        )
        if r.status_code in [200, 201]:
            return True, "eklendi"
        return False, r.text
    except Exception as e:
        return False, str(e)

def remove_from_watchlist(coin_id):
    try:
        r = requests.delete(f"{SB_URL}/rest/v1/takip_listesi?coin_id=eq.{coin_id}", headers=SB_HEADERS, timeout=10)
        return r.status_code in [200, 204]
    except Exception:
        return False

@st.cache_data(ttl=300)
def get_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        if r.status_code == 200:
            d = r.json()["data"][0]
            return int(d["value"]), d["value_classification"]
    except Exception:
        pass
    return None, None

@st.cache_data(ttl=300)
def get_btc_dominance():
    try:
        r = requests.get(f"{BASE_URL}/global", headers=HEADERS, timeout=8)
        if r.status_code == 200:
            data = r.json().get("data", {})
            btc = data.get("market_cap_percentage", {}).get("btc")
            change = data.get("market_cap_change_percentage_24h_usd")
            return (round(float(btc), 2) if btc else None, round(float(change), 2) if change else None)
    except Exception:
        pass
    return None, None
