"""
app.py — OBV Derinlik Tarayıcı
─────────────────────────────
Sadece UI orkestrasyonu. Tüm hesaplama/veri/AI mantığı şu modüllerden gelir:
    data.py        → CoinGecko + Supabase + piyasa bağlamı
    indicators.py  → OBV, RSI, MACD, Bollinger
    ai.py          → Groq tabanlı AI Guru
    styles.py      → CSS, HTML bileşenleri, Plotly teması
"""

import time
import pandas as pd
import streamlit as st

import data
import indicators as ind
import ai
import styles as ui


# ─── SAYFA AYARLARI ──────────────────────────────────────────────
st.set_page_config(page_title="OBV Derinlik Tarayıcı", layout="wide", page_icon="🐋")
ui.inject_global_styles()

ui.render_header(
    eyebrow="Canlı Tarama · CoinGecko + Groq AI",
    title="🐋 OBV Derinlik Tarayıcı",
    subtitle="Fiyat hareketlerini gerçek hacim akışıyla doğrulayan balina tespit sistemi.",
)


# ─── SIDEBAR — KONTROL PANELİ ────────────────────────────────────
df_kategoriler = data.kategorileri_getir()

st.sidebar.markdown('<div class="obv-sidebar-label">📡 Tarama Kapsamı</div>', unsafe_allow_html=True)

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

tarama_sayisi = st.sidebar.number_input("Kaç coin taransın?", min_value=5, max_value=250, value=50, step=5)

st.sidebar.markdown('<div class="obv-sidebar-label">⚙️ OBV Hassasiyeti</div>', unsafe_allow_html=True)

analiz_periyodu = st.sidebar.slider("OBV Kaç Günlük Trende Baksın?", 3, 30, 7, step=1)
obv_hassasiyet  = st.sidebar.select_slider(
    "OBV Hassasiyeti", options=["Düşük", "Orta", "Yüksek"], value="Orta",
    help="Düşük = sadece güçlü sinyaller | Yüksek = daha fazla sinyal üretir"
)

st.sidebar.markdown("<br>", unsafe_allow_html=True)
tarama_butonu = st.sidebar.button("Piyasayı Canlı Tara 🚀", use_container_width=True)


# ─── SESSION STATE ────────────────────────────────────────────────
if 'tarama_ham' not in st.session_state:
    st.session_state['tarama_ham'] = []
if 'df_sonuc' not in st.session_state:
    st.session_state['df_sonuc'] = pd.DataFrame()
if 'tab2_analiz' not in st.session_state:
    st.session_state['tab2_analiz'] = None


# ─── ANA SEKMELER ─────────────────────────────────────────────────
sekme1, sekme2, sekme3 = st.tabs(["📡 Piyasa Tarama", "🔍 Coin Ara", "⭐ Takip Listesi"])


