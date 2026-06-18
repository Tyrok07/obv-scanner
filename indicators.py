import pandas as pd

def calculate_obv(df):
    if len(df) < 2:
        df["OBV"] = 0
        df["OBV_Trend"] = 0
        df["OBV_EMA"] = 0
        return df

    obv = [0]
    for i in range(1, len(df)):
        diff = df.loc[i, "Fiyat"] - df.loc[i - 1, "Fiyat"]
        vol = df.loc[i, "Hacim"]
        if diff > 0:
            obv.append(obv[-1] + vol)
        elif diff < 0:
            obv.append(obv[-1] - vol)
        else:
            obv.append(obv[-1])

    df["OBV"] = obv
    df["OBV_Trend"] = df["OBV"].rolling(window=5, min_periods=1).mean()
    df["OBV_EMA"] = df["OBV"].ewm(span=5, adjust=False).mean()
    return df

def obv_balance(df, periyot=7):
    if len(df) < periyot + 1:
        return 0
    net = df["OBV"].iloc[-1] - df["OBV"].iloc[-periyot]
    total = df["Hacim"].iloc[-periyot:].sum()
    return (net / total * 100) if total > 0 else 0

def obv_signal(df, periyot=7, hassasiyet="Orta"):
    if len(df) < periyot + 1:
        return "Yetersiz Veri"
    threshold = {"Düşük": 3.0, "Orta": 1.5, "Yüksek": 0.5}.get(hassasiyet, 1.5)

    curr_price = df["Fiyat"].iloc[-1]
    prev_price = df["Fiyat"].iloc[-periyot]
    curr_obv = df["OBV"].iloc[-1]
    prev_obv = df["OBV"].iloc[-periyot]

    price_pct = ((curr_price - prev_price) / (prev_price + 1e-12)) * 100
    obv_pct = ((curr_obv - prev_obv) / (abs(prev_obv) + 1)) * 100

    if price_pct < -threshold and obv_pct > threshold:
        return "🔵 GÜÇLÜ POZİTİF (Ağır Balina Topluyor)" if obv_pct > abs(price_pct) * 2 else "🔵 POZİTİF (Balina Topluyor)"
    if price_pct > threshold and obv_pct < -threshold:
        return "🔴 GÜÇLÜ NEGATİF (Büyük Dağıtım)" if abs(obv_pct) > price_pct else "🔴 NEGATİF (Sahte Yükseliş)"
    if price_pct > threshold and obv_pct > threshold:
        return "🟢 GÜÇLÜ YÜKSELİŞ (Hacim Destekli)"
    if price_pct < -threshold and obv_pct < -threshold:
        return "🔻 GÜÇLÜ DÜŞÜŞ (Hacim Destekli)"

    trend = df["OBV_Trend"].iloc[-1]
    if curr_obv > trend:
        return "⚪ Nötr (OBV Yükselme Eğilimli)"
    if curr_obv < trend:
        return "⚪ Nötr (OBV Düşme Eğilimli)"
    return "⚪ Nötr"

def _rsi(df, period=14):
    if len(df) < period + 1:
        return None
    delta = df["Fiyat"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / (avg_loss + 1e-12)
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi.iloc[-1]), 2)

def _macd(df):
    if len(df) < 26:
        return None, None, None
    ema12 = df["Fiyat"].ewm(span=12, adjust=False).mean()
    ema26 = df["Fiyat"].ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return round(float(macd_line.iloc[-1]), 6), round(float(signal.iloc[-1]), 6), round(float(hist.iloc[-1]), 6)

def _bollinger(df, period=20, std_mult=2):
    if len(df) < period:
        return None, None, None, None
    mid = df["Fiyat"].rolling(window=period).mean()
    std = df["Fiyat"].rolling(window=period).std()
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    width = float(upper.iloc[-1] - lower.iloc[-1])
    pct_b = (df["Fiyat"].iloc[-1] - float(lower.iloc[-1])) / (width + 1e-12)
    return round(float(upper.iloc[-1]), 6), round(float(mid.iloc[-1]), 6), round(float(lower.iloc[-1]), 6), round(pct_b, 3)

def _volume(df, period=7):
    if len(df) < period + 1:
        return None, None
    avg = df["Hacim"].iloc[-period:].mean()
    ratio = df["Hacim"].iloc[-1] / (avg + 1e-12)
    return round(float(avg), 0), round(float(ratio), 2)

def calculate_all_indicators(df, periyot=7):
    rsi = _rsi(df)
    macd, macd_signal, macd_hist = _macd(df)
    bb_u, bb_m, bb_l, bb_pct = _bollinger(df)
    avg_vol, vol_ratio = _volume(df, periyot)

    rsi_comment = "Veri yetersiz"
    if rsi is not None:
        if rsi >= 70:
            rsi_comment = "Aşırı Alım Bölgesi"
        elif rsi >= 60:
            rsi_comment = "Güçlü Bölge"
        elif rsi >= 40:
            rsi_comment = "Nötr Bölge"
        elif rsi >= 30:
            rsi_comment = "Zayıf Bölge"
        else:
            rsi_comment = "Aşırı Satım Bölgesi"

    bb_comment = "Veri yetersiz"
    if bb_pct is not None:
        if bb_pct > 1:
            bb_comment = "Üst Bandın Üzerinde (Aşırı alım)"
        elif bb_pct > 0.8:
            bb_comment = "Üst Banda Yakın"
        elif bb_pct > 0.5:
            bb_comment = "Orta-Üst Bölge"
        elif bb_pct > 0.2:
            bb_comment = "Orta-Alt Bölge"
        elif bb_pct > 0:
            bb_comment = "Alt Banda Yakın"
        else:
            bb_comment = "Alt Bandın Altında (Aşırı satım)"

    macd_comment = "Veri yetersiz"
    if macd is not None and macd_hist is not None:
        if macd > macd_signal and macd_hist > 0:
            macd_comment = "Yükseliş sinyali"
        elif macd < macd_signal and macd_hist < 0:
            macd_comment = "Düşüş sinyali"
        elif macd > 0:
            macd_comment = "Pozitif bölge ama momentum zayıflıyor"
        else:
            macd_comment = "Negatif bölge ama momentum güçleniyor"

    return {
        "rsi": rsi,
        "rsi_yorum": rsi_comment,
        "macd": macd,
        "macd_sinyal": macd_signal,
        "macd_histogram": macd_hist,
        "macd_yorum": macd_comment,
        "bb_ust": bb_u,
        "bb_orta": bb_m,
        "bb_alt": bb_l,
        "bb_yuzde_b": bb_pct,
        "bb_yorum": bb_comment,
        "ort_hacim": avg_vol,
        "hacim_oran": vol_ratio,
    }
