import streamlit as st
import pandas as pd
import requests
import time
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from styles import get_css, get_banner_html
from data import (
    get_categories,
    search_coin,
    get_coin_chart,
    get_coin_info,
    get_current_price,
    get_watchlist,
    add_to_watchlist,
    remove_from_watchlist,
    get_fear_greed,
    get_btc_dominance,
)
from indicators import (
    calculate_obv,
    obv_balance,
    obv_signal,
    calculate_all_indicators,
)
from ai import get_guru_comment

st.set_page_config(page_title="OBV Pro Scanner", layout="wide", page_icon="🐋")
st.markdown(get_css(), unsafe_allow_html=True)
st.markdown(get_banner_html(), unsafe_allow_html=True)

if "scan_results" not in st.session_state:
    st.session_state.scan_results = pd.DataFrame()
if "scan_raw" not in st.session_state:
    st.session_state.scan_raw = []
if "tab2_analiz" not in st.session_state:
    st.session_state.tab2_analiz = None
if "watchlist_cache" not in st.session_state:
    st.session_state.watchlist_cache = []

def obv_grafigi_ciz(df_coin, coin_adi, sinyal):
    sinyal_renk = "#607D8B"
    if "POZİTİF" in sinyal:
        sinyal_renk = "#2196F3"
    elif "NEGATİF" in sinyal:
        sinyal_renk = "#F44336"
    elif "YÜKSELİŞ" in sinyal:
        sinyal_renk = "#4CAF50"
    elif "DÜŞÜŞ" in sinyal:
        sinyal_renk = "#FF9800"

    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        subplot_titles=("📈 Fiyat (USD)", "📊 OBV (On-Balance Volume)"),
        row_heights=[0.55, 0.45],
    )
    x = list(range(len(df_coin)))

    fig.add_trace(go.Scatter(
        x=x, y=df_coin["Fiyat"], mode="lines", name="Fiyat",
        line=dict(color="#00BCD4", width=2),
        fill="tozeroy", fillcolor="rgba(0,188,212,0.08)",
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=x, y=df_coin["OBV"], mode="lines", name="OBV",
        line=dict(color=sinyal_renk, width=2),
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=x, y=df_coin["OBV_EMA"], mode="lines", name="OBV EMA(5)",
        line=dict(color="rgba(255,193,7,0.8)", width=1.5, dash="dot"),
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=x, y=df_coin["OBV_Trend"], mode="lines", name="OBV MA(5)",
        line=dict(color="rgba(255,255,255,0.4)", width=1, dash="dash"),
    ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"{coin_adi} — OBV Analizi", font=dict(size=16)),
        paper_bgcolor="rgba(14,17,23,1)",
        plot_bgcolor="rgba(14,17,23,1)",
        font=dict(color="#FAFAFA"),
        height=600,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)"),
        xaxis2=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)", title="Gün"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)"),
        yaxis2=dict(showgrid=True, gridcolor="rgba(255,255,255,0.07)"),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig

def renklendir_sinyal(val):
    if "POZİTİF" in str(val):
        return "background-color: #1a3a2a; color: #90EE90"
    if "NEGATİF" in str(val):
        return "background-color: #3a1a1a; color: #FF8A80"
    if "YÜKSELİŞ" in str(val):
        return "background-color: #1a2a1a; color: #A5D6A7"
    if "DÜŞÜŞ" in str(val):
        return "background-color: #2a2a1a; color: #FFE082"
    return ""

