"""
indicators.py — Teknik İndikatör Hesaplamaları
─────────────────────────────────────────────
Bu modül tamamen saf hesaplama fonksiyonları içerir: pandas DataFrame alır,
sayı/DataFrame döndürür. Hiçbir Streamlit veya ağ çağrısı yoktur — bu yüzden
başka bir projede veya Jupyter'da da doğrudan kullanılabilir, test yazmak
da kolaydır.

Beklenen DataFrame şeması: 'Fiyat' ve 'Hacim' sütunları (günlük, kronolojik
sırada, index sıfırdan başlıyor). TradingView portu bölümündeki fonksiyonlar
ayrıca 'High' ve 'Low' sütunlarını da bekler (bkz. ohlc_hizala).
"""

import numpy as np
import pandas as pd


# ─── OBV (ON-BALANCE VOLUME) ────────────────────────────────────

def obv_hesapla(df: pd.DataFrame) -> pd.DataFrame:
    """OBV, OBV_Trend (5 günlük MA) ve OBV_EMA (5 günlük EMA) sütunlarını ekler."""
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


def obv_momentum_hesapla(df: pd.DataFrame, periyot: int = 5) -> float:
    if len(df) < periyot + 1:
        return 0.0
    payda = abs(df['OBV'].iloc[-periyot - 1]) + 1
    return (df['OBV'].iloc[-1] - df['OBV'].iloc[-periyot - 1]) / payda


def uyumsuzluk_kontrol_et(df: pd.DataFrame, periyot: int, hassasiyet: str = "Orta") -> str:
    """Fiyat ile OBV arasındaki uyum/uyumsuzluğa göre sinyal metni üretir."""
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


def obv_hacim_dengesi(df: pd.DataFrame, periyot: int = 7) -> float:
    if len(df) < periyot:
        return 0.0
    net_hacim    = df['OBV'].iloc[-1] - df['OBV'].iloc[-periyot]
    toplam_hacim = df['Hacim'].iloc[-periyot:].sum()
    return (net_hacim / toplam_hacim * 100) if toplam_hacim > 0 else 0.0


# ─── RSI ──────────────────────────────────────────────────────────

def rsi_hesapla(df: pd.DataFrame, periyot: int = 14):
    """RSI (Relative Strength Index) hesaplar. Yetersiz veride None döner."""
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


def rsi_yorumla(rsi) -> str:
    if rsi is None: return "Veri yetersiz"
    if rsi >= 70:   return "Aşırı Alım Bölgesi"
    if rsi >= 60:   return "Güçlü Bölge"
    if rsi >= 40:   return "Nötr Bölge"
    if rsi >= 30:   return "Zayıf Bölge"
    return "Aşırı Satım Bölgesi"


# ─── MACD ─────────────────────────────────────────────────────────

def macd_hesapla(df: pd.DataFrame):
    """MACD çizgisi, sinyal çizgisi ve histogram döndürür. Yetersiz veride (None, None, None)."""
    if len(df) < 26:
        return None, None, None
    ema12     = df['Fiyat'].ewm(span=12, adjust=False).mean()
    ema26     = df['Fiyat'].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sinyal    = macd_line.ewm(span=9, adjust=False).mean()
    histogram = macd_line - sinyal
    return (
        round(float(macd_line.iloc[-1]), 6),
        round(float(sinyal.iloc[-1]), 6),
        round(float(histogram.iloc[-1]), 6),
    )


def macd_yorumla(macd, macd_sinyal, macd_hist) -> str:
    if macd is None:
        return "Veri yetersiz"
    if macd > macd_sinyal and macd_hist > 0:
        return "Yükseliş sinyali (MACD sinyal üzerinde, histogram pozitif)"
    if macd < macd_sinyal and macd_hist < 0:
        return "Düşüş sinyali (MACD sinyal altında, histogram negatif)"
    if macd > 0:
        return "Pozitif bölge ama momentum zayıflıyor"
    return "Negatif bölge ama momentum güçleniyor"


# ─── BOLLİNGER BANDS ─────────────────────────────────────────────

