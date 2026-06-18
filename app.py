import streamlit as st
import pandas as pd
import requests
import time
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from groq import Groq

# ─── SAYFA AYARLARI ─────────────────────────────────────────────
st.set_page_config(page_title="OBV Pro Scanner", layout="wide", page_icon="🐋")

st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #8dc647; }
    .stProgress > div > div > div > div { background-color: #8dc647; }
    .sinyal-banner { padding:12px 20px; border-radius:6px; font-size:20px;
                     font-weight:bold; margin:12px 0; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="big-font">🦎 CoinGecko Altyapılı Gelişmiş OBV Hacim & Balina Tarayıcı</p>',
            unsafe_allow_html=True)

# ─── API AYARLARI ───────────────────────────────────────────────
API_KEY  = st.secrets["CG_API_KEY"]
BASE_URL = "https://api.coingecko.com/api/v3"
HEADERS  = {"accept": "application/json", "x-cg-demo-api-key": API_KEY}

# ─── SUPABASE REST API (kütüphanesiz) ───────────────────────────
SB_URL = st.secrets["SUPABASE_URL"]
SB_KEY = st.secrets["SUPABASE_KEY"]
SB_HEADERS = {
    "apikey": SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}


# ─── AI GURU YORUM ALTYAPISI ────────────────────────────────────
# Bu bölüm AI'a HİÇBİR ham fiyat verisi göndermez. AI sadece, kodun
# zaten hesapladığı gerçek OBV/sinyal/yüzde değerlerini alır ve bunları
# bir teknik analist diliyle yorumlar. AI sayı üretmez, sadece üretilmiş
# sayıları açıklar/değerlendirir.

GURU_SISTEM_PROMPT = """Sen deneyimli, soğukkanlı bir kripto piyasa teknik analistisin. Lakabın "Guru".
Sana verilen veriler CoinGecko API'sinden çekilmiş gerçek fiyat ve hacim verilerinden
bu uygulama tarafından zaten hesaplanmış OBV (On-Balance Volume) metrikleridir.

KURALLARIN:
1. SADECE sana verilen sayısal verilere dayanarak yorum yap. Veride olmayan kesin fiyat
   hedefi, "X gün içinde Y olur" gibi öngörülerde ASLA bulunma. Veri dışı varsayım üretme.
2. OBV ile fiyat arasındaki uyum/uyumsuzluğun teknik anlamını açıkla (balina birikimi,
   dağıtım, sahte kırılım, hacim onaylı trend vb.).
3. Riskleri belirt ve yanıtının sonunda "Bu bir yatırım tavsiyesi değildir." ifadesini ekle.
4. Akıcı paragraflar halinde, en fazla 180 kelime, madde işareti kullanmadan yaz.
5. Veri yetersiz veya çelişkiliyse bunu açıkça söyle; sallama yapma.
"""


@st.cache_resource
def ai_istemci_al():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def ai_guru_yorumu_uret(veri_metni):
    """Uygulamanın hesapladığı gerçek verileri AI'a gönderip guru yorumu üretir."""
    client = ai_istemci_al()
    if client is None:
        return ("⚠️ AI yorumu için GROQ_API_KEY tanımlı değil. "
                "Streamlit Cloud → App settings → Secrets bölümüne eklemen gerekiyor. "
                "Ücretsiz key almak için: console.groq.com")
    try:
        yanit = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": GURU_SISTEM_PROMPT},
                {"role": "user",   "content": veri_metni},
            ],
            max_tokens=600,
            temperature=0.4,
        )
        return yanit.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI yorumu alınamadı: {e}"


# ─── OBV FONKSİYONLARI ──────────────────────────────────────────
def obv_hesapla(df):
    if len(df) < 2:
        df['OBV'] = 0
        df['OBV_Trend'] = 0
        df['OBV_EMA'] = 0
        return df
    obv = [0]
    for i in range(1, len(df)):
        fark  = df.loc[i, 'Fiyat'] - df.loc[i - 1, 'Fiyat']
        hacim = df.loc[i, 'Hacim']
        if fark > 0:
            obv.append(obv[-1] + hacim)
        elif fark < 0:
            obv.append(obv[-1] - hacim)
        else:
            obv.append(obv[-1])
    df['OBV']       = obv
    df['OBV_Trend'] = df['OBV'].rolling(window=5, min_periods=1).mean()
    df['OBV_EMA']   = df['OBV'].ewm(span=5, adjust=False).mean()
    return df


def obv_momentum_hesapla(df, periyot=5):
    if len(df) < periyot + 1:
        return 0
    payda = abs(df['OBV'].iloc[-periyot - 1]) + 1
    return (df['OBV'].iloc[-1] - df['OBV'].iloc[-periyot - 1]) / payda


def uyumsuzluk_kontrol_et(df, periyot, hassasiyet="Orta"):
    if len(df) < periyot:
        return "Yetersiz Veri"
    esik         = {"Düşük": 3.0, "Orta": 1.5, "Yüksek": 0.5}.get(hassasiyet, 1.5)
    mevcut_fiyat = df['Fiyat'].iloc[-1]
    onceki_fiyat = df['Fiyat'].iloc[-periyot]
    mevcut_obv   = df['OBV'].iloc[-1]
    onceki_obv   = df['OBV'].iloc[-periyot]
    fiyat_pct    = ((mevcut_fiyat - onceki_fiyat) / (onceki_fiyat + 1e-12)) * 100
    obv_pct      = ((mevcut_obv   - onceki_obv)   / (abs(onceki_obv) + 1))   * 100

    if fiyat_pct < -esik and obv_pct > esik:
        if obv_pct > abs(fiyat_pct) * 2:
            return "🔵 GÜÇLÜ POZİTİF (Ağır Balina Topluyor)"
        return "🔵 POZİTİF (Balina Topluyor)"
    elif fiyat_pct > esik and obv_pct < -esik:
        if abs(obv_pct) > fiyat_pct:
            return "🔴 GÜÇLÜ NEGATİF (Büyük Dağıtım)"
        return "🔴 NEGATİF (Sahte Yükseliş)"
    elif fiyat_pct > esik and obv_pct > esik:
        momentum = obv_momentum_hesapla(df, periyot)
        if momentum > 0.05:
            return "🟢 GÜÇLÜ YÜKSELİŞ (Hacim Destekli)"
        return "🟢 YÜKSELİŞ (Hacim Onaylı)"
    elif fiyat_pct < -esik and obv_pct < -esik:
        momentum = obv_momentum_hesapla(df, periyot)
        if momentum < -0.05:
            return "🔻 GÜÇLÜ DÜŞÜŞ (Hacim Destekli)"
        return "🔻 DÜŞÜŞ (Hacim Onaylı)"
    else:
        obv_trend = df['OBV_Trend'].iloc[-1] if 'OBV_Trend' in df.columns else mevcut_obv
        if mevcut_obv > obv_trend:
            return "⚪ Nötr (OBV Yükselme Eğilimli)"
        elif mevcut_obv < obv_trend:
            return "⚪ Nötr (OBV Düşme Eğilimli)"
        return "⚪ Nötr"


