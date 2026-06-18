import streamlit as st
import pandas as pd
import requests
import time
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import anthropic

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
    api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    return anthropic.Anthropic(api_key=api_key)


def ai_guru_yorumu_uret(veri_metni):
    """Uygulamanın hesapladığı gerçek verileri AI'a gönderip guru yorumu üretir."""
    client = ai_istemci_al()
    if client is None:
        return ("⚠️ AI yorumu için ANTHROPIC_API_KEY tanımlı değil. "
                "Streamlit Cloud → App settings → Secrets bölümüne eklemen gerekiyor.")
    try:
        mesaj = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=GURU_SISTEM_PROMPT,
            messages=[{"role": "user", "content": veri_metni}],
        )
        return mesaj.content[0].text
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


# ─── KATEGORİ & COIN FONKSİYONLARI ─────────────────────────────
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

                    # Sonucu session_state'e kaydediyoruz: aşağıdaki "Takibe Ekle" ve
                    # "AI Yorumu Al" butonlarına tıklanınca sayfa yeniden çalışsa da
                    # analiz ekranda kalır, kaybolmaz.
                    st.session_state['tab2_analiz'] = {
                        "secilen_id":  secilen_id,
                        "secilen":     secilen,
                        "df_coin":     df_coin,
                        "sinyal":      sinyal,
                        "coin_bilgi":  coin_bilgi,
                        "obv_dengesi": obv_dengesi,
                        "periyot":     periyot,
                    }

            # ─── KAYITLI ANALİZİ GÖSTER (seçili coin'e aitse) ────────────
            analiz = st.session_state.get('tab2_analiz')
            if analiz and analiz.get("secilen_id") == secilen_id:
                df_coin     = analiz["df_coin"]
                sinyal      = analiz["sinyal"]
                coin_bilgi  = analiz["coin_bilgi"]
                obv_dengesi = analiz["obv_dengesi"]
                secilen_lbl = analiz["secilen"]

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

                # İstatistikler
                s1, s2, s3 = st.columns(3)
                s1.metric("OBV Dengesi %", f"{obv_dengesi:.2f}%")
                s2.metric("Son OBV", f"{df_coin['OBV'].iloc[-1]:,.0f}")
                s3.metric("OBV Trendi",
                          "📈 Yükseliyor" if df_coin['OBV'].iloc[-1] > df_coin['OBV_Trend'].iloc[-1] else "📉 Düşüyor")

                # ─── AI GURU COIN YORUMU ──────────────────────────
                st.markdown("---")
                st.subheader("🧠 AI Guru — Bu Coin İçin Durum Tespiti")
                st.caption("Yorum, yukarıda hesaplanan gerçek OBV ve fiyat verilerine dayanır; "
                           "AI rastgele tahmin üretmez.")

                if st.button("🔮 AI Yorumu Al", key=f"ai_coin_{secilen_id}"):
                    with st.spinner("🧠 Guru veriyi inceliyor..."):
                        veri_metni = f"""Coin: {coin_adi_str} ({coin_sym_str})
Güncel fiyat: ${mevcut_fiyat:,.6f}
24 saatlik fiyat değişimi: %{degisim_24h:.2f}
Market Cap: ${market_cap:,.0f}
24 saatlik hacim: ${hacim_24h:,.0f}
Analiz periyodu: {analiz['periyot']} gün, hassasiyet ayarı: {obv_hassasiyet}
Hesaplanan OBV sinyali: {sinyal}
OBV Dengesi: {obv_dengesi:.2f}%
Son OBV değeri: {df_coin['OBV'].iloc[-1]:,.0f}
OBV trendi: {"yükseliyor" if df_coin['OBV'].iloc[-1] > df_coin['OBV_Trend'].iloc[-1] else "düşüyor"}

Bu coin için OBV ve fiyat verilerine dayanarak bir durum tespiti yap."""
                        yorum = ai_guru_yorumu_uret(veri_metni)

                    st.markdown(
                        f'<div style="background:{banner_renk}15; border-left:4px solid {banner_renk}; '
                        f'padding:16px 20px; border-radius:6px; line-height:1.6;">{yorum}</div>',
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
