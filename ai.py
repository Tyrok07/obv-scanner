import streamlit as st
from groq import Groq

GURU_SISTEM_PROMPT = """Sen deneyimli, soğukkanlı bir kripto piyasa teknik analistisin. Lakabın "Guru".
Sana verilen veriler bu uygulama tarafından zaten hesaplanmış OBV ve teknik indikatör metrikleridir.

KURALLARIN:
1. SADECE sana verilen verilere dayan.
2. Veride olmayan kesin hedef veya zaman tahmini verme.
3. OBV, RSI, MACD, Bollinger ve hacim ilişkisini açıkla.
4. Riskleri belirt ve sonunda "Bu bir yatırım tavsiyesi değildir." yaz.
5. En fazla 180 kelime, madde işareti kullanma.
6. Veri yetersizse bunu açıkça söyle.
"""

@st.cache_resource
def _client():
    key = st.secrets.get("GROQ_API_KEY", "")
    if not key:
        return None
    return Groq(api_key=key)

def get_guru_comment(text):
    client = _client()
    if client is None:
        return "⚠️ AI yorumu için GROQ_API_KEY tanımlı değil."
    try:
        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": GURU_SISTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            max_tokens=600,
            temperature=0.4,
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI yorumu alınamadı: {e}"