def obv_hacim_dengesi(df, periyot=7):
    if len(df) < periyot:
        return 0
    net_hacim    = df['OBV'].iloc[-1] - df['OBV'].iloc[-periyot]
    toplam_hacim = df['Hacim'].iloc[-periyot:].sum()
    return (net_hacim / toplam_hacim * 100) if toplam_hacim > 0 else 0


# ─── TEKNİK İNDİKATÖRLER ────────────────────────────────────────

def rsi_hesapla(df, periyot=14):
    """RSI (Relative Strength Index) hesaplar."""
    if len(df) < periyot + 1:
        return None
    delta  = df['Fiyat'].diff()
    kazan  = delta.clip(lower=0)
    kayip  = -delta.clip(upper=0)
    ort_k  = kazan.ewm(com=periyot - 1, min_periods=periyot).mean()
    ort_ka = kayip.ewm(com=periyot - 1, min_periods=periyot).mean()
    rs     = ort_k / (ort_ka + 1e-12)
    rsi    = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)


def macd_hesapla(df):
    """MACD, sinyal çizgisi ve histogram hesaplar."""
    if len(df) < 26:
        return None, None, None
    ema12    = df['Fiyat'].ewm(span=12, adjust=False).mean()
    ema26    = df['Fiyat'].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sinyal   = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - sinyal
    return (
        round(float(macd_line.iloc[-1]), 6),
        round(float(sinyal.iloc[-1]), 6),
        round(float(histogram.iloc[-1]), 6),
    )


def bollinger_hesapla(df, periyot=20, std_katsayi=2):
    """Bollinger Bands hesaplar ve fiyatın banda göre konumunu döndürür."""
    if len(df) < periyot:
        return None, None, None, None
    ort      = df['Fiyat'].rolling(window=periyot).mean()
    std      = df['Fiyat'].rolling(window=periyot).std()
    ust_band = ort + std_katsayi * std
    alt_band = ort - std_katsayi * std
    son_fiyat = df['Fiyat'].iloc[-1]
    bant_genisligi = float(ust_band.iloc[-1] - alt_band.iloc[-1])
    # %B: fiyatın band içindeki konumu (0=alt band, 1=üst band)
    yuzde_b = (son_fiyat - float(alt_band.iloc[-1])) / (bant_genisligi + 1e-12)
    return (
        round(float(ust_band.iloc[-1]), 6),
        round(float(ort.iloc[-1]), 6),
        round(float(alt_band.iloc[-1]), 6),
        round(yuzde_b, 3),
    )


def hacim_analizi(df, periyot=7):
    """Son hacmi ortalama hacimle karşılaştırır."""
    if len(df) < periyot + 1:
        return None, None
    ort_hacim  = df['Hacim'].iloc[-periyot:].mean()
    son_hacim  = df['Hacim'].iloc[-1]
    hacim_oran = son_hacim / (ort_hacim + 1e-12)
    return round(float(ort_hacim), 0), round(float(hacim_oran), 2)


def tum_indiktorleri_hesapla(df, periyot=7):
    """Tüm teknik indikatörleri tek seferde hesaplar ve dict döndürür."""
    rsi = rsi_hesapla(df)
    macd, macd_sinyal, macd_hist = macd_hesapla(df)
    bb_ust, bb_orta, bb_alt, bb_yuzde_b = bollinger_hesapla(df)
    ort_hacim, hacim_oran = hacim_analizi(df, periyot)

    # RSI yorumu
    rsi_yorum = "Veri yetersiz"
    if rsi is not None:
        if rsi >= 70:   rsi_yorum = "Aşırı Alım Bölgesi"
        elif rsi >= 60: rsi_yorum = "Güçlü Bölge"
        elif rsi >= 40: rsi_yorum = "Nötr Bölge"
        elif rsi >= 30: rsi_yorum = "Zayıf Bölge"
        else:           rsi_yorum = "Aşırı Satım Bölgesi"

    # Bollinger yorumu
    bb_yorum = "Veri yetersiz"
    if bb_yuzde_b is not None:
        if bb_yuzde_b > 1:    bb_yorum = "Üst Bandın Üzerinde (Aşırı alım)"
        elif bb_yuzde_b > 0.8: bb_yorum = "Üst Banda Yakın"
        elif bb_yuzde_b > 0.5: bb_yorum = "Orta-Üst Bölge"
        elif bb_yuzde_b > 0.2: bb_yorum = "Orta-Alt Bölge"
        elif bb_yuzde_b > 0:   bb_yorum = "Alt Banda Yakın"
        else:                   bb_yorum = "Alt Bandın Altında (Aşırı satım)"

    # MACD yorumu
    macd_yorum = "Veri yetersiz"
    if macd is not None and macd_hist is not None:
        if macd > macd_sinyal and macd_hist > 0:
            macd_yorum = "Yükseliş sinyali (MACD sinyal üzerinde, histogram pozitif)"
        elif macd < macd_sinyal and macd_hist < 0:
            macd_yorum = "Düşüş sinyali (MACD sinyal altında, histogram negatif)"
        elif macd > 0:
            macd_yorum = "Pozitif bölge ama momentum zayıflıyor"
        else:
            macd_yorum = "Negatif bölge ama momentum güçleniyor"

    return {
        "rsi": rsi, "rsi_yorum": rsi_yorum,
        "macd": macd, "macd_sinyal": macd_sinyal,
        "macd_histogram": macd_hist, "macd_yorum": macd_yorum,
        "bb_ust": bb_ust, "bb_orta": bb_orta, "bb_alt": bb_alt,
        "bb_yuzde_b": bb_yuzde_b, "bb_yorum": bb_yorum,
        "ort_hacim": ort_hacim, "hacim_oran": hacim_oran,
    }


# ─── EKSTRA PİYASA VERİSİ ───────────────────────────────────────

