"""
styles.py — Görsel Katman
─────────────────────────
Uygulamanın tüm görsel kimliği burada toplanır: renk paleti, global CSS,
yeniden kullanılabilir HTML bileşenleri (sinyal banner'ı, Guru transmisyon
kartı, başlık) ve Plotly grafik teması.

Tasarım konsepti: "Derin Deniz Tarama Terminali" — balina/OBV temasına
oturan, koyu okyanus paleti + biyolüminesan turkuaz vurgu + terminal
tipografisi (Space Grotesk / JetBrains Mono). İmza öğesi: sinyal
banner'larında ve Guru kartında tekrar eden "sonar ping" animasyonu.

app.py bu modülden sadece fonksiyon çağırır; hiçbir CSS app.py içinde
yazılmaz.
"""

import streamlit as st


# ─── RENK PALETİ ─────────────────────────────────────────────────
BG_BASE       = "#060B14"   # ana arka plan (abisal lacivert-siyah)
BG_SURFACE    = "#0E1729"   # kart / panel yüzeyi
BG_SURFACE_2  = "#16223B"   # yükseltilmiş kart / hover
BORDER        = "#223252"   # ince ayraç çizgisi

ACCENT        = "#2DD4BF"   # imza rengi — biyolüminesan turkuaz
ACCENT_SOFT   = "#5EEAD4"

POSITIVE      = "#34D399"   # deniz yeşili — onaylı yükseliş / balina birikimi
NEGATIVE      = "#F87171"   # mercan kırmızısı — dağıtım / risk
WARNING       = "#FBBF24"   # amber — dikkat / düşüş
NEUTRAL       = "#64748B"   # slate — nötr

TEXT_PRIMARY  = "#E7ECF5"
TEXT_MUTED    = "#8B9BB8"

# Sinyal metnindeki anahtar kelimeye göre renk eşlemesi.
# Bu, eskiden 3 farklı yerde kopyalanmış olan renk mantığının TEK kaynağı.
SIGNAL_COLORS = {
    "POZİTİF":  ACCENT,     # balina birikimi
    "NEGATİF":  NEGATIVE,   # dağıtım / sahte yükseliş
    "YÜKSELİŞ": POSITIVE,   # hacim onaylı yükseliş
    "DÜŞÜŞ":    WARNING,    # hacim onaylı düşüş
}


def get_signal_color(sinyal: str) -> str:
    """Sinyal metnindeki anahtar kelimeye göre tek, tutarlı renk döndürür."""
    sinyal = str(sinyal)
    for anahtar, renk in SIGNAL_COLORS.items():
        if anahtar in sinyal:
            return renk
    return NEUTRAL


# ─── GLOBAL CSS ──────────────────────────────────────────────────
_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root {
    --bg-base: #060B14;
    --bg-surface: #0E1729;
    --bg-surface-2: #16223B;
    --border: #223252;
    --accent: #2DD4BF;
    --text-primary: #E7ECF5;
    --text-muted: #8B9BB8;
}

/* ── Temel yüzeyler ── */
[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 1200px 600px at 50% -10%, rgba(45,212,191,0.07), transparent 60%),
        var(--bg-base);
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] {
    background: var(--bg-surface);
    border-right: 1px solid var(--border);
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.2rem; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
}
h1, h2, h3, h4 { font-family: 'Space Grotesk', sans-serif !important; }

/* ── Sidebar mini başlıkları ── */
.obv-sidebar-label {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--text-muted);
    margin: 1.1rem 0 0.3rem 0;
    display: flex; align-items: center; gap: 6px;
}