def bollinger_hesapla(df: pd.DataFrame, periyot: int = 20, std_katsayi: float = 2):
    """Üst/orta/alt bant ve %B (fiyatın bant içindeki konumu) döndürür."""
    if len(df) < periyot:
        return None, None, None, None
    ort       = df['Fiyat'].rolling(window=periyot).mean()
    std       = df['Fiyat'].rolling(window=periyot).std()
    ust_band  = ort + std_katsayi * std
    alt_band  = ort - std_katsayi * std
    son_fiyat = df['Fiyat'].iloc[-1]
    bant_genisligi = float(ust_band.iloc[-1] - alt_band.iloc[-1])
    yuzde_b = (son_fiyat - float(alt_band.iloc[-1])) / (bant_genisligi + 1e-12)
    return (
        round(float(ust_band.iloc[-1]), 6),
        round(float(ort.iloc[-1]), 6),
        round(float(alt_band.iloc[-1]), 6),
        round(yuzde_b, 3),
    )


def bollinger_yorumla(bb_yuzde_b) -> str:
    if bb_yuzde_b is None: return "Veri yetersiz"
    if bb_yuzde_b > 1:     return "Üst Bandın Üzerinde (Aşırı alım)"
    if bb_yuzde_b > 0.8:   return "Üst Banda Yakın"
    if bb_yuzde_b > 0.5:   return "Orta-Üst Bölge"
    if bb_yuzde_b > 0.2:   return "Orta-Alt Bölge"
    if bb_yuzde_b > 0:     return "Alt Banda Yakın"
    return "Alt Bandın Altında (Aşırı satım)"


# ─── HACİM ANALİZİ ───────────────────────────────────────────────

def hacim_analizi(df: pd.DataFrame, periyot: int = 7):
    """Son hacmin, periyot ortalamasına oranını döndürür (ort_hacim, oran)."""
    if len(df) < periyot + 1:
        return None, None
    ort_hacim  = df['Hacim'].iloc[-periyot:].mean()
    son_hacim  = df['Hacim'].iloc[-1]
    hacim_oran = son_hacim / (ort_hacim + 1e-12)
    return round(float(ort_hacim), 0), round(float(hacim_oran), 2)


# ─── TÜMÜNÜ TEK SEFERDE HESAPLA ─────────────────────────────────

def tum_indiktorleri_hesapla(df: pd.DataFrame, periyot: int = 7) -> dict:
    """RSI, MACD, Bollinger ve hacim analizini tek dict içinde, yorumlarıyla birlikte döndürür."""
    rsi = rsi_hesapla(df)
    macd, macd_sinyal, macd_hist = macd_hesapla(df)
    bb_ust, bb_orta, bb_alt, bb_yuzde_b = bollinger_hesapla(df)
    ort_hacim, hacim_oran = hacim_analizi(df, periyot)

    return {
        "rsi":            rsi,
        "rsi_yorum":      rsi_yorumla(rsi),
        "macd":           macd,
        "macd_sinyal":    macd_sinyal,
        "macd_histogram": macd_hist,
        "macd_yorum":     macd_yorumla(macd, macd_sinyal, macd_hist),
        "bb_ust":         bb_ust,
        "bb_orta":        bb_orta,
        "bb_alt":         bb_alt,
        "bb_yuzde_b":     bb_yuzde_b,
        "bb_yorum":       bollinger_yorumla(bb_yuzde_b),
        "ort_hacim":      ort_hacim,
        "hacim_oran":     hacim_oran,
    }


# ═══════════════════════════════════════════════════════════════════
# TRADINGVIEW "OBV MACD INDICATOR" PORTU (Pine Script v4 → pandas)
# ═══════════════════════════════════════════════════════════════════
# Orijinal göstergedeki üç aşama birebir taşındı:
#   1) obv_sentetik_fiyat()   → Pine'daki 'out' serisi (OBV sapmasını High/Low
#                                volatilitesiyle ölçekleyip fiyat gibi kullanan seri)
#   2) tv_macd_hesapla()      → Pine'daki 'macd = ma - slow_ma' (ma = DEMA/TEMA/EMA
#                                bu sentetik seri üzerinde, slow_ma = EMA(close,26))
#   3) tv_linreg_projeksiyon()+tv_tchannel() → Pine'daki calcSlope()/tt1 ve
#                                T-Channel adaptif baseline + yön (oc) mantığı
#
# NOT: Bu fonksiyonlar 'High' ve 'Low' sütunu ister — CoinGecko'nun /market_chart
# uç noktası bunları vermez, /ohlc uç noktasından ayrıca çekilip ohlc_hizala()
# ile günlük df'e hizalanmalıdır (bkz. data.coin_ohlc_istegi).

