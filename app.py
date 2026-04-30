import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
import datetime

# --- 0. 密碼鎖與訪客紀錄 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🐝 🐝 🐝 🐝 🐝</h1>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>阿峰的回測追蹤</h1>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            password = st.text_input("密碼", type="password")
            if st.button("確認登入"):
                if password == "19930522": 
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("🚫 密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()

# --- 1. 配置 ---
st.set_page_config(page_title="台股量價全視角雷達", layout="wide")
st.title("🏹 台股量價監測：職業交易員視角")

# --- 2. 影片核心邏輯：動能衰減檢查函數 ---
def check_professional_metrics(df):
    try:
        bodies = abs(df['Close'] - df['Open'])
        is_black = df['Close'] < df['Open']
        black_bodies = bodies[is_black]
        recent_black = black_bodies.iloc[-3:].mean() if len(black_bodies) >= 3 else 0
        prev_black = black_bodies.iloc[-10:-3].mean() if len(black_bodies) >= 10 else 999
        momentum_decay = recent_black < prev_black
        last_c, last_o = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1])
        prev_c, prev_o = float(df['Close'].iloc[-2]), float(df['Open'].iloc[-2])
        is_engulfing = (last_c > prev_o) and (last_o < prev_c)
        lower_shadow = min(last_c, last_o) - df['Low'].iloc[-1]
        has_tail = lower_shadow > (abs(last_c - last_o) * 1.5)
        signal = "🔥 轉強訊號" if is_engulfing or has_tail else "⏳ 等待訊號"
        action = "🎯 建議試單 1/3" if (momentum_decay and (is_engulfing or has_tail)) else "☕ 先手觀望"
        return {"decay": momentum_decay, "signal": signal, "action": action}
    except:
        return {"decay": False, "signal": "數據不足", "action": "持續觀察"}

# --- 3. 核心分析函數 (包含 PE 抓取) ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        df = yf.download(symbol, period="200d", progress=False, threads=False)
        if df.empty or len(df) < 65: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]

        close = df['Close'].astype(float).squeeze().dropna()
        volume = df['Volume'].astype(float).squeeze().dropna()
        ma10, ma20, ma60 = close.rolling(10).mean(), close.rolling(20).mean(), close.rolling(60).mean()
        
        curr_p = float(close.iloc[-1])
        m10, m20, m60_curr = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma60.iloc[-1])
        m60_prev = float(ma60.iloc[-2])
        avg_vol_5d = volume.iloc[-6:-1].mean()
        vol_diff_pct = ((volume.iloc[-1] - avg_vol_5d) / avg_vol_5d) * 100 if avg_vol_5d > 0 else 0

        # 直接抓取 PE
        try:
            ticker = yf.Ticker(symbol)
            pe_ratio = ticker.info.get('trailingPE') or ticker.info.get('forwardPE')
        except:
            pe_ratio = None

        if mode_choice == "均線回檔 (趨勢追蹤)":
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200:
                dist_10, dist_20 = (curr_p - m10) / m10, (curr_p - m20) / m20
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    pro_metrics = check_professional_metrics(df.tail(20))
                    struct_stop = df['Low'].iloc[-5:].min()
                    return {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "pe": pe_ratio,
                            "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(40), 
                            "status": "🛡️ 回檔支撐", "pro": pro_metrics, "stop": struct_stop}
        return None
    except:
        return None

# --- 4. 側邊欄 ---
with st.sidebar:
    st.header("🔍 模式選擇")
    mode = st.radio("選擇監測模式", ["均線回檔 (趨勢追蹤)"])
    # 這裡手動加入你最常看的標的作為測試
    test_list = ["2330.TW", "3010.TW", "3028.TW", "6187.TW", "3131.TW", "3583.TW", "6196.TW"]
    sensitivity = st.slider("靠近均線門檻 (%)", 0.1, 8.0, 3.5) / 100
    run_btn = st.button("🚀 開始掃描")

# --- 5. 結果顯示與 Plotly K線 ---
if run_btn:
    hits = []
    bar = st.progress(0)
    for i, s in enumerate(test_list):
        res = analyze_stock(s, mode, sensitivity)
        if res: hits.append(res)
        bar.progress((i + 1) / len(test_list))

    if hits:
        for hit in hits:
            clean_id = hit['id'].replace(".TW", "")
            # Yahoo 股市連結
            yahoo_url = f"https://tw.stock.yahoo.com/quote/{clean_id}"
            st.markdown(f"### [{hit['id']} {hit['status']}]({yahoo_url})")
            
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("現價", f"{hit['price']:.1f}")
            c2.metric("量能變動", f"{hit['vol_diff']:.1f}%")
            c3.metric("距20MA", f"{hit['d20']:.2f}%")
            pe_display = f"{hit['pe']:.1f}" if hit['pe'] else "N/A"
            c4.metric("本益比(PE)", pe_display)

            # 職業視角面板
            pro = hit['pro']
            st.info(f"💡 **職業視角分析**：\n- 動能衰減：{'✅ 賣壓竭盡' if pro['decay'] else '❌ 仍有壓力'}\n- 訊號狀態：{pro['signal']}\n- **策略節奏：{pro['action']}**\n- 🛑 **結構停損位：{hit['stop']:.1f}**")

            # --- Plotly K線圖 ---
            df_plot = hit['df']
            fig = go.Figure(data=[go.Candlestick(
                x=df_plot.index, open=df_plot['Open'], high=df_plot['High'],
                low=df_plot['Low'], close=df_plot['Close'], name='K線'
            )])
            # 加入均線
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'].rolling(10).mean(), name='10MA', line=dict(color='orange', width=1)))
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Close'].rolling(20).mean(), name='20MA', line=dict(color='magenta', width=1)))
            
            fig.update_layout(xaxis_rangeslider_visible=False, height=400, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.divider()
    else:
        st.warning("查無標的，試著把門檻拉高一點？")