/* ── Metrikler (st.metric) ── */
[data-testid="stMetric"] {
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px 16px 12px 16px;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.55;
}
[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace !important;
    font-weight: 600 !important;
    font-size: 1.35rem !important;
}
[data-testid="stMetricLabel"] {
    font-family: 'Inter', sans-serif;
    color: var(--text-muted) !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

/* ── Butonlar ── */
.stButton > button {
    border-radius: 9px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    border: 1px solid var(--border);
    background: var(--bg-surface-2);
    color: var(--text-primary);
    transition: all 0.15s ease;
}
.stButton > button:hover {
    border-color: var(--accent);
    color: var(--accent);
}
[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(135deg, #2DD4BF, #14B8A6);
    color: #06151A;
    border: none;
    box-shadow: 0 0 0 1px rgba(45,212,191,0.35), 0 6px 18px rgba(45,212,191,0.22);
    font-weight: 700;
}
[data-testid="stSidebar"] .stButton > button:hover { filter: brightness(1.08); }

/* ── Sekmeler ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-surface);
    padding: 5px;
    border-radius: 11px;
    border: 1px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600;
    color: var(--text-muted);
    padding: 8px 16px;
}
.stTabs [aria-selected="true"] {
    background: rgba(45,212,191,0.12) !important;
    color: var(--accent) !important;
}

/* ── Veri tabloları ── */
[data-testid="stDataFrame"] {
    border-radius: 11px;
    overflow: hidden;
    border: 1px solid var(--border);
}

/* ── Girdi alanları ── */
.stSelectbox > div > div, .stTextInput > div > div, .stNumberInput > div > div {
    background: var(--bg-surface-2);
    border-color: var(--border) !important;
    border-radius: 8px;
}

/* ── Ayraçlar ── */
hr { border-color: var(--border) !important; opacity: 0.7; }

/* ── Uyarı/bilgi kutuları ── */
.stAlert { border-radius: 10px; font-family: 'Inter', sans-serif; }

/* ── İmza öğesi: Sonar Ping ── */
.obv-ping {
    position: relative;
    display: inline-block;
    width: 9px; height: 9px;
    border-radius: 50%;
    background: var(--ping-color, var(--accent));
    flex-shrink: 0;
}
.obv-ping::after {
    content: '';
    position: absolute; inset: 0;
    border-radius: 50%;
    background: var(--ping-color, var(--accent));
    animation: obvPing 1.8s cubic-bezier(0,0,0.2,1) infinite;
}
@keyframes obvPing {
    0%   { transform: scale(1);   opacity: 0.65; }
    75%  { transform: scale(2.8); opacity: 0; }
    100% { transform: scale(2.8); opacity: 0; }
}

/* ── Sayfa başlığı ── */
.obv-header { margin-bottom: 0.6rem; }
.obv-header-eyebrow {
    display: flex; align-items: center; gap: 9px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem; letter-spacing: 0.12em;
    color: var(--text-muted); text-transform: uppercase;
    margin-bottom: 6px;
}
.obv-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.9rem; font-weight: 700;
    color: var(--text-primary);
    margin: 0 0 4px 0;
}
.obv-subtitle {
    font-family: 'Inter', sans-serif;
    color: var(--text-muted);
    font-size: 0.92rem;
    margin: 0;
}

/* ── Sinyal banner ── */
.obv-signal-banner {
    display: flex; align-items: center; gap: 12px;
    background: var(--banner-color, var(--accent))15;
    border: 1px solid var(--banner-color, var(--accent))40;
    border-left: 3px solid var(--banner-color, var(--accent));
    padding: 14px 20px;
    border-radius: 10px;
    margin: 14px 0;
}
.obv-signal-text {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 600; font-size: 1.05rem;
    color: var(--banner-color, var(--accent));
}

/* ── AI Guru transmisyon kartı ── */
.obv-guru-card {
    background:
        repeating-linear-gradient(0deg, rgba(255,255,255,0.012) 0px, rgba(255,255,255,0.012) 1px, transparent 1px, transparent 3px),
        var(--bg-surface);
    border: 1px solid var(--guru-color, var(--accent))35;
    border-left: 3px solid var(--guru-color, var(--accent));
    border-radius: 10px;
    padding: 16px 20px;
    margin-top: 10px;
}
.obv-guru-head {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 10px;
}
.obv-guru-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem; letter-spacing: 0.1em;
    color: var(--guru-color, var(--accent));
    text-transform: uppercase;
}
.obv-guru-text {
    font-family: 'Inter', sans-serif;
    color: var(--text-primary);
    line-height: 1.75;
    font-size: 0.96rem;
    margin: 0;
}