@st.cache_data(ttl=300)
def fear_greed_getir():
    """Alternative.me Fear & Greed Index — tamamen ücretsiz API."""
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=8)
        if res.status_code == 200:
            veri = res.json()['data'][0]
            return int(veri['value']), veri['value_classification']
    except Exception:
        pass
    return None, None


@st.cache_data(ttl=300)
def btc_dominans_getir():
    """BTC dominansı ve global market cap değişimi — CoinGecko."""
    try:
        res = requests.get(f"{BASE_URL}/global", headers=HEADERS, timeout=8)
        if res.status_code == 200:
            data = res.json().get('data', {})
            btc_dom = data.get('market_cap_percentage', {}).get('btc', None)
            mcap_degisim = data.get('market_cap_change_percentage_24h_usd', None)
            return (
                round(float(btc_dom), 2) if btc_dom else None,
                round(float(mcap_degisim), 2) if mcap_degisim else None,
            )
    except Exception:
        pass
    return None, None



@st.cache_data(ttl=3600)
def kategorileri_getir():
    try:
        res = requests.get(f"{BASE_URL}/coins/categories/list", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
    except Exception:
        pass
    return pd.DataFrame()


@st.cache_data(ttl=300)
def coin_ara(sorgu):
    try:
        res = requests.get(f"{BASE_URL}/search", headers=HEADERS,
                           params={"query": sorgu}, timeout=10)
        if res.status_code == 200:
            return res.json().get("coins", [])
    except Exception:
        pass
    return []


@st.cache_data(ttl=300)
def coin_detay_getir(coin_id, days=35):
    try:
        res = requests.get(
            f"{BASE_URL}/coins/{coin_id}/market_chart",
            headers=HEADERS,
            params={"vs_currency": "usd", "days": days, "interval": "daily"},
            timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=300)
def coin_bilgi_getir(coin_id):
    try:
        res = requests.get(
            f"{BASE_URL}/coins/{coin_id}",
            headers=HEADERS,
            params={"localization": "false", "tickers": "false",
                    "community_data": "false", "developer_data": "false"},
            timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None


def guncel_fiyat_getir(coin_id):
    """Tek coin için anlık fiyat çeker"""
    try:
        res = requests.get(
            f"{BASE_URL}/simple/price",
            headers=HEADERS,
            params={"ids": coin_id, "vs_currencies": "usd",
                    "include_24hr_change": "true"},
            timeout=10
        )
        if res.status_code == 200:
            data = res.json().get(coin_id, {})
            return data.get("usd", 0), data.get("usd_24h_change", 0)
    except Exception:
        pass
    return 0, 0


# ─── SUPABASE TAKİP FONKSİYONLARI ──────────────────────────────
def takip_listesi_getir():
    try:
        res = requests.get(
            f"{SB_URL}/rest/v1/takip_listesi?select=*",
            headers=SB_HEADERS, timeout=10
        )
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


def takibe_ekle(coin_id, coin_adi, sembol, fiyat, sinyal):
    try:
        # Zaten takipte mi?
        kontrol = requests.get(
            f"{SB_URL}/rest/v1/takip_listesi?coin_id=eq.{coin_id}",
            headers=SB_HEADERS, timeout=10
        )
        if kontrol.status_code == 200 and len(kontrol.json()) > 0:
            return False, "zaten_var"

        res = requests.post(
            f"{SB_URL}/rest/v1/takip_listesi",
            headers=SB_HEADERS,
            json={
                "coin_id":          coin_id,
                "coin_adi":         coin_adi,
                "sembol":           sembol,
                "baslangic_fiyat":  fiyat,
                "baslangic_sinyal": sinyal,
                "eklenme_tarihi":   datetime.now().strftime("%Y-%m-%d %H:%M"),
            },
            timeout=10
        )
        if res.status_code in [200, 201]:
            return True, "eklendi"
        return False, res.text
    except Exception as e:
        return False, str(e)


def takipten_cikar(coin_id):
    try:
        res = requests.delete(
            f"{SB_URL}/rest/v1/takip_listesi?coin_id=eq.{coin_id}",
            headers=SB_HEADERS, timeout=10
        )
        return res.status_code in [200, 204]
    except Exception:
        return False


# ─── PLOTLY GRAFİK ──────────────────────────────────────────────
def obv_grafigi_ciz(df_coin, coin_adi, sinyal):
    sinyal_renk = "#607D8B"
    if "POZİTİF" in sinyal:   sinyal_renk = "#2196F3"
    elif "NEGATİF" in sinyal: sinyal_renk = "#F44336"
    elif "YÜKSELİŞ" in sinyal: sinyal_renk = "#4CAF50"
    elif "DÜŞÜŞ" in sinyal:   sinyal_renk = "#FF9800"

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("📈 Fiyat (USD)", "📊 OBV (On-Balance Volume)"),
        row_heights=[0.55, 0.45]
    )
    tarihler = list(range(len(df_coin)))

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['Fiyat'], mode='lines', name='Fiyat',
        line=dict(color='#00BCD4', width=2),
        fill='tozeroy', fillcolor='rgba(0,188,212,0.08)',
        hovertemplate='Gün %{x}<br>Fiyat: $%{y:,.6f}<extra></extra>'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['OBV'], mode='lines', name='OBV',
        line=dict(color=sinyal_renk, width=2),
        hovertemplate='Gün %{x}<br>OBV: %{y:,.0f}<extra></extra>'
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['OBV_EMA'], mode='lines', name='OBV EMA(5)',
        line=dict(color='rgba(255,193,7,0.8)', width=1.5, dash='dot'),
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['OBV_Trend'], mode='lines', name='OBV MA(5)',
        line=dict(color='rgba(255,255,255,0.4)', width=1, dash='dash'),
    ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"{coin_adi} — OBV Analizi", font=dict(size=16)),
        paper_bgcolor='rgba(14,17,23,1)', plot_bgcolor='rgba(14,17,23,1)',
        font=dict(color='#FAFAFA'), height=600, hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.07)'),
        xaxis2=dict(showgrid=True, gridcolor='rgba(255,255,255,0.07)', title='Gün'),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.07)'),
        yaxis2=dict(showgrid=True, gridcolor='rgba(255,255,255,0.07)'),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig


def renklendir_sinyal(val):
    if "POZİTİF" in str(val):   return 'background-color: #1a3a2a; color: #90EE90'
    elif "NEGATİF" in str(val): return 'background-color: #3a1a1a; color: #FF8A80'
    elif "YÜKSELİŞ" in str(val): return 'background-color: #1a2a1a; color: #A5D6A7'
    elif "DÜŞÜŞ" in str(val):   return 'background-color: #2a2a1a; color: #FFE082'
    return ''