def _dema(series: pd.Series, length: int) -> pd.Series:
    ema1 = series.ewm(span=length, adjust=False).mean()
    ema2 = ema1.ewm(span=length, adjust=False).mean()
    return 2 * ema1 - ema2


def _tema(series: pd.Series, length: int) -> pd.Series:
    ema1 = series.ewm(span=length, adjust=False).mean()
    ema2 = ema1.ewm(span=length, adjust=False).mean()
    ema3 = ema2.ewm(span=length, adjust=False).mean()
    return 3 * (ema1 - ema2) + ema3


def _tv_myma(series: pd.Series, length: int, tip: str = "DEMA") -> pd.Series:
    """Pine'daki myma() seçicisinin en sık kullanılan 3 türü (EMA/DEMA/TEMA).
    Orijinal script'te 14 tip var; gösterge varsayılanı DEMA olduğu için
    diğerleri (ZLEMA, HMA türevleri vb.) burada taşınmadı, gerekirse eklenebilir."""
    tip = (tip or "DEMA").upper()
    if tip == "EMA":
        return series.ewm(span=length, adjust=False).mean()
    if tip == "TEMA":
        return _tema(series, length)
    return _dema(series, length)


def ohlc_hizala(df: pd.DataFrame, ohlc_liste: list, ts_kolon: str = "ts") -> pd.DataFrame:
    """CoinGecko /ohlc uç noktasından gelen [ts_ms, open, high, low, close]
    listesini, zaten bir 'ts' (datetime) sütunu içeren günlük df'e en yakın
    zaman damgasına göre hizalayıp 'High'/'Low' sütunlarını ekler.

    df: 'ts' (datetime64), 'Fiyat', 'Hacim' sütunlarını içermeli.
    ohlc_liste: data.coin_ohlc_istegi(...).json() çıktısı.

    CoinGecko /ohlc, istenen gün sayısına göre farklı mum genişliği döndürür
    (1-2 gün: 30dk, 3-30 gün: 4 saat, 31+ gün: 4 gün) — bu yüzden birebir
    zaman eşleşmesi yerine en yakın mum kullanılır (direction='nearest')."""
    df = df.copy()
    if not ohlc_liste or ts_kolon not in df.columns:
        df['High'] = df['Fiyat']
        df['Low']  = df['Fiyat']
        return df

    df_ohlc = pd.DataFrame(ohlc_liste, columns=['ts_ms', 'Open', 'High', 'Low', 'Close'])
    df_ohlc['ts'] = pd.to_datetime(df_ohlc['ts_ms'], unit='ms').astype('datetime64[ns]')
    df_ohlc = df_ohlc[['ts', 'High', 'Low']].sort_values('ts').reset_index(drop=True)

    df = df.sort_values(ts_kolon).reset_index(drop=True)
    df[ts_kolon] = pd.to_datetime(df[ts_kolon]).astype('datetime64[ns]')
    hizali = pd.merge_asof(df, df_ohlc, left_on=ts_kolon, right_on='ts', direction='nearest')
    hizali = hizali.drop(columns=['ts']) if 'ts' in hizali.columns and ts_kolon != 'ts' else hizali
    hizali['High'] = hizali['High'].fillna(hizali['Fiyat'])
    hizali['Low']  = hizali['Low'].fillna(hizali['Fiyat'])
    return hizali


def obv_cum_seri(df: pd.DataFrame) -> pd.Series:
    """Pine: v = cum(sign(change(close)) * volume).
    Not: Bu, obv_hesapla()'daki 'OBV' sütunuyla matematiksel olarak eşdeğerdir;
    TradingView portu kendi içinde bağımsız çalışabilsin diye ayrıca tanımlandı."""
    fark   = df['Fiyat'].diff()
    isaret = np.sign(fark).fillna(0)
    return (isaret * df['Hacim']).cumsum()


