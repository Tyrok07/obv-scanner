"""
ai.py — AI Guru Katmanı
─────────────────────────
Groq API (ücretsiz, Llama 3.3 70B) ile çalışan "Guru" yorum motoru.

ÖNEMLİ TASARIM PRENSİBİ: Bu modüle hiçbir zaman ham fiyat/hacim listesi
gönderilmez. Sadece data.py + indicators.py'nin ZATEN hesapladığı sonuçlar
(OBV sinyali, RSI, MACD, Bollinger %B, Fear&Greed, BTC dominansı vb.)
metne çevrilip gönderilir. Guru sayı üretmez, sadece üretilmiş sayıları
bir teknik analist diliyle yorumlar.
"""

import streamlit as st
from groq import Groq

GROQ_MODEL = "llama-3.3-70b-versatile"

GURU_SISTEM_PROMPT = """Sen deneyimli, soğukkanlı bir kripto piyasa teknik analistisin. Lakabın "Guru".
Sana verilen veriler CoinGecko API'sinden çekilmiş gerçek fiyat ve hacim verilerinden
bu uygulama tarafından zaten hesaplanmış OBV, RSI, MACD, Bollinger Bands ve piyasa
bağlamı (Fear & Greed Index, BTC dominansı) metrikleridir.

KURALLARIN:
1. SADECE sana verilen sayısal verilere dayanarak yorum yap. Veride olmayan kesin fiyat
   hedefi, "X gün içinde Y olur" gibi öngörülerde ASLA bulunma. Veri dışı varsayım üretme.
2. İndikatörlerin birbirini teyit edip etmediğini belirt (örneğin OBV düşüş gösterirken
   RSI aşırı satım bölgesindeyse, bu bir çelişki ya da dipten dönüş işareti olabilir —
   bunu açıkça tartış).
3. Riskleri belirt ve yanıtının sonunda "Bu bir yatırım tavsiyesi değildir." ifadesini ekle.
4. Akıcı paragraflar halinde, en fazla 200 kelime, madde işareti kullanmadan yaz.
5. Veri yetersiz veya çelişkiliyse bunu açıkça söyle; sallama yapma.
"""


@st.cache_resource
def _istemci_al():
    api_key = st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    return Groq(api_key=api_key)


def guru_yorumu_uret(veri_metni: str) -> str:
    """Uygulamanın hesapladığı gerçek verileri AI'a gönderip guru yorumu üretir."""
    client = _istemci_al()
    if client is None:
        return ("⚠️ AI yorumu için GROQ_API_KEY tanımlı değil. "
                "Streamlit Cloud → App settings → Secrets bölümüne eklemen gerekiyor. "
                "Ücretsiz key almak için: console.groq.com")
    try:
        yanit = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": GURU_SISTEM_PROMPT},
                {"role": "user",   "content": veri_metni},
            ],
            max_tokens=700,
            temperature=0.4,
        )
        return yanit.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI yorumu alınamadı: {e}"
