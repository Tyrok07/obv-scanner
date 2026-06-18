def get_css():
    return """
    <style>
    .big-font {
        font-size: 24px !important;
        font-weight: 700;
        color: #8dc647;
        margin-bottom: 0.25rem;
    }
    .hero-box {
        padding: 14px 18px;
        border-radius: 14px;
        background: linear-gradient(90deg, rgba(141,198,71,0.14), rgba(141,198,71,0.04));
        border: 1px solid rgba(141,198,71,0.25);
        margin-bottom: 1rem;
    }
    .section-box {
        padding: 12px 16px;
        border-radius: 12px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        margin: 0.4rem 0 1rem 0;
    }
    .stProgress > div > div > div > div {
        background-color: #8dc647;
    }
    .sinyal-banner {
        padding: 12px 20px;
        border-radius: 10px;
        font-size: 20px;
        font-weight: 700;
        margin: 12px 0;
    }
    </style>
    """

def get_banner_html():
    return """
    <div class="hero-box">
        <div class="big-font">🦎 CoinGecko Altyapılı Gelişmiş OBV Hacim & Balina Tarayıcı</div>
        <div style="opacity:0.85;margin-top:4px;">
            OBV, RSI, MACD, Bollinger ve piyasa bağlamını birlikte okuyarak sinyal üretir.
        </div>
    </div>
    """