def obv_sentetik_fiyat(df: pd.DataFrame, window_len: int = 28, v_len: int = 14) -> pd.Series:
    """Pine: v, smooth, v_spread, price_spread, shadow, out satırlarının karşılığı.
    OBV'nin kendi 14 periyotluk ortalamasından sapmasını, fiyatın 28 periyotluk
    High-Low volatilitesiyle ölçeklendirip High veya Low'a ekleyerek sentetik
    bir fiyat serisi üretir ('out')."""
    for kolon in ('High', 'Low'):
        if kolon not in df.columns:
            raise ValueError(
                f"obv_sentetik_fiyat için '{kolon}' sütunu gerekli — önce ohlc_hizala() ile ekleyin."
            )
    v            = obv_cum_seri(df)
    smooth       = v.rolling(v_len, min_periods=1).mean()
    v_spread     = (v - smooth).rolling(window_len, min_periods=2).std(ddof=0)
    price_spread = (df['High'] - df['Low']).rolling(window_len, min_periods=2).std(ddof=0)
    shadow       = (v - smooth) / v_spread.replace(0, np.nan) * price_spread
    out          = np.where(shadow > 0, df['High'] + shadow, df['Low'] + shadow)
    return pd.Series(out, index=df.index)


def tv_macd_hesapla(df: pd.DataFrame, dema_len: int = 9, slow_len: int = 26,
                     window_len: int = 28, v_len: int = 14, obv_ema_len: int = 1,
                     ma_tipi: str = "DEMA") -> pd.Series:
    """Pine: ma = myma(obvema, len) ; slow_ma = ema(close, 26) ; macd = ma - slow_ma.
    obv_ema_len=1 iken Pine'daki ema(out,1) satırı matematiksel olarak out'un
    kendisine eşittir (span=1 EMA fark yaratmaz), o yüzden varsayılan geçişte
    doğrudan 'out' kullanılır."""
    out    = obv_sentetik_fiyat(df, window_len, v_len)
    obvema = out if obv_ema_len <= 1 else out.ewm(span=obv_ema_len, adjust=False).mean()
    ma      = _tv_myma(obvema, dema_len, ma_tipi)
    slow_ma = df['Fiyat'].ewm(span=slow_len, adjust=False).mean()
    return ma - slow_ma


def tv_linreg_projeksiyon(seri: pd.Series, uzunluk: int = 2, offset: int = 0) -> pd.Series:
    """Pine: calcSlope(src5, len5) → tt1 = intercept + slope*(len5-offset).
    Son `uzunluk` bar üzerinde ağırlıklı lineer regresyon uygulayıp projekte
    edilmiş değeri döndürür (varsayılan uzunluk=2, offset=0 ile tt1 == seri,
    bu Pine kodundaki algebrik bir özdeşliktir — script'i len5>2 ile
    kullananlar için genel biçimde bırakıldı)."""
    vals = seri.values.astype(float)
    n = len(vals)
    tt1 = np.full(n, np.nan)
    for idx in range(n):
        if idx - (uzunluk - 1) < 0:
            continue
        pencere = vals[idx - uzunluk + 1: idx + 1]
        if np.isnan(pencere).any():
            continue
        sumX = sumY = sumXSqr = sumXY = 0.0
        for i in range(1, uzunluk + 1):
            bars_ago = uzunluk - i
            val = vals[idx - bars_ago]
            per = i + 1.0
            sumX    += per
            sumY    += val
            sumXSqr += per * per
            sumXY   += val * per
        denom = uzunluk * sumXSqr - sumX * sumX
        if denom == 0:
            continue
        slope     = (uzunluk * sumXY - sumX * sumY) / denom
        average   = sumY / uzunluk
        intercept = average - slope * sumX / uzunluk + slope
        tt1[idx]  = intercept + slope * (uzunluk - offset)
    return pd.Series(tt1, index=seri.index)