# ─── SIDEBAR ────────────────────────────────────────────────────
df_kategoriler = kategorileri_getir()

st.sidebar.header("🎛️ Filtreleme ve Piyasa Ayarları")

siralam_secimi = st.sidebar.selectbox(
    "Sıralama Esası",
    ["Market Cap (Büyükten Küçüğe)", "Market Cap (Küçükten Büyüğe)", "24 Saatlik Hacim Yüksekten Düşüğe"]
)
siralam_map = {
    "Market Cap (Büyükten Küçüğe)":      "market_cap_desc",
    "Market Cap (Küçükten Büyüğe)":      "market_cap_asc",
    "24 Saatlik Hacim Yüksekten Düşüğe": "volume_desc",
}

kategori_opsiyonlari = ["Tüm Kripto Dünyası"]
if not df_kategoriler.empty and 'name' in df_kategoriler.columns:
    kategori_opsiyonlari.extend(df_kategoriler['name'].tolist())

secilen_kategori_adi = st.sidebar.selectbox("Kategori / Sektör Seçin", kategori_opsiyonlari)
secilen_kategori_id  = ""
if secilen_kategori_adi != "Tüm Kripto Dünyası" and not df_kategoriler.empty:
    eslesen = df_kategoriler[df_kategoriler['name'] == secilen_kategori_adi]
    if not eslesen.empty:
        secilen_kategori_id = eslesen['category_id'].values[0]

st.sidebar.markdown("---")
tarama_sayisi   = st.sidebar.number_input("Kaç coin taransın?", min_value=5, max_value=250, value=50, step=5)
analiz_periyodu = st.sidebar.slider("OBV Kaç Günlük Trende Baksın?", 3, 30, 7, step=1)
obv_hassasiyet  = st.sidebar.select_slider(
    "OBV Hassasiyeti", options=["Düşük", "Orta", "Yüksek"], value="Orta",
    help="Düşük = sadece güçlü sinyaller | Yüksek = daha fazla sinyal üretir"
)
tarama_butonu = st.sidebar.button("Piyasayı Canlı Tara 🚀", use_container_width=True)


# ─── SESSION STATE ──────────────────────────────────────────────
if 'tarama_ham' not in st.session_state:
    st.session_state['tarama_ham'] = []
if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = pd.DataFrame()
if 'tab2_analiz' not in st.session_state:
    st.session_state['tab2_analiz'] = None

# ─── ANA SEKMELER ───────────────────────────────────────────────
sekme1, sekme2, sekme3 = st.tabs(["📡 Piyasa Tarama", "🔍 Coin Ara", "⭐ Takip Listesi"])