/* ── Mini indikatör rozeti (sidebar / panel etiketleri) ── */
.obv-chip {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: var(--text-muted);
    background: var(--bg-surface-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 4px 10px;
    margin-right: 6px;
}
</style>
"""


def inject_global_styles():
    """Sayfanın en başında bir kere çağrılır; tüm global CSS'i enjekte eder."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ─── HTML BİLEŞENLERİ ────────────────────────────────────────────

def render_header(eyebrow: str, title: str, subtitle: str):
    """Sayfa başlığı: canlı ping + başlık + alt yazı."""
    st.markdown(f"""
    <div class="obv-header">
        <div class="obv-header-eyebrow">
            <span class="obv-ping" style="--ping-color:{ACCENT}"></span>
            {eyebrow}
        </div>
        <div class="obv-title">{title}</div>
        <p class="obv-subtitle">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def render_signal_banner(sinyal: str):
    """Sinyal metnini, rengine göre boyanmış sonar-ping'li bir banner içinde gösterir."""
    renk = get_signal_color(sinyal)
    st.markdown(f"""
    <div class="obv-signal-banner" style="--banner-color:{renk}">
        <span class="obv-ping" style="--ping-color:{renk}"></span>
        <span class="obv-signal-text">{sinyal}</span>
    </div>
    """, unsafe_allow_html=True)


def render_guru_card(yorum: str, renk: str = ACCENT):
    """AI Guru yorumunu 'transmisyon' temalı bir kartta gösterir."""
    st.markdown(f"""
    <div class="obv-guru-card" style="--guru-color:{renk}">
        <div class="obv-guru-head">
            <span class="obv-ping" style="--ping-color:{renk}"></span>
            <span class="obv-guru-label">Guru // Transmisyon</span>
        </div>
        <p class="obv-guru-text">{yorum}</p>
    </div>
    """, unsafe_allow_html=True)


def render_chip(text: str):
    """Küçük bir bilgi rozeti döndürür (string olarak; başka HTML'e gömülebilir)."""
    return f'<span class="obv-chip">{text}</span>'


# ─── DATAFRAME HÜCRE STİLLERİ ────────────────────────────────────

def style_signal_cell(val):
    """st.dataframe(...).style.map() için sinyal hücresi renklendirme."""
    renk = get_signal_color(val)
    if renk == NEUTRAL:
        return ''
    return f'background-color:{renk}1F; color:{renk}; font-weight:600;'


def style_performance_cell(val):
    """Performans % hücreleri için renklendirme (takip listesi)."""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ''
    if v > 5:
        return f'background-color:{POSITIVE}26; color:{POSITIVE}; font-weight:600;'
    elif v > 0:
        return f'background-color:{POSITIVE}14; color:{POSITIVE};'
    elif v > -5:
        return f'background-color:{WARNING}14; color:{WARNING};'
    else:
        return f'background-color:{NEGATIVE}26; color:{NEGATIVE}; font-weight:600;'


# ─── PLOTLY GRAFİK TEMASI ────────────────────────────────────────

def obv_grafigi_ciz(df_coin, coin_adi, sinyal):
    """OBV + Fiyat grafiğini 'derin deniz terminali' temasıyla çizer."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    sinyal_renk = get_signal_color(sinyal)

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Fiyat (USD)", "OBV (On-Balance Volume)"),
        row_heights=[0.55, 0.45]
    )
    tarihler = list(range(len(df_coin)))

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['Fiyat'], mode='lines', name='Fiyat',
        line=dict(color=ACCENT, width=2),
        fill='tozeroy', fillcolor='rgba(45,212,191,0.08)',
        hovertemplate='Gün %{x}<br>Fiyat: $%{y:,.6f}<extra></extra>'
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['OBV'], mode='lines', name='OBV',
        line=dict(color=sinyal_renk, width=2),
        hovertemplate='Gün %{x}<br>OBV: %{y:,.0f}<extra></extra>'
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['OBV_EMA'], mode='lines', name='OBV EMA(5)',
        line=dict(color='rgba(251,191,36,0.85)', width=1.5, dash='dot'),
    ), row=2, col=1)

    fig.add_trace(go.Scatter(
        x=tarihler, y=df_coin['OBV_Trend'], mode='lines', name='OBV MA(5)',
        line=dict(color='rgba(139,155,184,0.5)', width=1, dash='dash'),
    ), row=2, col=1)

    fig.update_layout(
        title=dict(text=f"{coin_adi} — OBV Analizi",
                    font=dict(size=15, family="Space Grotesk, sans-serif", color=TEXT_PRIMARY)),
        paper_bgcolor=BG_SURFACE, plot_bgcolor=BG_SURFACE,
        font=dict(color=TEXT_MUTED, family="Inter, sans-serif"),
        height=600, hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                    font=dict(family="Inter, sans-serif", size=11)),
        xaxis=dict(showgrid=True, gridcolor=BORDER, tickfont=dict(family="JetBrains Mono, monospace", size=10)),
        xaxis2=dict(showgrid=True, gridcolor=BORDER, title='Gün',
                    tickfont=dict(family="JetBrains Mono, monospace", size=10)),
        yaxis=dict(showgrid=True, gridcolor=BORDER, tickfont=dict(family="JetBrains Mono, monospace", size=10)),
        yaxis2=dict(showgrid=True, gridcolor=BORDER, tickfont=dict(family="JetBrains Mono, monospace", size=10)),
        margin=dict(l=10, r=10, t=60, b=10),
    )
    return fig