def tv_tchannel(tt1: pd.Series, p: float = 1.0):
    """Pine: b5/dev5/oc satırlarının karşılığı (T-Channel).
    b5: adaptif baseline — sadece kümülatif ortalama mutlak sapma eşiğini (a15)
        aşan hareketlerde yeniden konumlanır.
    oc: yön — 1 = yükseliş (mavi), -1 = düşüş (kırmızı).

    NOT: Pine'daki n5 = cum(1)-1, TradingView grafiğindeki TOPLAM bar sayısına
    dayalı global bir sayaçtır (chart'ın en başından itibaren). Sınırlı pencereli
    (35-90 günlük) bir taramada bunun tam karşılığı yoktur; burada df'in kendi
    bar index'i (idx) kullanılır — bu, script'in tek bir grafik üzerinde baştan
    çalıştırılmasıyla en tutarlı yorumdur."""
    vals = tt1.values.astype(float)
    n = len(vals)
    b5  = np.full(n, np.nan)
    oc  = np.zeros(n)
    dev5 = np.full(n, np.nan)
    cum_abs_dev = 0.0

    for idx in range(n):
        if np.isnan(vals[idx]):
            continue
        onceki_gecersiz = np.isnan(b5[idx - 1]) if idx > 0 else True
        if onceki_gecersiz:
            b5[idx]   = vals[idx]
            oc[idx]   = oc[idx - 1] if idx > 0 else 0
            dev5[idx] = dev5[idx - 1] if (idx > 0 and not np.isnan(dev5[idx - 1])) else 0.0
            continue

        prev_b5 = b5[idx - 1]
        n5 = idx
        cum_abs_dev += abs(vals[idx] - prev_b5)
        a15 = (cum_abs_dev / n5 * p) if n5 > 0 else 0.0

        if vals[idx] > prev_b5 + a15:
            b5[idx] = vals[idx]
        elif vals[idx] < prev_b5 - a15:
            b5[idx] = vals[idx]
        else:
            b5[idx] = prev_b5

        if b5[idx] != prev_b5:
            dev5[idx] = a15
            oc[idx]   = 1 if b5[idx] > prev_b5 else -1
        else:
            dev5[idx] = dev5[idx - 1] if not np.isnan(dev5[idx - 1]) else a15
            oc[idx]   = oc[idx - 1]

    return pd.Series(b5, index=tt1.index), pd.Series(oc, index=tt1.index)


def tv_tchannel_sinyali_uret(oc: pd.Series) -> str:
    """Son bardaki T-Channel yönünü ve varsa taze bir dönüşü (flip) okunabilir
    Türkçe metne çevirir — uyumsuzluk_kontrol_et() ile aynı formatta, tarayıcı
    tablosunda doğrudan kullanılabilir."""
    if oc.empty or len(oc) < 2 or pd.isna(oc.iloc[-1]) or pd.isna(oc.iloc[-2]):
        return "Yetersiz Veri"
    son     = oc.iloc[-1]
    onceki  = oc.iloc[-2]
    flip    = son - onceki
    if flip > 0:
        return "🔵 T-CHANNEL AL (Yön Yeni Döndü ↑)"
    if flip < 0:
        return "🔴 T-CHANNEL SAT (Yön Yeni Döndü ↓)"
    if son == 1:
        return "🔵 T-Channel Yükseliş Trendi"
    if son == -1:
        return "🔴 T-Channel Düşüş Trendi"
    return "⚪ T-Channel Belirsiz"


def tv_obv_macd_tchannel_analiz_et(df: pd.DataFrame, dema_len: int = 9, slow_len: int = 26,
                                    window_len: int = 28, v_len: int = 14,
                                    reg_len: int = 2, ma_tipi: str = "DEMA") -> dict:
    """TradingView göstergesinin tamamını (OBV sentetik fiyat → MACD → lineer
    regresyon projeksiyonu → T-Channel) tek çağrıda çalıştırır.

    df en az 'Fiyat', 'Hacim', 'High', 'Low' sütunlarını içermeli
    (bkz. ohlc_hizala). Varsayılan parametreler Pine script'teki
    varsayılanlarla birebir aynıdır (window_len=28, v_len=14, dema_len=9,
    slow_len=26, reg_len=2, ma_tipi=DEMA)."""
    macd = tv_macd_hesapla(df, dema_len, slow_len, window_len, v_len, ma_tipi=ma_tipi)
    tt1  = tv_linreg_projeksiyon(macd, reg_len)
    baseline, oc = tv_tchannel(tt1)
    sinyal = tv_tchannel_sinyali_uret(oc)

    return {
        "macd_tv":        macd,
        "tt1":            tt1,
        "baseline":       baseline,
        "yon":            oc,
        "sinyal":         sinyal,
        "son_yon_deger":  None if oc.empty or pd.isna(oc.iloc[-1]) else int(oc.iloc[-1]),
    }