# ════════════════════════════════════════════════════════════════
# SEKME 1 — PİYASA TARAMA
# ════════════════════════════════════════════════════════════════
with sekme1:
    st.write("Fiyat hareketlerini gerçek hacim trendleriyle doğrulayarak balina akümülasyonunu kategorilere göre filtreleyin.")

    if tarama_butonu:
        st.info("🔄 Coin listesi CoinGecko'dan çekiliyor...")

        params = {
            "vs_currency": "usd",
            "order":       siralam_map.get(siralam_secimi, "market_cap_desc"),
            "per_page":    tarama_sayisi,
            "page":        1,
            "sparkline":   "false",
        }
        if secilen_kategori_id:
            params["category"] = secilen_kategori_id

        try:
            res = requests.get(f"{BASE_URL}/coins/markets", headers=HEADERS, params=params, timeout=15)
            if res.status_code == 429:
                st.error("⚠️ API hız limiti aşıldı. Birkaç dakika sonra tekrar deneyin.")
                st.stop()
            elif res.status_code != 200:
                st.error(f"Veri çekme hatası. Kod: {res.status_code}")
                st.stop()
            coin_listesi = res.json()
        except Exception as e:
            st.error(f"Bağlantı hatası: {e}")
            st.stop()

        if not coin_listesi:
            st.warning("Seçilen kategoride eşleşen coin bulunamadı.")
            st.stop()

        sonuc_tablosu = []
        st.session_state['tarama_ham'] = []
        progres_bari  = st.progress(0)
        durum_yazisi  = st.empty()

        for indeks, coin in enumerate(coin_listesi):
            coin_id          = coin['id']
            coin_name        = coin['name']
            coin_symbol      = coin['symbol'].upper()
            current_price    = coin.get('current_price', 0)
            market_cap       = coin.get('market_cap', 0)
            hacim_24h        = coin.get('total_volume', 0)
            price_change_24h = coin.get('price_change_percentage_24h', 0)

            durum_yazisi.text(f"📡 Analiz ediliyor: {coin_name} ({indeks + 1}/{len(coin_listesi)})")

            try:
                chart_res = requests.get(
                    f"{BASE_URL}/coins/{coin_id}/market_chart",
                    headers=HEADERS,
                    params={"vs_currency": "usd", "days": 35, "interval": "daily"},
                    timeout=10
                )
                if chart_res.status_code == 429:
                    time.sleep(8)
                    chart_res = requests.get(
                        f"{BASE_URL}/coins/{coin_id}/market_chart",
                        headers=HEADERS,
                        params={"vs_currency": "usd", "days": 35, "interval": "daily"},
                        timeout=10
                    )

                if chart_res.status_code == 200:
                    chart_data = chart_res.json()
                    fiyatlar   = [o[1] for o in chart_data.get('prices', [])]
                    hacimler   = [o[1] for o in chart_data.get('total_volumes', [])]

                    if fiyatlar and hacimler:
                        df_coin     = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                        df_coin     = obv_hesapla(df_coin)
                        sinyal      = uyumsuzluk_kontrol_et(df_coin, analiz_periyodu, obv_hassasiyet)
                        obv_dengesi = obv_hacim_dengesi(df_coin, analiz_periyodu)

                        sonuc_tablosu.append({
                            "Coin Adı":       f"https://www.coingecko.com/en/coins/{coin_id}",
                            "Coin Adı Metin": coin_name,
                            "Sembol":         coin_symbol,
                            "Fiyat ($)":      current_price,
                            "24s Değişim %":  price_change_24h,
                            "Market Cap ($)": market_cap,
                            "24s Hacim ($)":  hacim_24h,
                            "OBV Dengesi %":  round(obv_dengesi, 2),
                            "OBV Sinyali":    sinyal,
                        })
                        st.session_state['tarama_ham'].append({
                            "coin_id": coin_id, "coin_adi": coin_name,
                            "sembol": coin_symbol, "fiyat": current_price, "sinyal": sinyal
                        })
            except Exception:
                continue

            time.sleep(1.5)
            progres_bari.progress((indeks + 1) / len(coin_listesi))

        durum_yazisi.empty()
        df_sonuc = pd.DataFrame(sonuc_tablosu)
        st.session_state['df_sonuc'] = df_sonuc

    # Tarama sonuçlarını session state'den göster
    df_sonuc = st.session_state['df_sonuc']

    if not df_sonuc.empty:
        st.success(f"📊 {len(df_sonuc)} coin OBV süzgecinden geçirildi!")

        pozitif        = df_sonuc[df_sonuc['OBV Sinyali'].str.contains("POZİTİF", na=False)]
        negatif        = df_sonuc[df_sonuc['OBV Sinyali'].str.contains("NEGATİF", na=False)]
        hacim_destekli = df_sonuc[df_sonuc['OBV Sinyali'].str.contains("YÜKSELİŞ", na=False)]

        c1, c2, c3 = st.columns(3)
        c1.metric("🐋 Balina Toplayan Coin",    len(pozitif))
        c2.metric("🚨 Riskli / Şişen Coin",     len(negatif))
        c3.metric("📈 Hacim Destekli Yükseliş", len(hacim_destekli))

        st.markdown("---")
        link_config = {
            "Coin Adı Metin": st.column_config.TextColumn("Coin Adı"),
            "Coin Adı":       st.column_config.LinkColumn("🔗 CG", display_text="🔗"),
        }

        col_sol, col_orta, col_sag = st.columns(3)
        with col_sol:
            st.markdown("### 🔵 Potansiyel Alım Fırsatları")
            if not pozitif.empty:
                st.dataframe(
                    pozitif[["Coin Adı Metin","Coin Adı","Sembol","Fiyat ($)","OBV Dengesi %","24s Hacim ($)"]],
                    column_config=link_config, use_container_width=True, hide_index=True,
                )
        with col_orta:
            st.markdown("### 🟢 Hacim Destekli Yükseliş")
            if not hacim_destekli.empty:
                st.dataframe(
                    hacim_destekli[["Coin Adı Metin","Coin Adı","Sembol","24s Değişim %","OBV Dengesi %","24s Hacim ($)"]],
                    column_config=link_config, use_container_width=True, hide_index=True,
                )
        with col_sag:
            st.markdown("### 🔴 Potansiyel Satış / Kar Al Bölgeleri")
            if not negatif.empty:
                st.dataframe(
                    negatif[["Coin Adı Metin","Coin Adı","Sembol","Fiyat ($)","OBV Dengesi %","24s Hacim ($)"]],
                    column_config=link_config, use_container_width=True, hide_index=True,
                )

        st.markdown("---")
        st.subheader("📋 Tüm Piyasa Tablosu")
        st.dataframe(
            df_sonuc.style.format({
                "Fiyat ($)": "{:,.4f}", "Market Cap ($)": "{:,.0f}",
                "24s Hacim ($)": "{:,.0f}", "OBV Dengesi %": "{:,.2f}",
                "24s Değişim %": "{:,.2f}",
            }).map(renklendir_sinyal, subset=['OBV Sinyali']),
            column_config=link_config, use_container_width=True, hide_index=True,
        )

        # ─── TAKİBE AL BÖLÜMÜ ────────────────────────────────
        st.markdown("---")
        st.subheader("⭐ Takibe Al")
        st.write("Sinyal veren coinleri takip listene ekle, günler içindeki performansını izle.")

        sinyal_verenler = [c for c in st.session_state['tarama_ham'] 
                           if "Nötr" not in c['sinyal'] and "Yetersiz" not in c['sinyal']]

        if sinyal_verenler:
            secenekler = {f"{c['coin_adi']} ({c['sembol']}) — {c['sinyal']}": c for c in sinyal_verenler}
            secilen_coin_str = st.selectbox("Takibe almak istediğin coin:", list(secenekler.keys()))
            secilen_coin_data = secenekler[secilen_coin_str]

            if st.button("➕ Takip Listesine Ekle", use_container_width=False):
                basari, mesaj = takibe_ekle(
                    secilen_coin_data['coin_id'],
                    secilen_coin_data['coin_adi'],
                    secilen_coin_data['sembol'],
                    secilen_coin_data['fiyat'],
                    secilen_coin_data['sinyal'],
                )
                if basari:
                    st.success(f"✅ {secilen_coin_data['coin_adi']} takip listesine eklendi!")
                    st.balloons()
                elif mesaj == "zaten_var":
                    st.info(f"ℹ️ {secilen_coin_data['coin_adi']} zaten takip listende.")
                else:
                    st.error(f"Hata: {mesaj}")
        else:
            st.info("Sinyal veren coin bulunamadı. Taramayı tekrar çalıştırın.")

        # İstatistiksel özet
        st.markdown("---")
        st.subheader("📈 OBV İstatistiksel Özeti")
        pozitif_obv = df_sonuc[df_sonuc['OBV Dengesi %'] > 0]
        negatif_obv = df_sonuc[df_sonuc['OBV Dengesi %'] < 0]
        col_a, col_b = st.columns(2)
        col_a.metric("🟢 Pozitif OBV Dengesi", len(pozitif_obv),
                     delta=f"%{pozitif_obv['OBV Dengesi %'].mean():.1f}" if not pozitif_obv.empty else "0")
        col_b.metric("🔴 Negatif OBV Dengesi", len(negatif_obv),
                     delta=f"%{negatif_obv['OBV Dengesi %'].mean():.1f}" if not negatif_obv.empty else "0")

        # ─── AI GURU PİYASA YORUMU ──────────────────────────────
        st.markdown("---")
        st.subheader("🧠 AI Guru — Piyasa Durum Tespiti")
        st.caption("Yorum, yukarıdaki tabloda hesaplanan gerçek OBV ve fiyat verilerine dayanır; "
                   "AI rastgele tahmin üretmez.")

        if st.button("🔮 AI Piyasa Yorumu Oluştur", use_container_width=False):
            with st.spinner("🧠 Guru veriyi inceliyor..."):
                top_pozitif = pozitif.sort_values("OBV Dengesi %", ascending=False).head(5)
                top_negatif = negatif.sort_values("OBV Dengesi %", ascending=True).head(5)

                veri_metni = f"""Taranan toplam coin sayısı: {len(df_sonuc)}
Balina birikim sinyali (POZİTİF) veren coin sayısı: {len(pozitif)}
Dağıtım/riskli sinyal (NEGATİF) veren coin sayısı: {len(negatif)}
Hacim destekli yükselişte olan coin sayısı: {len(hacim_destekli)}
Tüm coinlerin ortalama OBV Dengesi: {df_sonuc['OBV Dengesi %'].mean():.2f}%
Analiz periyodu: {analiz_periyodu} gün, hassasiyet ayarı: {obv_hassasiyet}

En güçlü pozitif (balina toplama) sinyali veren coinler (Coin, Sembol, 24s Değişim%, OBV Dengesi%):
{top_pozitif[['Coin Adı Metin','Sembol','24s Değişim %','OBV Dengesi %']].to_string(index=False) if not top_pozitif.empty else 'Yok'}

En güçlü negatif (dağıtım) sinyali veren coinler (Coin, Sembol, 24s Değişim%, OBV Dengesi%):
{top_negatif[['Coin Adı Metin','Sembol','24s Değişim %','OBV Dengesi %']].to_string(index=False) if not top_negatif.empty else 'Yok'}

Bu verilere dayanarak genel piyasa durumunu (balina davranışı, risk seviyesi, dikkat edilmesi
gereken noktalar) bir guru gibi değerlendir."""

                yorum = ai_guru_yorumu_uret(veri_metni)

            st.markdown(
                f'<div style="background:#8dc64722; border-left:4px solid #8dc647; '
                f'padding:16px 20px; border-radius:6px; line-height:1.6;">{yorum}</div>',
                unsafe_allow_html=True
            )