def render_piyasa_tarama():
    st.write("Fiyat hareketlerini gerçek hacim trendleriyle doğrulayarak balina akümülasyonunu kategorilere göre filtreleyin.")

    df_kategoriler = get_categories()
    siralam_secimi = st.session_state.get("siralam_secimi")
    kategori_adi = st.session_state.get("kategori_adi")
    tarama_sayisi = st.session_state.get("tarama_sayisi", 50)
    analiz_periyodu = st.session_state.get("analiz_periyodu", 7)
    obv_hassasiyet = st.session_state.get("obv_hassasiyet", "Orta")

    if "siralam_secimi" not in st.session_state:
        st.session_state.siralam_secimi = "Market Cap (Büyükten Küçüğe)"
    if "kategori_adi" not in st.session_state:
        st.session_state.kategori_adi = "Tüm Kripto Dünyası"

    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
    with col1:
        st.session_state.siralam_secimi = st.selectbox(
            "Sıralama Esası",
            ["Market Cap (Büyükten Küçüğe)", "Market Cap (Küçükten Büyüğe)", "24 Saatlik Hacim Yüksekten Düşüğe"],
            index=["Market Cap (Büyükten Küçüğe)", "Market Cap (Küçükten Büyüğe)", "24 Saatlik Hacim Yüksekten Düşüğe"].index(st.session_state.siralam_secimi),
        )
    kategori_opsiyonlari = ["Tüm Kripto Dünyası"]
    if not df_kategoriler.empty and "name" in df_kategoriler.columns:
        kategori_opsiyonlari.extend(df_kategoriler["name"].tolist())
    with col2:
        st.session_state.kategori_adi = st.selectbox(
            "Kategori / Sektör Seçin",
            kategori_opsiyonlari,
            index=kategori_opsiyonlari.index(st.session_state.kategori_adi) if st.session_state.kategori_adi in kategori_opsiyonlari else 0,
        )
    with col3:
        st.session_state.tarama_sayisi = st.number_input("Kaç coin taransın?", min_value=5, max_value=250, value=int(tarama_sayisi), step=5)
    with col4:
        st.session_state.analiz_periyodu = st.slider("OBV Günlük Trend", 3, 30, int(analiz_periyodu), step=1)

    st.session_state.obv_hassasiyet = st.select_slider(
        "OBV Hassasiyeti",
        options=["Düşük", "Orta", "Yüksek"],
        value=obv_hassasiyet,
        help="Düşük = sadece güçlü sinyaller | Yüksek = daha fazla sinyal üretir",
    )

    tarama_butonu = st.button("Piyasayı Canlı Tara 🚀", use_container_width=True)

    secilen_kategori_id = ""
    if st.session_state.kategori_adi != "Tüm Kripto Dünyası" and not df_kategoriler.empty:
        eslesen = df_kategoriler[df_kategoriler["name"] == st.session_state.kategori_adi]
        if not eslesen.empty:
            secilen_kategori_id = eslesen["category_id"].values[0]

    if tarama_butonu:
        st.info("🔄 Coin listesi CoinGecko'dan çekiliyor...")
        siralama_map = {
            "Market Cap (Büyükten Küçüğe)": "market_cap_desc",
            "Market Cap (Küçükten Büyüğe)": "market_cap_asc",
            "24 Saatlik Hacim Yüksekten Düşüğe": "volume_desc",
        }
        params = {
            "vs_currency": "usd",
            "order": siralama_map.get(st.session_state.siralam_secimi, "market_cap_desc"),
            "per_page": st.session_state.tarama_sayisi,
            "page": 1,
            "sparkline": "false",
        }
        if secilen_kategori_id:
            params["category"] = secilen_kategori_id

        try:
            res = requests.get("https://api.coingecko.com/api/v3/coins/markets", headers={"accept": "application/json", "x-cg-demo-api-key": st.secrets["CG_API_KEY"]}, params=params, timeout=15)
            if res.status_code == 429:
                st.error("⚠️ API hız limiti aşıldı. Birkaç dakika sonra tekrar deneyin.")
                st.stop()
            if res.status_code != 200:
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
        st.session_state.scan_raw = []
        prog = st.progress(0)
        durum = st.empty()

        for idx, coin in enumerate(coin_listesi):
            coin_id = coin["id"]
            coin_name = coin["name"]
            coin_symbol = coin["symbol"].upper()
            current_price = coin.get("current_price", 0)
            market_cap = coin.get("market_cap", 0)
            hacim_24h = coin.get("total_volume", 0)
            price_change_24h = coin.get("price_change_percentage_24h", 0)

            durum.text(f"📡 Analiz ediliyor: {coin_name} ({idx + 1}/{len(coin_listesi)})")
            try:
                chart_data = get_coin_chart(coin_id, 35)
                if chart_data:
                    fiyatlar = [o[1] for o in chart_data.get("prices", [])]
                    hacimler = [o[1] for o in chart_data.get("total_volumes", [])]
                    if fiyatlar and hacimler:
                        df_coin = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                        df_coin = calculate_obv(df_coin)
                        sinyal = obv_signal(df_coin, st.session_state.analiz_periyodu, st.session_state.obv_hassasiyet)
                        obv_dengesi = obv_balance(df_coin, st.session_state.analiz_periyodu)
                        sonuc_tablosu.append({
                            "Coin Adı": f"https://www.coingecko.com/en/coins/{coin_id}",
                            "Coin Adı Metin": coin_name,
                            "Sembol": coin_symbol,
                            "Fiyat ($)": current_price,
                            "24s Değişim %": price_change_24h,
                            "Market Cap ($)": market_cap,
                            "24s Hacim ($)": hacim_24h,
                            "OBV Dengesi %": round(obv_dengesi, 2),
                            "OBV Sinyali": sinyal,
                        })
                        st.session_state.scan_raw.append({
                            "coin_id": coin_id, "coin_adi": coin_name, "sembol": coin_symbol,
                            "fiyat": current_price, "sinyal": sinyal
                        })
            except Exception:
                pass

            time.sleep(1.2)
            prog.progress((idx + 1) / len(coin_listesi))

        durum.empty()
        st.session_state.scan_results = pd.DataFrame(sonuc_tablosu)

    df_sonuc = st.session_state.scan_results
    if df_sonuc.empty:
        st.info("Henüz tarama sonucu yok. Yukarıdaki butonla tarama başlat.")
        return

    st.success(f"📊 {len(df_sonuc)} coin OBV süzgecinden geçirildi!")
    pozitif = df_sonuc[df_sonuc["OBV Sinyali"].str.contains("POZİTİF", na=False)]
    negatif = df_sonuc[df_sonuc["OBV Sinyali"].str.contains("NEGATİF", na=False)]
    hacim_destekli = df_sonuc[df_sonuc["OBV Sinyali"].str.contains("YÜKSELİŞ", na=False)]

    c1, c2, c3 = st.columns(3)
    c1.metric("🐋 Balina Toplayan Coin", len(pozitif))
    c2.metric("🚨 Riskli / Şişen Coin", len(negatif))
    c3.metric("📈 Hacim Destekli Yükseliş", len(hacim_destekli))

    st.markdown("---")
    link_config = {
        "Coin Adı Metin": st.column_config.TextColumn("Coin Adı"),
        "Coin Adı": st.column_config.LinkColumn("🔗 CG", display_text="🔗"),
    }

    col_sol, col_orta, col_sag = st.columns(3)
    with col_sol:
        st.markdown("### 🔵 Potansiyel Alım Fırsatları")
        if not pozitif.empty:
            st.dataframe(pozitif[["Coin Adı Metin", "Coin Adı", "Sembol", "Fiyat ($)", "OBV Dengesi %", "24s Hacim ($)"]], column_config=link_config, use_container_width=True, hide_index=True)
    with col_orta:
        st.markdown("### 🟢 Hacim Destekli Yükseliş")
        if not hacim_destekli.empty:
            st.dataframe(hacim_destekli[["Coin Adı Metin", "Coin Adı", "Sembol", "24s Değişim %", "OBV Dengesi %", "24s Hacim ($)"]], column_config=link_config, use_container_width=True, hide_index=True)
    with col_sag:
        st.markdown("### 🔴 Potansiyel Satış / Kar Al Bölgeleri")
        if not negatif.empty:
            st.dataframe(negatif[["Coin Adı Metin", "Coin Adı", "Sembol", "Fiyat ($)", "OBV Dengesi %", "24s Hacim ($)"]], column_config=link_config, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("📋 Tüm Piyasa Tablosu")
    st.dataframe(
        df_sonuc.style.format({
            "Fiyat ($)": "{:,.4f}",
            "Market Cap ($)": "{:,.0f}",
            "24s Hacim ($)": "{:,.0f}",
            "OBV Dengesi %": "{:,.2f}",
            "24s Değişim %": "{:,.2f}",
        }).map(renklendir_sinyal, subset=["OBV Sinyali"]),
        column_config=link_config,
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.subheader("⭐ Takibe Al")
    sinyal_verenler = [c for c in st.session_state.scan_raw if "Nötr" not in c["sinyal"] and "Yetersiz" not in c["sinyal"]]
    if sinyal_verenler:
        secenekler = {f"{c['coin_adi']} ({c['sembol']}) — {c['sinyal']}": c for c in sinyal_verenler}
        secilen_coin_str = st.selectbox("Takibe almak istediğin coin:", list(secenekler.keys()))
        secilen_coin_data = secenekler[secilen_coin_str]
        if st.button("➕ Takip Listesine Ekle"):
            basari, mesaj = add_to_watchlist(secilen_coin_data["coin_id"], secilen_coin_data["coin_adi"], secilen_coin_data["sembol"], secilen_coin_data["fiyat"], secilen_coin_data["sinyal"])
            if basari:
                st.success(f"✅ {secilen_coin_data['coin_adi']} takip listesine eklendi!")
                st.balloons()
            elif mesaj == "zaten_var":
                st.info(f"ℹ️ {secilen_coin_data['coin_adi']} zaten takip listende.")
            else:
                st.error(f"Hata: {mesaj}")
    else:
        st.info("Sinyal veren coin bulunamadı.")

    st.markdown("---")
    st.subheader("📈 OBV İstatistiksel Özeti")
    pozitif_obv = df_sonuc[df_sonuc["OBV Dengesi %"] > 0]
    negatif_obv = df_sonuc[df_sonuc["OBV Dengesi %"] < 0]
    col_a, col_b = st.columns(2)
    col_a.metric("🟢 Pozitif OBV Dengesi", len(pozitif_obv), delta=f"%{pozitif_obv['OBV Dengesi %'].mean():.1f}" if not pozitif_obv.empty else "0")
    col_b.metric("🔴 Negatif OBV Dengesi", len(negatif_obv), delta=f"%{negatif_obv['OBV Dengesi %'].mean():.1f}" if not negatif_obv.empty else "0")

    st.markdown("---")
    st.subheader("🧠 AI Guru — Piyasa Durum Tespiti")
    if st.button("🔮 AI Piyasa Yorumu Oluştur"):
        with st.spinner("🧠 Guru veriyi inceliyor..."):
            top_pozitif = pozitif.sort_values("OBV Dengesi %", ascending=False).head(5)
            top_negatif = negatif.sort_values("OBV Dengesi %", ascending=True).head(5)
            veri_metni = f"""Taranan toplam coin sayısı: {len(df_sonuc)}
Balina birikim sinyali (POZİTİF) veren coin sayısı: {len(pozitif)}
Dağıtım/riskli sinyal (NEGATİF) veren coin sayısı: {len(negatif)}
Hacim destekli yükselişte olan coin sayısı: {len(hacim_destekli)}
Tüm coinlerin ortalama OBV Dengesi: {df_sonuc['OBV Dengesi %'].mean():.2f}%
Analiz periyodu: {st.session_state.analiz_periyodu} gün, hassasiyet ayarı: {st.session_state.obv_hassasiyet}

En güçlü pozitif coinler:
{top_pozitif[['Coin Adı Metin','Sembol','24s Değişim %','OBV Dengesi %']].to_string(index=False) if not top_pozitif.empty else 'Yok'}

En güçlü negatif coinler:
{top_negatif[['Coin Adı Metin','Sembol','24s Değişim %','OBV Dengesi %']].to_string(index=False) if not top_negatif.empty else 'Yok'}"""
            yorum = get_guru_comment(veri_metni)
        st.markdown(f'<div style="background:#8dc64722; border-left:4px solid #8dc647; padding:16px 20px; border-radius:6px; line-height:1.6;">{yorum}</div>', unsafe_allow_html=True)

def render_coin_ara():
    st.subheader("🔍 Tek Coin OBV Analizi")
    st.write("Coin adı veya sembolü yazın, detaylı OBV grafiği ve sinyal görün.")

    col_ara, col_gun = st.columns([3, 1])
    with col_ara:
        arama_metni = st.text_input("Coin Ara", placeholder="Bitcoin, ETH, SOL, VIRTUAL...", key="arama_coin")
    with col_gun:
        grafik_gun = st.selectbox("Gün Aralığı", [7, 14, 30, 60, 90], index=2, key="grafik_gun")

    if not arama_metni:
        st.info("Arama yapmak için bir coin adı veya sembolü yaz.")
        return

    with st.spinner("🔎 Aranıyor..."):
        sonuclar = search_coin(arama_metni)

    if not sonuclar:
        st.warning("Sonuç bulunamadı.")
        return

    secenekler = {f"{c['name']} ({c['symbol'].upper()})": c['id'] for c in sonuclar[:8]}
    secilen = st.selectbox("Sonuçlar:", list(secenekler.keys()), key="secilen_coin")
    secilen_id = secenekler[secilen]

    if st.button("📊 Analiz Et"):
        with st.spinner("📡 Veri çekiliyor..."):
            chart_data = get_coin_chart(secilen_id, grafik_gun)
            coin_bilgi = get_coin_info(secilen_id)

        if not chart_data:
            st.error("Veri çekilemedi.")
            st.session_state.tab2_analiz = None
            return

        fiyatlar = [o[1] for o in chart_data.get("prices", [])]
        hacimler = [o[1] for o in chart_data.get("total_volumes", [])]
        df_coin = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
        df_coin = calculate_obv(df_coin)
        periyot = min(st.session_state.analiz_periyodu, len(df_coin) - 1)
        sinyal = obv_signal(df_coin, periyot, st.session_state.obv_hassasiyet)
        obv_dengesi = obv_balance(df_coin, periyot)
        ind = calculate_all_indicators(df_coin, periyot)
        fg_deger, fg_yorum = get_fear_greed()
        btc_dom, mcap_degisim = get_btc_dominance()

        st.session_state.tab2_analiz = {
            "secilen_id": secilen_id,
            "secilen": secilen,
            "df_coin": df_coin,
            "sinyal": sinyal,
            "coin_bilgi": coin_bilgi,
            "obv_dengesi": obv_dengesi,
            "periyot": periyot,
            "ind": ind,
            "fg_deger": fg_deger,
            "fg_yorum": fg_yorum,
            "btc_dom": btc_dom,
            "mcap_degisim": mcap_degisim,
        }

    analiz = st.session_state.tab2_analiz
    if not analiz or analiz.get("secilen_id") != secilen_id:
        return

    df_coin = analiz["df_coin"]
    sinyal = analiz["sinyal"]
    coin_bilgi = analiz["coin_bilgi"]
    obv_dengesi = analiz["obv_dengesi"]
    secilen_lbl = analiz["secilen"]
    ind = analiz["ind"]
    fg_deger = analiz["fg_deger"]
    fg_yorum = analiz["fg_yorum"]
    btc_dom = analiz["btc_dom"]
    mcap_degisim = analiz["mcap_degisim"]

    mevcut_fiyat = degisim_24h = market_cap = hacim_24h = 0
    if coin_bilgi:
        mevcut_fiyat = coin_bilgi.get("market_data", {}).get("current_price", {}).get("usd", 0)
        degisim_24h = coin_bilgi.get("market_data", {}).get("price_change_percentage_24h", 0)
        market_cap = coin_bilgi.get("market_data", {}).get("market_cap", {}).get("usd", 0)
        hacim_24h = coin_bilgi.get("market_data", {}).get("total_volume", {}).get("usd", 0)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("💰 Fiyat", f"${mevcut_fiyat:,.6f}", delta=f"%{degisim_24h:.2f}")
    k2.metric("📊 Market Cap", f"${market_cap:,.0f}")
    k3.metric("💧 24s Hacim", f"${hacim_24h:,.0f}")
    k4.metric("🔗 CoinGecko", "→", help=f"https://www.coingecko.com/en/coins/{secilen_id}")

    st.markdown(f"[🔗 CoinGecko'da Görüntüle](https://www.coingecko.com/en/coins/{secilen_id})")

    sinyal_renk_map = {"POZİTİF": "#2196F3", "NEGATİF": "#F44336", "YÜKSELİŞ": "#4CAF50", "DÜŞÜŞ": "#FF9800"}
    banner_renk = "#607D8B"
    for k, v in sinyal_renk_map.items():
        if k in sinyal:
            banner_renk = v
            break
    st.markdown(f'<div style="background:{banner_renk}22; border-left:4px solid {banner_renk}; padding:12px 20px; border-radius:6px; font-size:20px; font-weight:bold; color:{banner_renk}; margin:12px 0">{sinyal}</div>', unsafe_allow_html=True)

    st.plotly_chart(obv_grafigi_ciz(df_coin, secilen_lbl, sinyal), use_container_width=True)

    st.markdown("---")
    st.subheader("📐 Teknik İndikatörler")
    i1, i2, i3, i4 = st.columns(4)
    i1.metric("RSI (14)", f"{ind.get('rsi')}" if ind.get("rsi") is not None else "—", delta=ind.get("rsi_yorum", ""))
    i2.metric("MACD", f"{ind.get('macd'):.6f}" if ind.get("macd") is not None else "—", delta="▲ Pozitif" if ind.get("macd_histogram") and ind.get("macd_histogram") > 0 else "▼ Negatif" if ind.get("macd_histogram") is not None else "")
    i3.metric("Bollinger %B", f"{ind.get('bb_yuzde_b'):.2f}" if ind.get("bb_yuzde_b") is not None else "—", delta=ind.get("bb_yorum", ""))
    hr = ind.get("hacim_oran")
    i4.metric("Hacim/Ort.", f"{hr:.2f}x" if hr else "—", delta="🔥 Yüksek hacim" if hr and hr > 1.5 else "📉 Düşük hacim" if hr and hr < 0.7 else "Normal")

    if fg_deger or btc_dom:
        p1, p2 = st.columns(2)
        if fg_deger:
            p1.metric("😨 Fear & Greed", f"{fg_deger} — {fg_yorum}")
        if btc_dom:
            p2.metric("₿ BTC Dominansı", f"%{btc_dom}", delta=f"Global MC 24s: %{mcap_degisim:.2f}" if mcap_degisim else "")

    st.markdown("---")
    coin_adi_str = secilen_lbl.split(" (")[0]
    coin_sym_str = secilen_lbl.split("(")[1].replace(")", "")
    if st.button("⭐ Takip Listesine Ekle"):
        basari, mesaj = add_to_watchlist(secilen_id, coin_adi_str, coin_sym_str, mevcut_fiyat, sinyal)
        if basari:
            st.success(f"✅ {coin_adi_str} takip listesine eklendi!")
            st.balloons()
        elif mesaj == "zaten_var":
            st.info("ℹ️ Bu coin zaten takip listende.")
        else:
            st.error(f"Hata: {mesaj}")

    s1, s2, s3 = st.columns(3)
    s1.metric("OBV Dengesi %", f"{obv_dengesi:.2f}%")
    s2.metric("Son OBV", f"{df_coin['OBV'].iloc[-1]:,.0f}")
    s3.metric("OBV Trendi", "📈 Yükseliyor" if df_coin["OBV"].iloc[-1] > df_coin["OBV_Trend"].iloc[-1] else "📉 Düşüyor")

    st.markdown("---")
    st.subheader("🧠 AI Guru — Bu Coin İçin Durum Tespiti")
    if st.button("🔮 AI Yorumu Al"):
        with st.spinner("🧠 Guru veriyi inceliyor..."):
            verimetni = f"""Coin: {coin_adi_str} ({coin_sym_str})
Fiyat: {mevcut_fiyat:,.6f}
24s Değişim: %{degisim_24h:.2f}
OBV Sinyali: {sinyal}
OBV Dengesi: {obv_dengesi:.2f}%
RSI: {ind.get('rsi')}
MACD: {ind.get('macd')}
MACD Sinyal: {ind.get('macd_sinyal')}
MACD Histogram: {ind.get('macd_histogram')}
Bollinger %B: {ind.get('bb_yuzde_b')}
Hacim Oranı: {ind.get('hacim_oran')}
Fear & Greed: {fg_deger} - {fg_yorum}
BTC Dominansı: {btc_dom}
Global MC 24s: {mcap_degisim}
"""
            yorum = get_guru_comment(verimetni)
        st.markdown(f'<div style="background:#8dc64722; border-left:4px solid #8dc647; padding:16px 20px; border-radius:6px; line-height:1.6;">{yorum}</div>', unsafe_allow_html=True)

def render_takip_listesi():
    st.write("Takipteki coinlerin performansını izleyin.")
    if st.button("🔄 Listeyi Güncelle"):
        st.session_state.watchlist_cache = get_watchlist()

    if not st.session_state.watchlist_cache:
        st.session_state.watchlist_cache = get_watchlist()

    takip_verisi = st.session_state.watchlist_cache
    if not takip_verisi:
        st.info("Henüz takip listene coin eklemedin.")
        return

    satirlar = []
    for kayit in takip_verisi:
        coin_id = kayit.get("coin_id")
        baslangic_fiyat = kayit.get("baslangic_fiyat", 0) or 0
        guncel_fiyat, degisim24h = get_current_price(coin_id)
        performans = ((guncel_fiyat - baslangic_fiyat) / baslangic_fiyat * 100) if baslangic_fiyat else 0
        satirlar.append({
            "Coin": kayit.get("coin_adi"),
            "Sembol": kayit.get("sembol"),
            "Eklenme": kayit.get("eklenme_tarihi"),
            "Başlangıç Fiyatı": baslangic_fiyat,
            "Güncel Fiyat": guncel_fiyat,
            "Performans %": round(performans, 2),
            "24s Değişim %": round(degisim24h, 2),
            "Başlangıç Sinyali": kayit.get("baslangic_sinyal"),
            "Güncel Sinyal": kayit.get("baslangic_sinyal"),
            "Sinyal Durumu": "Aynı",
            "coin_id": coin_id,
        })

    dftakip = pd.DataFrame(satirlar)
    if dftakip.empty:
        st.info("Henüz takip listene coin eklemedin.")
        return

    st.dataframe(
        dftakip[["Coin", "Sembol", "Eklenme", "Başlangıç Fiyatı", "Güncel Fiyat", "Performans %", "24s Değişim %", "Başlangıç Sinyali", "Güncel Sinyal", "Sinyal Durumu"]]
        .style.format({"Başlangıç Fiyatı": "{:,.6f}", "Güncel Fiyat": "{:,.6f}", "Performans %": "{:,.2f}", "24s Değişim %": "{:,.2f}"}),
        use_container_width=True,
        hide_index=True,
    )

    kazananlar = dftakip[dftakip["Performans %"] > 0]
    kaybedenler = dftakip[dftakip["Performans %"] < 0]
    degisenler = dftakip[dftakip["Sinyal Durumu"] != "Aynı"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Karda Olan", len(kazananlar))
    c2.metric("Zararda Olan", len(kaybedenler))
    c3.metric("Sinyali Değişen", len(degisenler))
    c4.metric("Ort. Performans", f"{dftakip['Performans %'].mean():.2f}")

    if st.button("Takipten Çıkar"):
        secenekler = {f"{r['Coin']} ({r['Sembol']})": r["coin_id"] for _, r in dftakip.iterrows()}
        secilen = st.selectbox("Takipten çıkarılacak coin", list(secenekler.keys()))
        if st.button("Onayla"):
            if remove_from_watchlist(secenekler[secilen]):
                st.success("Coin takip listesinden çıkarıldı.")
                st.session_state.watchlist_cache = get_watchlist()
                st.rerun()
            else:
                st.error("Bir hata oluştu.")

def main():
    sekme1, sekme2, sekme3 = st.tabs(["📡 Piyasa Tarama", "🔍 Coin Ara", "⭐ Takip Listesi"])
    with sekme1:
        render_piyasa_tarama()
    with sekme2:
        render_coin_ara()
    with sekme3:
        render_takip_listesi()

main()
