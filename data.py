"""
data.py — Veri Katmanı
───────────────────────
CoinGecko API, Supabase (takip listesi) ve ücretsiz piyasa bağlamı
kaynaklarıyla (Fear & Greed Index) ilgili her şey burada toplanır.
Bu modül "veri getir / veri gönder" sorumluluğunu taşır; hiçbir UI
mantığı içermez.
"""

import requests
import pandas as pd
import streamlit as st
from datetime import datetime

CG_BASE = "https://api.coingecko.com/api/v3"


def _cg_headers():
    return {
        "accept": "application/json",
        "x-cg-demo-api-key": st.secrets["CG_API_KEY"],
    }


def _sb_headers():
    key = st.secrets["SUPABASE_KEY"]
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ─── COİNGECKO — PİYASA & COIN VERİSİ ───────────────────────────

@st.cache_data(ttl=3600)
def kategorileri_getir() -> pd.DataFrame:
    try:
        r = requests.get(f"{CG_BASE}/coins/categories/list", headers=_cg_headers(), timeout=10)
        if r.status_code == 200:
            return pd.DataFrame(r.json())
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=300)
def coin_ara(sorgu: str) -> list:
    try:
        r = requests.get(f"{CG_BASE}/search", headers=_cg_headers(),
                          params={"query": sorgu}, timeout=10)
        if r.status_code == 200:
            return r.json().get("coins", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=300)
