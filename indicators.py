"""
indicators.py — Teknik İndikatör Hesaplamaları
─────────────────────────────────────────────
Bu modül tamamen saf hesaplama fonksiyonları içerir: pandas DataFrame alır,
sayı/DataFrame döndürür. Hiçbir Streamlit veya ağ çağrısı yoktur — bu yüzden
başka bir projede veya Jupyter'da da doğrudan kullanılabilir, test yazmak
da kolaydır.

Beklenen DataFrame şeması: 'Fiyat' ve 'Hacim' sütunları (günlük, kronolojik
sırada, index sıfırdan başlıyor).
"""

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