# ════════════════════════════════════════════════════════════════
# SEKME 2 — COİN ARA
# ════════════════════════════════════════════════════════════════
with sekme2:
    st.subheader("🔍 Tek Coin OBV Analizi")
    st.write("Coin adı veya sembolü yazın, detaylı OBV grafiği ve sinyal görün.")

    col_ara, col_gun = st.columns([3, 1])
    with col_ara:
        arama_metni = st.text_input("Coin Ara", placeholder="Bitcoin, ETH, SOL, VIRTUAL...")
    with col_gun:
        grafik_gun = st.selectbox("Gün Aralığı", [7, 14, 30, 60, 90], index=2)

    if arama_metni:
        with st.spinner("🔎 Aranıyor..."):
            sonuclar = coin_ara(arama_metni)

        if not sonuclar:
            st.warning("Sonuç bulunamadı.")
        else:
            secenekler = {f"{c['name']} ({c['symbol'].upper()})": c['id'] for c in sonuclar[:8]}
            secilen    = st.selectbox("Sonuçlar:", list(secenekler.keys()))
            secilen_id = secenekler[secilen]

            if st.button("📊 Analiz Et"):
                with st.spinner("📡 Veri çekiliyor..."):
                    chart_data = coin_detay_getir(secilen_id, grafik_gun)
                    coin_bilgi = coin_bilgi_getir(secilen_id)

                if not chart_data:
                    st.error("Veri çekilemedi.")
                    st.session_state['tab2_analiz'] = None
                else:
                    fiyatlar = [o[1] for o in chart_data.get('prices', [])]
                    hacimler = [o[1] for o in chart_data.get('total_volumes', [])]
                    df_coin     = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                    df_coin     = obv_hesapla(df_coin)
                    periyot     = min(analiz_periyodu, len(df_coin) - 1)
                    sinyal      = uyumsuzluk_kontrol_et(df_coin, periyot, obv_hassasiyet)
                    obv_dengesi = obv_hacim_dengesi(df_coin, periyot)

                    # ── Yeni: Tüm teknik indikatörleri hesapla ──
                    indiktorler = tum_indiktorleri_hesapla(df_coin, periyot)

                    # ── Yeni: Piyasa bağlamı verisi ──
                    fg_deger, fg_yorum = fear_greed_getir()
                    btc_dom, mcap_degisim = btc_dominans_getir()

                    st.session_state['tab2_analiz'] = {
                        "secilen_id":    secilen_id,
                        "secilen":       secilen,
                        "df_coin":       df_coin,
                        "sinyal":        sinyal,
                        "coin_bilgi":    coin_bilgi,
                        "obv_dengesi":   obv_dengesi,
                        "periyot":       periyot,
                        "indiktorler":   indiktorler,
                        "fg_deger":      fg_deger,
                        "fg_yorum":      fg_yorum,
                        "btc_dom":       btc_dom,
                        "mcap_degisim":  mcap_degisim,
                    }

            # ─── KAYITLI ANALİZİ GÖSTER (seçili coin'e aitse) ────────────
            analiz = st.session_state.get('tab2_analiz')
            if analiz and analiz.get("secilen_id") == secilen_id:
                df_coin     = analiz["df_coin"]
                sinyal      = analiz["sinyal"]
                coin_bilgi  = analiz["coin_bilgi"]
                obv_dengesi = analiz["obv_dengesi"]
                secilen_lbl = analiz["secilen"]
                indiktorler = analiz.get("indiktorler", {})
                fg_deger    = analiz.get("fg_deger")
                fg_yorum    = analiz.get("fg_yorum")
                btc_dom     = analiz.get("btc_dom")
                mcap_degisim = analiz.get("mcap_degisim")

                mevcut_fiyat = degisim_24h = market_cap = hacim_24h = 0
                if coin_bilgi:
                    mevcut_fiyat = coin_bilgi.get('market_data', {}).get('current_price', {}).get('usd', 0)
                    degisim_24h  = coin_bilgi.get('market_data', {}).get('price_change_percentage_24h', 0)
                    market_cap   = coin_bilgi.get('market_data', {}).get('market_cap', {}).get('usd', 0)
                    hacim_24h    = coin_bilgi.get('market_data', {}).get('total_volume', {}).get('usd', 0)

                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("💰 Fiyat", f"${mevcut_fiyat:,.6f}", delta=f"%{degisim_24h:.2f}")
                    k2.metric("📊 Market Cap", f"${market_cap:,.0f}")
                    k3.metric("💧 24s Hacim", f"${hacim_24h:,.0f}")
                    k4.metric("🔗 CoinGecko", "→", help=f"https://www.coingecko.com/en/coins/{secilen_id}")
                    st.markdown(f"[🔗 CoinGecko'da Görüntüle](https://www.coingecko.com/en/coins/{secilen_id})")

                # Sinyal banner
                sinyal_renk_map = {"POZİTİF": "#2196F3", "NEGATİF": "#F44336",
                                   "YÜKSELİŞ": "#4CAF50", "DÜŞÜŞ": "#FF9800"}
                banner_renk = "#607D8B"
                for k, v in sinyal_renk_map.items():
                    if k in sinyal:
                        banner_renk = v
                        break

                st.markdown(
                    f'<div style="background:{banner_renk}22; border-left:4px solid {banner_renk};'
                    f'padding:12px 20px; border-radius:6px; font-size:20px; font-weight:bold;'
                    f'color:{banner_renk}; margin:12px 0">{sinyal}</div>',
                    unsafe_allow_html=True
                )

                st.plotly_chart(obv_grafigi_ciz(df_coin, secilen_lbl, sinyal), use_container_width=True)

                # ─── TEKNİK İNDİKATÖR PANELİ ─────────────────────
                st.markdown("---")
                st.subheader("📐 Teknik İndikatörler")
                i1, i2, i3, i4 = st.columns(4)

                rsi_val = indiktorler.get('rsi')
                rsi_renk = "#4CAF50" if rsi_val and rsi_val < 30 else "#F44336" if rsi_val and rsi_val > 70 else "#FAFAFA"
                i1.metric("RSI (14)", f"{rsi_val}" if rsi_val else "—",
                          delta=indiktorler.get('rsi_yorum', ''))

                macd_val  = indiktorler.get('macd')
                macd_hist = indiktorler.get('macd_histogram')
                i2.metric("MACD", f"{macd_val:.6f}" if macd_val else "—",
                          delta="▲ Pozitif" if macd_hist and macd_hist > 0 else "▼ Negatif" if macd_hist else "")

                bb_yb = indiktorler.get('bb_yuzde_b')
                i3.metric("Bollinger %B", f"{bb_yb:.2f}" if bb_yb is not None else "—",
                          delta=indiktorler.get('bb_yorum', ''))

                hr = indiktorler.get('hacim_oran')
                i4.metric("Hacim/Ort.", f"{hr:.2f}x" if hr else "—",
                          delta="🔥 Yüksek hacim" if hr and hr > 1.5 else "📉 Düşük hacim" if hr and hr < 0.7 else "Normal")

                # Piyasa bağlamı
                if fg_deger or btc_dom:
                    p1, p2 = st.columns(2)
                    if fg_deger:
                        p1.metric("😨 Fear & Greed", f"{fg_deger} — {fg_yorum}")
                    if btc_dom:
                        p2.metric("₿ BTC Dominansı", f"%{btc_dom}",
                                  delta=f"Global MC 24s: %{mcap_degisim:.2f}" if mcap_degisim else "")

                # Takibe al butonu
                st.markdown("---")
                coin_adi_str = secilen_lbl.split(" (")[0]
                coin_sym_str = secilen_lbl.split("(")[1].replace(")", "")
                fiyat_str    = mevcut_fiyat

                if st.button("⭐ Takip Listesine Ekle", use_container_width=False):
                    basari, mesaj = takibe_ekle(secilen_id, coin_adi_str, coin_sym_str, fiyat_str, sinyal)
                    if basari:
                        st.success(f"✅ {coin_adi_str} takip listesine eklendi!")
                        st.balloons()
                    elif mesaj == "zaten_var":
                        st.info("ℹ️ Bu coin zaten takip listende.")
                    else:
                        st.error(f"Hata: {mesaj}")

                # OBV İstatistikleri
                s1, s2, s3 = st.columns(3)
                s1.metric("OBV Dengesi %", f"{obv_dengesi:.2f}%")
                s2.metric("Son OBV", f"{df_coin['OBV'].iloc[-1]:,.0f}")
                s3.metric("OBV Trendi",
                          "📈 Yükseliyor" if df_coin['OBV'].iloc[-1] > df_coin['OBV_Trend'].iloc[-1] else "📉 Düşüyor")

                # ─── AI GURU COIN YORUMU ──────────────────────────
                st.markdown("---")
                st.subheader("🧠 AI Guru — Bu Coin İçin Durum Tespiti")
                st.caption("Yorum; OBV, RSI, MACD, Bollinger, hacim ve piyasa bağlamı verilerine dayanır.")

                if st.button("🔮 AI Yorumu Al", key=f"ai_coin_{secilen_id}"):
                    with st.spinner("🧠 Guru tüm indikatörleri işliyor..."):

                        rsi         = indiktorler.get('rsi', 'N/A')
                        rsi_y       = indiktorler.get('rsi_yorum', 'N/A')
                        macd_v      = indiktorler.get('macd', 'N/A')
                        macd_s      = indiktorler.get('macd_sinyal', 'N/A')
                        macd_h      = indiktorler.get('macd_histogram', 'N/A')
                        macd_y      = indiktorler.get('macd_yorum', 'N/A')
                        bb_u        = indiktorler.get('bb_ust', 'N/A')
                        bb_o        = indiktorler.get('bb_orta', 'N/A')
                        bb_a        = indiktorler.get('bb_alt', 'N/A')
                        bb_y        = indiktorler.get('bb_yuzde_b', 'N/A')
                        bb_yo       = indiktorler.get('bb_yorum', 'N/A')
                        h_oran      = indiktorler.get('hacim_oran', 'N/A')
                        obv_trend_y = "yükseliyor" if df_coin['OBV'].iloc[-1] > df_coin['OBV_Trend'].iloc[-1] else "düşüyor"

                        veri_metni = f"""=== KOİN BİLGİSİ ===
Coin: {coin_adi_str} ({coin_sym_str})
Güncel fiyat: ${mevcut_fiyat:,.6f}
24 saatlik fiyat değişimi: %{degisim_24h:.2f}
Market Cap: ${market_cap:,.0f}
24 saatlik işlem hacmi: ${hacim_24h:,.0f}

=== OBV ANALİZİ ===
OBV Sinyali: {sinyal}
OBV Dengesi ({analiz['periyot']} gün): %{obv_dengesi:.2f}
OBV Trendi: {obv_trend_y}

=== TEKNİK İNDİKATÖRLER ===
RSI (14): {rsi} — {rsi_y}
MACD: {macd_v} | Sinyal: {macd_s} | Histogram: {macd_h}
MACD Durumu: {macd_y}
Bollinger Üst Band: {bb_u} | Orta: {bb_o} | Alt: {bb_a}
Bollinger %B: {bb_y} — {bb_yo}
Son Hacim / Ortalama Hacim: {h_oran}x

=== PİYASA BAĞLAMI ===
Fear & Greed Index: {fg_deger if fg_deger else 'N/A'} ({fg_yorum if fg_yorum else 'N/A'})
BTC Dominansı: %{btc_dom if btc_dom else 'N/A'}
Global Market Cap 24s Değişim: %{mcap_degisim if mcap_degisim else 'N/A'}

Tüm bu verileri birlikte yorumlayarak kapsamlı bir teknik analiz durum tespiti yap.
OBV, RSI, MACD ve Bollinger sinyallerinin birbirini teyit edip etmediğini özellikle belirt."""

                        yorum = ai_guru_yorumu_uret(veri_metni)

                    st.markdown(
                        f'<div style="background:{banner_renk}15; border-left:4px solid {banner_renk}; '
                        f'padding:16px 20px; border-radius:6px; line-height:1.7;">{yorum}</div>',
                        unsafe_allow_html=True
                    )