def coin_detay_getir(coin_id: str, days: int = 35):
    """Günlük fiyat + hacim geçmişi (market_chart endpoint)."""
    try:
        r = requests.get(
            f"{CG_BASE}/coins/{coin_id}/market_chart",
            headers=_cg_headers(),
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def coin_ohlc_getir(coin_id: str, days: int = 30):
    """OHLC mumları (open/high/low/close) — TradingView OBV/MACD/T-Channel
    portu (indicators.tv_obv_macd_tchannel_analiz_et) gerçek High/Low verisine
    ihtiyaç duyduğu için eklendi. coin_detay_getir ile aynı önbellekleme
    deseni (ttl=300) kullanılıyor; başarısızlıkta None döner, çağıran taraf
    (app.py) bunu T-Channel panelini atlamak için kontrol eder.

    Dönüş: [[timestamp_ms, open, high, low, close], ...] ya da None.

    NOT: CoinGecko bu uç noktada gün sayısına göre farklı mum genişliği
    döndürür — 1-2 gün: 30 dakika, 3-30 gün: 4 saat, 31+ gün: 4 gün.
    Bu yüzden market_chart'ın günlük çözünürlüğüyle birebir örtüşmez;
    hizalama indicators.ohlc_hizala() tarafından (en yakın mum eşleştirmesiyle)
    otomatik yapılır.
    """
    try:
        r = requests.get(
            f"{CG_BASE}/coins/{coin_id}/ohlc",
            headers=_cg_headers(),
            params={"vs_currency": "usd", "days": days},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def coin_bilgi_getir(coin_id: str):
    """Tek coin için anlık fiyat, market cap, hacim vb. detaylı bilgi."""
    try:
        r = requests.get(
            f"{CG_BASE}/coins/{coin_id}",
            headers=_cg_headers(),
            params={"localization": "false", "tickers": "false",
                    "community_data": "false", "developer_data": "false"},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def guncel_fiyat_getir(coin_id: str):
    """Tek coin için anlık fiyat ve 24s değişim — cache'siz (Takip Listesi sekmesi için)."""
    try:
        r = requests.get(
            f"{CG_BASE}/simple/price",
            headers=_cg_headers(),
            params={"ids": coin_id, "vs_currencies": "usd", "include_24hr_change": "true"},
            timeout=10,
        )
        if r.status_code == 200:
            d = r.json().get(coin_id, {})
            return d.get("usd", 0), d.get("usd_24h_change", 0)
    except Exception:
        pass
    return 0, 0


def piyasa_taramasi_istegi(siralama: str, sayfa_basi: int, kategori_id: str = ""):
    """Piyasa tarama listesini çeker (coins/markets). Hata durumunda
    requests.Response nesnesini olduğu gibi döndürür ki çağıran taraf
    status_code'a göre (429 / diğer) karar verebilsin."""
    params = {
        "vs_currency": "usd",
        "order":       siralama,
        "per_page":    sayfa_basi,
        "page":        1,
        "sparkline":   "false",
    }
    if kategori_id:
        params["category"] = kategori_id
    return requests.get(f"{CG_BASE}/coins/markets", headers=_cg_headers(), params=params, timeout=15)


def coin_grafik_istegi(coin_id: str, days: int = 35, retry_on_429: bool = True):
    """Tarama döngüsü için cache'siz market_chart isteği (429'da bir kez tekrar dener)."""
    import time
    r = requests.get(
        f"{CG_BASE}/coins/{coin_id}/market_chart",
        headers=_cg_headers(),
        params={"vs_currency": "usd", "days": days, "interval": "daily"},
        timeout=10,
    )
    if r.status_code == 429 and retry_on_429:
        time.sleep(8)
        r = requests.get(
            f"{CG_BASE}/coins/{coin_id}/market_chart",
            headers=_cg_headers(),
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=10,
        )
    return r


def coin_ohlc_istegi(coin_id: str, days: int = 30, retry_on_429: bool = True):
    """Tekli coin analiz sekmesi için cache'siz OHLC isteği (429'da bir kez
    tekrar dener) — coin_grafik_istegi ile aynı desen. app.py bu fonksiyonu
    kullanıp .status_code / .json() ile kontrol eder; önbellekli sürüm için
    coin_ohlc_getir() kullanılabilir."""
    import time
    r = requests.get(
        f"{CG_BASE}/coins/{coin_id}/ohlc",
        headers=_cg_headers(),
        params={"vs_currency": "usd", "days": days},
        timeout=10,
    )
    if r.status_code == 429 and retry_on_429:
        time.sleep(8)
        r = requests.get(
            f"{CG_BASE}/coins/{coin_id}/ohlc",
            headers=_cg_headers(),
            params={"vs_currency": "usd", "days": days},
            timeout=10,
        )
    return r


# ─── PİYASA BAĞLAMI (ücretsiz, ekstra maliyetsiz) ──────────────

@st.cache_data(ttl=300)
def fear_greed_getir():
    """Alternative.me Fear & Greed Index — tamamen ücretsiz, limitsiz."""
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        if r.status_code == 200:
            v = r.json()['data'][0]
            return int(v['value']), v['value_classification']
    except Exception:
        pass
    return None, None


@st.cache_data(ttl=300)
def btc_dominans_getir():
    """BTC dominansı ve global market cap 24s değişimi — CoinGecko /global."""
    try:
        r = requests.get(f"{CG_BASE}/global", headers=_cg_headers(), timeout=8)
        if r.status_code == 200:
            d = r.json().get('data', {})
            btc = d.get('market_cap_percentage', {}).get('btc')
            chg = d.get('market_cap_change_percentage_24h_usd')
            return (
                round(float(btc), 2) if btc else None,
                round(float(chg), 2) if chg else None,
            )
    except Exception:
        pass
    return None, None


# ─── SUPABASE — TAKİP LİSTESİ ────────────────────────────────────

def takip_listesi_getir() -> list:
    try:
        r = requests.get(
            f"{st.secrets['SUPABASE_URL']}/rest/v1/takip_listesi?select=*",
            headers=_sb_headers(), timeout=10,
        )
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return []


def takibe_ekle(coin_id, coin_adi, sembol, fiyat, sinyal):
    sb_url = st.secrets['SUPABASE_URL']
    try:
        kontrol = requests.get(
            f"{sb_url}/rest/v1/takip_listesi?coin_id=eq.{coin_id}",
            headers=_sb_headers(), timeout=10,
        )
        if kontrol.status_code == 200 and len(kontrol.json()) > 0:
            return False, "zaten_var"

        r = requests.post(
            f"{sb_url}/rest/v1/takip_listesi",
            headers=_sb_headers(),
            json={
                "coin_id":          coin_id,
                "coin_adi":         coin_adi,
                "sembol":           sembol,
                "baslangic_fiyat":  fiyat,
                "baslangic_sinyal": sinyal,
                "eklenme_tarihi":   datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            timeout=10,
        )
        if r.status_code in [200, 201]:
            return True, "eklendi"
        return False, r.text
    except Exception as e:
        return False, str(e)


def takipten_cikar(coin_id: str) -> bool:
    try:
        r = requests.delete(
            f"{st.secrets['SUPABASE_URL']}/rest/v1/takip_listesi?coin_id=eq.{coin_id}",
            headers=_sb_headers(), timeout=10,
        )
        return r.status_code in [200, 204]
    except Exception:
        return False