# ════════════════════════════════════════════════════════════════
# SEKME 1 — PİYASA TARAMA
# ════════════════════════════════════════════════════════════════
with sekme1:
    st.write("Fiyat hareketlerini gerçek hacim trendleriyle doğrulayarak balina akümülasyonunu kategorilere göre filtreleyin.")

    if tarama_butonu:
        st.info("🔄 Coin listesi CoinGecko'dan çekiliyor...")

        try:
            res = data.piyasa_taramasi_istegi(
                siralam_map.get(siralam_secimi, "market_cap_desc"),
                tarama_sayisi,
                secilen_kategori_id,
            )
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
                chart_res = data.coin_grafik_istegi(coin_id, days=35)

                if chart_res.status_code == 200:
                    chart_data = chart_res.json()
                    fiyatlar   = [o[1] for o in chart_data.get('prices', [])]
                    hacimler   = [o[1] for o in chart_data.get('total_volumes', [])]

                    if fiyatlar and hacimler:
                        df_coin     = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                        df_coin     = ind.obv_hesapla(df_coin)
                        sinyal      = ind.uyumsuzluk_kontrol_et(df_coin, analiz_periyodu, obv_hassasiyet)
                        obv_dengesi = ind.obv_hacim_dengesi(df_coin, analiz_periyodu)

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
        st.session_state['df_sonuc'] = pd.DataFrame(sonuc_tablosu)

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
            }).map(ui.style_signal_cell, subset=['OBV Sinyali']),
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
                basari, mesaj = data.takibe_ekle(
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

                yorum = ai.guru_yorumu_uret(veri_metni)

            ui.render_guru_card(yorum, renk=ui.ACCENT)


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
            sonuclar = data.coin_ara(arama_metni)

        if not sonuclar:
            st.warning("Sonuç bulunamadı.")
        else:
            secenekler = {f"{c['name']} ({c['symbol'].upper()})": c['id'] for c in sonuclar[:8]}
            secilen    = st.selectbox("Sonuçlar:", list(secenekler.keys()))
            secilen_id = secenekler[secilen]

            if st.button("📊 Analiz Et"):
                with st.spinner("📡 Veri çekiliyor..."):
                    chart_data = data.coin_detay_getir(secilen_id, grafik_gun)
                    coin_bilgi = data.coin_bilgi_getir(secilen_id)

                if not chart_data:
                    st.error("Veri çekilemedi.")
                    st.session_state['tab2_analiz'] = None
                else:
                    fiyatlar = [o[1] for o in chart_data.get('prices', [])]
                    hacimler = [o[1] for o in chart_data.get('total_volumes', [])]
                    df_coin     = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                    df_coin     = ind.obv_hesapla(df_coin)
                    periyot     = min(analiz_periyodu, len(df_coin) - 1)
                    sinyal      = ind.uyumsuzluk_kontrol_et(df_coin, periyot, obv_hassasiyet)
                    obv_dengesi = ind.obv_hacim_dengesi(df_coin, periyot)

                    # Teknik indikatörler + piyasa bağlamı
                    indiktorler = ind.tum_indiktorleri_hesapla(df_coin, periyot)
                    fg_deger, fg_yorum   = data.fear_greed_getir()
                    btc_dom, mcap_degisim = data.btc_dominans_getir()

                    st.session_state['tab2_analiz'] = {
                        "secilen_id":   secilen_id,
                        "secilen":      secilen,
                        "df_coin":      df_coin,
                        "sinyal":       sinyal,
                        "coin_bilgi":   coin_bilgi,
                        "obv_dengesi":  obv_dengesi,
                        "periyot":      periyot,
                        "indiktorler":  indiktorler,
                        "fg_deger":     fg_deger,
                        "fg_yorum":     fg_yorum,
                        "btc_dom":      btc_dom,
                        "mcap_degisim": mcap_degisim,
                    }

            # ─── KAYITLI ANALİZİ GÖSTER (seçili coin'e aitse) ────────────
            analiz = st.session_state.get('tab2_analiz')
            if analiz and analiz.get("secilen_id") == secilen_id:
                df_coin      = analiz["df_coin"]
                sinyal       = analiz["sinyal"]
                coin_bilgi   = analiz["coin_bilgi"]
                obv_dengesi  = analiz["obv_dengesi"]
                secilen_lbl  = analiz["secilen"]
                indiktorler  = analiz.get("indiktorler", {})
                fg_deger     = analiz.get("fg_deger")
                fg_yorum     = analiz.get("fg_yorum")
                btc_dom      = analiz.get("btc_dom")
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

                ui.render_signal_banner(sinyal)
                banner_renk = ui.get_signal_color(sinyal)

                st.plotly_chart(ui.obv_grafigi_ciz(df_coin, secilen_lbl, sinyal), use_container_width=True)

                # ─── TEKNİK İNDİKATÖR PANELİ ─────────────────────
                st.markdown("---")
                st.subheader("📐 Teknik İndikatörler")
                i1, i2, i3, i4 = st.columns(4)

                rsi_val = indiktorler.get('rsi')
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

                if fg_deger or btc_dom:
                    p1, p2 = st.columns(2)
                    if fg_deger:
                        p1.metric("😨 Fear & Greed", f"{fg_deger} — {fg_yorum}")
                    if btc_dom:
                        p2.metric("₿ BTC Dominansı", f"%{btc_dom}",
                                  delta=f"Global MC 24s: %{mcap_degisim:.2f}" if mcap_degisim else "")

                if indiktorler.get('rsi') is None:
                    st.caption(f"ℹ️ RSI/MACD/Bollinger için en az 30 günlük veri gerekir. "
                               f"Şu an {grafik_gun} gün seçili — daha geniş indikatör görünümü için "
                               f"Gün Aralığı'nı 30+ yapabilirsin.")

                # Takibe al butonu
                st.markdown("---")
                coin_adi_str = secilen_lbl.split(" (")[0]
                coin_sym_str = secilen_lbl.split("(")[1].replace(")", "")
                fiyat_str    = mevcut_fiyat

                if st.button("⭐ Takip Listesine Ekle", use_container_width=False):
                    basari, mesaj = data.takibe_ekle(secilen_id, coin_adi_str, coin_sym_str, fiyat_str, sinyal)
                    if basari:
                        st.success(f"✅ {coin_adi_str} takip listesine eklendi!")
                        st.balloons()
                    elif mesaj == "zaten_var":
                        st.info("ℹ️ Bu coin zaten takip listende.")
                    else:
                        st.error(f"Hata: {mesaj}")

                # OBV istatistikleri
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
RSI (14): {indiktorler.get('rsi', 'N/A')} — {indiktorler.get('rsi_yorum', 'N/A')}
MACD: {indiktorler.get('macd', 'N/A')} | Sinyal: {indiktorler.get('macd_sinyal', 'N/A')} | Histogram: {indiktorler.get('macd_histogram', 'N/A')}
MACD Durumu: {indiktorler.get('macd_yorum', 'N/A')}
Bollinger Üst Band: {indiktorler.get('bb_ust', 'N/A')} | Orta: {indiktorler.get('bb_orta', 'N/A')} | Alt: {indiktorler.get('bb_alt', 'N/A')}
Bollinger %B: {indiktorler.get('bb_yuzde_b', 'N/A')} — {indiktorler.get('bb_yorum', 'N/A')}
Son Hacim / Ortalama Hacim: {indiktorler.get('hacim_oran', 'N/A')}x

=== PİYASA BAĞLAMI ===
Fear & Greed Index: {fg_deger if fg_deger else 'N/A'} ({fg_yorum if fg_yorum else 'N/A'})
BTC Dominansı: %{btc_dom if btc_dom else 'N/A'}
Global Market Cap 24s Değişim: %{mcap_degisim if mcap_degisim else 'N/A'}

Tüm bu verileri birlikte yorumlayarak kapsamlı bir teknik analiz durum tespiti yap.
OBV, RSI, MACD ve Bollinger sinyallerinin birbirini teyit edip etmediğini özellikle belirt."""

                        yorum = ai.guru_yorumu_uret(veri_metni)

                    ui.render_guru_card(yorum, renk=banner_renk)


# ════════════════════════════════════════════════════════════════
# SEKME 3 — TAKİP LİSTESİ
# ════════════════════════════════════════════════════════════════
with sekme3:
    st.subheader("⭐ Takip Listesi")
    st.write("Takipteki coinlerin başlangıç sinyali ve fiyatına göre performansını izle.")

    col_yenile, col_bos = st.columns([1, 4])
    with col_yenile:
        st.button("🔄 Listeyi Güncelle", use_container_width=True)

    takip_verisi = data.takip_listesi_getir()

    if not takip_verisi:
        st.info("Henüz takip listene coin eklemedin. Tarama veya Coin Ara sekmesinden ekleyebilirsin.")
    else:
        st.success(f"📋 {len(takip_verisi)} coin takip ediliyor.")

        tablo_satirlari = []

        with st.spinner("📡 Güncel fiyatlar çekiliyor..."):
            for kayit in takip_verisi:
                coin_id         = kayit['coin_id']
                baslangic_fiyat = kayit.get('baslangic_fiyat', 0) or 0
                guncel_fiyat, degisim_24h = data.guncel_fiyat_getir(coin_id)

                if baslangic_fiyat > 0 and guncel_fiyat > 0:
                    performans = ((guncel_fiyat - baslangic_fiyat) / baslangic_fiyat) * 100
                else:
                    performans = 0

                chart_data = data.coin_detay_getir(coin_id, 35)
                guncel_sinyal = "—"
                if chart_data:
                    fiyatlar = [o[1] for o in chart_data.get('prices', [])]
                    hacimler = [o[1] for o in chart_data.get('total_volumes', [])]
                    if fiyatlar and hacimler:
                        df_c = pd.DataFrame({"Fiyat": fiyatlar, "Hacim": hacimler})
                        df_c = ind.obv_hesapla(df_c)
                        guncel_sinyal = ind.uyumsuzluk_kontrol_et(df_c, analiz_periyodu, obv_hassasiyet)

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

            st.dataframe(
                df_takip[["Coin","Sembol","Eklenme","Başlangıç Fiyat","Güncel Fiyat",
                           "Performans %","24s Değişim %","Başlangıç Sinyali","Güncel Sinyal","Sinyal Durumu"]]
                .style.format({
                    "Başlangıç Fiyat": "{:,.6f}",
                    "Güncel Fiyat":    "{:,.6f}",
                    "Performans %":    "{:+.2f}",
                    "24s Değişim %":   "{:+.2f}",
                })
                .map(ui.style_performance_cell, subset=["Performans %"])
                .map(ui.style_signal_cell, subset=["Başlangıç Sinyali", "Güncel Sinyal"]),
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
                m4.metric("📊 Ort. Performans", f"%{df_takip['Performans %'].mean():+.2f}")

            # Takipten çıkar
            st.markdown("---")
            st.subheader("🗑️ Takipten Çıkar")
            cikar_secenekler = {f"{r['Coin']} ({r['Sembol']})": r['_coin_id'] for _, r in df_takip.iterrows()}
            secilen_cikar    = st.selectbox("Takipten çıkarılacak coin:", list(cikar_secenekler.keys()))
            if st.button("🗑️ Takipten Çıkar", use_container_width=False):
                if data.takipten_cikar(cikar_secenekler[secilen_cikar]):
                    st.success(f"✅ {secilen_cikar} takip listesinden çıkarıldı.")
                    st.rerun()
                else:
                    st.error("Bir hata oluştu.")