# ════════════════════════════════════════════════════════════════
# SEKME 3 — TAKİP LİSTESİ
# ════════════════════════════════════════════════════════════════
with sekme3:
    st.subheader("⭐ Takip Listesi")
    st.write("Takipteki coinlerin başlangıç sinyali ve fiyatına göre performansını izle.")

    col_yenile, col_bos = st.columns([1, 4])
    with col_yenile:
        yenile_butonu = st.button("🔄 Listeyi Güncelle", use_container_width=True)

    takip_verisi = takip_listesi_getir()

    if not takip_verisi:
        st.info("Henüz takip listene coin eklemedin. Tarama veya Coin Ara sekmesinden ekleyebilirsin.")
    else:
        st.success(f"📋 {len(takip_verisi)} coin takip ediliyor.")

        tablo_satirlari = []

        with st.spinner("📡 Güncel fiyatlar çekiliyor..."):
            for kayit in takip_verisi:
                coin_id         = kayit['coin_id']
                baslangic_fiyat = kayit.get('baslangic_fiyat', 0) or 0
                guncel_fiyat, degisim_24h = guncel_fiyat_getir(coin_id)

                # Performans hesapla
                if baslangic_fiyat > 0 and guncel_fiyat > 0:
                    performans = ((guncel_fiyat - baslangic_fiyat) / baslangic_fiyat) * 100
                else:
                    performans = 0

                # Güncel OBV sinyali
                chart_data = coin_detay_getir(coin_id, 35)
                guncel_sinyal = "—"
                if chart_data:
                    fiyatlar = [o[1] for o in chart_data.get('prices', [])]
                    hacimler = [o[1] for o in chart_data.get('total_volumes', [])]
                    if fiyatlar and hacimler:
                        df_c = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                        df_c = obv_hesapla(df_c)
                        guncel_sinyal = uyumsuzluk_kontrol_et(df_c, analiz_periyodu, obv_hassasiyet)

                # Sinyal değişti mi?
                baslangic_sinyal = kayit.get('baslangic_sinyal', '')
                sinyal_durumu = "✅ Aynı" if baslangic_sinyal == guncel_sinyal else "🔄 Değişti"

                tablo_satirlari.append({
                    "Coin":              kayit.get('coin_adi', ''),
                    "Sembol":            kayit.get('sembol', ''),
                    "Eklenme":           kayit.get('eklenme_tarihi', ''),
                    "Başlangıç Fiyat":   baslangic_fiyat,
                    "Güncel Fiyat":      guncel_fiyat,
                    "Performans %":      round(performans, 2),
                    "24s Değişim %":     round(degisim_24h, 2),
                    "Başlangıç Sinyali": baslangic_sinyal,
                    "Güncel Sinyal":     guncel_sinyal,
                    "Sinyal Durumu":     sinyal_durumu,
                    "_coin_id":          coin_id,
                })

                time.sleep(0.5)

        if tablo_satirlari:
            df_takip = pd.DataFrame(tablo_satirlari)

            # Renklendirme
            def renklendir_performans(val):
                try:
                    v = float(val)
                    if v > 5:    return 'background-color: #1a3a2a; color: #90EE90'
                    elif v > 0:  return 'background-color: #1a2a1a; color: #A5D6A7'
                    elif v > -5: return 'background-color: #2a2a1a; color: #FFE082'
                    else:        return 'background-color: #3a1a1a; color: #FF8A80'
                except:
                    return ''

            st.dataframe(
                df_takip[["Coin","Sembol","Eklenme","Başlangıç Fiyat","Güncel Fiyat",
                           "Performans %","24s Değişim %","Başlangıç Sinyali","Güncel Sinyal","Sinyal Durumu"]]
                .style.format({
                    "Başlangıç Fiyat": "{:,.6f}",
                    "Güncel Fiyat":    "{:,.6f}",
                    "Performans %":    "{:+.2f}",
                    "24s Değişim %":   "{:+.2f}",
                })
                .map(renklendir_performans, subset=["Performans %"])
                .map(renklendir_sinyal, subset=["Başlangıç Sinyali", "Güncel Sinyal"]),
                use_container_width=True, hide_index=True,
            )

            # Özet metrikler
            st.markdown("---")
            kazananlar = df_takip[df_takip['Performans %'] > 0]
            kaybedenler = df_takip[df_takip['Performans %'] < 0]
            sinyal_degisenler = df_takip[df_takip['Sinyal Durumu'] == "🔄 Değişti"]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("✅ Karda Olan", len(kazananlar))
            m2.metric("❌ Zararda Olan", len(kaybedenler))
            m3.metric("🔄 Sinyali Değişen", len(sinyal_degisenler))
            if not df_takip.empty:
                m4.metric("📊 Ort. Performans",
                          f"%{df_takip['Performans %'].mean():+.2f}")

            # Takipten çıkar
            st.markdown("---")
            st.subheader("🗑️ Takipten Çıkar")
            cikar_secenekler = {f"{r['Coin']} ({r['Sembol']})": r['_coin_id'] for _, r in df_takip.iterrows()}
            secilen_cikar    = st.selectbox("Takipten çıkarılacak coin:", list(cikar_secenekler.keys()))
            if st.button("🗑️ Takipten Çıkar", use_container_width=False):
                if takipten_cikar(cikar_secenekler[secilen_cikar]):
                    st.success(f"✅ {secilen_cikar} takip listesinden çıkarıldı.")
                    st.rerun()
                else:
                    st.error("Bir hata oluştu.")
