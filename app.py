import streamlit as st
import pandas as pd
import requests
import time
import numpy as np

# SAYFA AYARLARI
st.set_page_config(page_title="OBV Pro Scanner", layout="wide", page_icon="🐋")

st.markdown("""
    <style>
    .big-font { font-size:24px !important; font-weight: bold; color: #8dc647; }
    .stProgress > div > div > div > div { background-color: #8dc647; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<p class="big-font">🦎 CoinGecko Altyapılı Gelişmiş OBV Hacim & Balina Tarayıcı</p>', unsafe_allow_html=True)
st.write("Fiyat hareketlerini gerçek hacim trendleriyle doğrulayarak balina akümülasyonunu kategorilere göre filtreleyin.")

# ─── API AYARLARI ───────────────────────────────────────────────
API_KEY = st.secrets["CG_API_KEY"]
BASE_URL = "https://api.coingecko.com/api/v3"
HEADERS  = {"accept": "application/json", "x-cg-demo-api-key": API_KEY}


# ─── OBV FONKSİYONLARI ──────────────────────────────────────────
def obv_hesapla(df):
    """
    OBV(t) = OBV(t-1) + V(t) * sign(P(t) - P(t-1))
    """
    if len(df) < 2:
        df['OBV'] = 0
        df['OBV_Trend'] = 0
        df['OBV_EMA'] = 0
        return df

    obv = [0]
    for i in range(1, len(df)):
        fark = df.loc[i, 'Fiyat'] - df.loc[i - 1, 'Fiyat']
        hacim = df.loc[i, 'Hacim']
        if fark > 0:
            obv.append(obv[-1] + hacim)
        elif fark < 0:
            obv.append(obv[-1] - hacim)
        else:
            obv.append(obv[-1])

    df['OBV'] = obv
    df['OBV_Trend'] = df['OBV'].rolling(window=5, min_periods=1).mean()
    df['OBV_EMA']   = df['OBV'].ewm(span=5, adjust=False).mean()
    return df


def obv_momentum_hesapla(df, periyot=5):
    if len(df) < periyot + 1:
        return 0
    payda = abs(df['OBV'].iloc[-periyot - 1]) + 1
    return (df['OBV'].iloc[-1] - df['OBV'].iloc[-periyot - 1]) / payda


def uyumsuzluk_kontrol_et(df, periyot, hassasiyet="Orta"):
    """
    Fiyat-OBV diverjansı kontrolü.
    hassasiyet parametresi eşik değerlerini ayarlar:
      Düşük  → sadece güçlü sinyaller
      Orta   → dengeli
      Yüksek → hassas, daha fazla sinyal üretir
    """
    if len(df) < periyot:
        return "Yetersiz Veri"

    esik = {"Düşük": 3.0, "Orta": 1.5, "Yüksek": 0.5}.get(hassasiyet, 1.5)

    mevcut_fiyat = df['Fiyat'].iloc[-1]
    onceki_fiyat = df['Fiyat'].iloc[-periyot]
    mevcut_obv   = df['OBV'].iloc[-1]
    onceki_obv   = df['OBV'].iloc[-periyot]

    fiyat_pct = ((mevcut_fiyat - onceki_fiyat) / (onceki_fiyat + 1e-12)) * 100
    obv_pct   = ((mevcut_obv   - onceki_obv)   / (abs(onceki_obv) + 1))   * 100

    # Pozitif diverjans: fiyat düşerken OBV yükseliyor
    if fiyat_pct < -esik and obv_pct > esik:
        if obv_pct > abs(fiyat_pct) * 2:
            return "🔵 GÜÇLÜ POZİTİF (Ağır Balina Topluyor)"
        return "🔵 POZİTİF (Balina Topluyor)"

    # Negatif diverjans: fiyat yükselirken OBV düşüyor
    elif fiyat_pct > esik and obv_pct < -esik:
        if abs(obv_pct) > fiyat_pct:
            return "🔴 GÜÇLÜ NEGATİF (Büyük Dağıtım)"
        return "🔴 NEGATİF (Sahte Yükseliş)"

    # Hacim destekli hareketler
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

    # Nötr
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


# ─── KATEGORİ LİSTESİ ───────────────────────────────────────────
@st.cache_data(ttl=3600)
def kategorileri_getir():
    try:
        res = requests.get(f"{BASE_URL}/coins/categories/list", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return pd.DataFrame(res.json())
    except Exception:
        pass
    return pd.DataFrame()


df_kategoriler = kategorileri_getir()


# ─── SIDEBAR ────────────────────────────────────────────────────
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

secilen_kategori_id = ""
if secilen_kategori_adi != "Tüm Kripto Dünyası" and not df_kategoriler.empty:
    eslesen = df_kategoriler[df_kategoriler['name'] == secilen_kategori_adi]
    if not eslesen.empty:
        secilen_kategori_id = eslesen['category_id'].values[0]

st.sidebar.markdown("---")
tarama_sayisi   = st.sidebar.number_input("Kaç coin taransın?", min_value=5, max_value=500, value=50, step=5)
analiz_periyodu = st.sidebar.slider("OBV Kaç Günlük Trende Baksın?", 3, 30, 7, step=1)

# ✅ DÜZELTİLDİ: hassasiyet artık fonksiyona geçiriliyor
obv_hassasiyet  = st.sidebar.select_slider(
    "OBV Hassasiyeti",
    options=["Düşük", "Orta", "Yüksek"],
    value="Orta",
    help="Düşük = sadece güçlü sinyaller | Yüksek = daha fazla sinyal üretir"
)

tarama_butonu = st.sidebar.button("Piyasayı Canlı Tara ve Analiz Et 🚀", use_container_width=True)


# ─── TARAMA MOTORU ──────────────────────────────────────────────
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
            st.error(f"Veri çekme hatası. Kod: {res.status_code} | {res.text[:200]}")
            st.stop()
        coin_listesi = res.json()
    except Exception as e:
        st.error(f"Bağlantı hatası: {e}")
        st.stop()

    if not coin_listesi:
        st.warning("Seçilen kategoride eşleşen coin bulunamadı.")
        st.stop()

    sonuc_tablosu = []
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

        chart_url    = f"{BASE_URL}/coins/{coin_id}/market_chart"
        chart_params = {"vs_currency": "usd", "days": 35, "interval": "daily"}

        try:
            chart_res = requests.get(chart_url, headers=HEADERS, params=chart_params, timeout=10)
            if chart_res.status_code == 429:
                time.sleep(8)
                chart_res = requests.get(chart_url, headers=HEADERS, params=chart_params, timeout=10)

            if chart_res.status_code == 200:
                chart_data = chart_res.json()
                fiyatlar   = [oge[1] for oge in chart_data.get('prices', [])]
                hacimler   = [oge[1] for oge in chart_data.get('total_volumes', [])]

                if fiyatlar and hacimler:
                    df_coin     = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                    df_coin     = obv_hesapla(df_coin)
                    # ✅ DÜZELTİLDİ: hassasiyet parametresi artık geçiriliyor
                    sinyal      = uyumsuzluk_kontrol_et(df_coin, analiz_periyodu, obv_hassasiyet)
                    obv_dengesi = obv_hacim_dengesi(df_coin, analiz_periyodu)

                    sonuc_tablosu.append({
                        "Sıra":           indeks + 1,
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
        except Exception:
            continue   # ✅ DÜZELTİLDİ: pass → continue

        time.sleep(1.5)
        progres_bari.progress((indeks + 1) / len(coin_listesi))

    durum_yazisi.empty()

    # ─── RAPORLAMA ───────────────────────────────────────────────
    df_sonuc = pd.DataFrame(sonuc_tablosu)

    if not df_sonuc.empty:
        st.success(f"📊 {len(df_sonuc)} coin OBV süzgecinden geçirildi!")

        pozitif              = df_sonuc[df_sonuc['OBV Sinyali'].str.contains("POZİTİF", na=False)]
        negatif              = df_sonuc[df_sonuc['OBV Sinyali'].str.contains("NEGATİF", na=False)]
        hacim_destekli       = df_sonuc[df_sonuc['OBV Sinyali'].str.contains("YÜKSELİŞ", na=False)]

        c1, c2, c3 = st.columns(3)
        c1.metric("🐋 Balina Toplayan Coin",    len(pozitif))
        c2.metric("🚨 Riskli / Şişen Coin",     len(negatif))
        c3.metric("📈 Hacim Destekli Yükseliş", len(hacim_destekli))

        st.markdown("---")
        col_sol, col_orta, col_sag = st.columns(3)

        with col_sol:
            st.markdown("### 🔵 Potansiyel Alım Fırsatları")
            if not pozitif.empty:
                st.dataframe(
                    pozitif[["Coin Adı Metin", "Coin Adı", "Sembol", "Fiyat ($)", "OBV Dengesi %", "24s Hacim ($)"]],
                    column_config={
                        "Coin Adı Metin": st.column_config.TextColumn("Coin Adı"),
                        "Coin Adı": st.column_config.LinkColumn("🔗 CG", display_text="🔗"),
                    },
                    use_container_width=True, hide_index=True,
                )
            else:
                st.write("Pozitif uyumsuzluk gösteren coin yok.")

        with col_orta:
            st.markdown("### 🟢 Hacim Destekli Yükseliş")
            if not hacim_destekli.empty:
                st.dataframe(
                    hacim_destekli[["Coin Adı Metin", "Coin Adı", "Sembol", "24s Değişim %", "OBV Dengesi %", "24s Hacim ($)"]],
                    column_config={
                        "Coin Adı Metin": st.column_config.TextColumn("Coin Adı"),
                        "Coin Adı": st.column_config.LinkColumn("🔗 CG", display_text="🔗"),
                    },
                    use_container_width=True, hide_index=True,
                )
            else:
                st.write("Hacim destekli yükseliş gösteren coin yok.")

        with col_sag:
            st.markdown("### 🔴 Potansiyel Satış / Kar Al Bölgeleri")
            if not negatif.empty:
                st.dataframe(
                    negatif[["Coin Adı Metin", "Coin Adı", "Sembol", "Fiyat ($)", "OBV Dengesi %", "24s Hacim ($)"]],
                    column_config={
                        "Coin Adı Metin": st.column_config.TextColumn("Coin Adı"),
                        "Coin Adı": st.column_config.LinkColumn("🔗 CG", display_text="🔗"),
                    },
                    use_container_width=True, hide_index=True,
                )
            else:
                st.write("Negatif uyumsuzluk gösteren coin yok.")

        st.markdown("---")
        st.subheader("📋 Tüm Piyasa Tablosu")

        # ✅ DÜZELTİLDİ: applymap → map (Pandas 2.1+ uyumlu)
        def renklendir_sinyal(val):
            if "POZİTİF" in str(val):
                return 'background-color: #90EE90'
            elif "NEGATİF" in str(val):
                return 'background-color: #FFCCCC'
            elif "YÜKSELİŞ" in str(val):
                return 'background-color: #E0F7FA'
            elif "DÜŞÜŞ" in str(val):
                return 'background-color: #FFF3CD'
            return ''

        st.dataframe(
            df_sonuc.style.format({
                "Fiyat ($)":      "{:,.4f}",
                "Market Cap ($)": "{:,.0f}",
                "24s Hacim ($)":  "{:,.0f}",
                "OBV Dengesi %":  "{:,.2f}",
                "24s Değişim %":  "{:,.2f}",
            }).map(renklendir_sinyal, subset=['OBV Sinyali']),
            column_config={
                "Coin Adı Metin": st.column_config.TextColumn("Coin Adı"),
                "Coin Adı": st.column_config.LinkColumn("🔗 CG", display_text="🔗"),
            },
            use_container_width=True,
            hide_index=True,
        )

        # ─── İSTATİSTİKSEL ÖZET ──────────────────────────────────
        st.markdown("---")
        st.subheader("📈 OBV İstatistiksel Özeti")

        pozitif_obv = df_sonuc[df_sonuc['OBV Dengesi %'] > 0]
        negatif_obv = df_sonuc[df_sonuc['OBV Dengesi %'] < 0]

        col_a, col_b = st.columns(2)
        col_a.metric(
            "🟢 Pozitif OBV Dengesi Olan Coinler",
            len(pozitif_obv),
            delta=f"%{pozitif_obv['OBV Dengesi %'].mean():.1f}" if not pozitif_obv.empty else "0"
        )
        col_b.metric(
            "🔴 Negatif OBV Dengesi Olan Coinler",
            len(negatif_obv),
            delta=f"%{negatif_obv['OBV Dengesi %'].mean():.1f}" if not negatif_obv.empty else "0"
        )

    else:
        st.error("Tablo oluşturulamadı. Lütfen birkaç dakika sonra tekrar çalıştırın.")
