import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
import json
import datetime

# --- 0. 密碼鎖與訪客紀錄 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🐝 🐝 🐝 🐝 🐝</h1>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>阿峰的回測追蹤測試</h1>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            password = st.text_input("密碼", type="password")
            if st.button("確認登入"):
                if password == "19930522": 
                    st.session_state["password_correct"] = True
                    now = datetime.datetime.now() + datetime.timedelta(hours=8)
                    with open("login_log.txt", "a", encoding="utf-8") as f:
                        f.write(f"{now.strftime('%Y-%m-%d %H:%M:%S')} - 阿峰 登入\n")
                    st.rerun()
                else:
                    st.error("🚫 密碼錯誤")
        return False
    return True

if not check_password():
    st.stop()

# --- 1. 介面配置 ---
st.set_page_config(page_title="台股量價全視角雷達", layout="wide")
st.title("🏹 台股量價監測：職業交易員視角")

# --- 2. 影片核心邏輯：動能衰減檢查函數 ---
def check_professional_metrics(df):
    """
    實作簡一影片邏輯：檢查黑K實體是否縮小、是否有轉強訊號
    """
    try:
        # 計算K棒實體
        bodies = abs(df['Close'] - df['Open'])
        is_black = df['Close'] < df['Open']
        black_bodies = bodies[is_black]
        
        # 1. 動能衰減 (比較最近3次黑K vs 前7次)
        recent_black = black_bodies.iloc[-3:].mean() if len(black_bodies) >= 3 else 0
        prev_black = black_bodies.iloc[-10:-3].mean() if len(black_bodies) >= 10 else 999
        momentum_decay = recent_black < prev_black
        
        # 2. 止跌訊號 (吞噬或長下影線)
        last_c, last_o = float(df['Close'].iloc[-1]), float(df['Open'].iloc[-1])
        prev_c, prev_o = float(df['Close'].iloc[-2]), float(df['Open'].iloc[-2])
        is_engulfing = (last_c > prev_o) and (last_o < prev_c)
        
        # 下影線判斷
        lower_shadow = min(last_c, last_o) - df['Low'].iloc[-1]
        has_tail = lower_shadow > (abs(last_c - last_o) * 1.5)
        
        signal = "🔥 轉強訊號" if is_engulfing or has_tail else "⏳ 等待訊號"
        # 建議動作
        action = "🎯 建議試單 1/3" if (momentum_decay and (is_engulfing or has_tail)) else "☕ 先手觀望"
        
        return {
            "decay": momentum_decay,
            "signal": signal,
            "action": action,
            "is_ready": momentum_decay and (is_engulfing or has_tail)
        }
    except:
        return {"decay": False, "signal": "數據不足", "action": "持續觀察", "is_ready": False}

# --- 3. 核心分析函數 ---
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

        # --- 判斷邏輯 ---
        hit_data = None
        if mode_choice == "均線回檔 (趨勢追蹤)":
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200:
                dist_10 = (curr_p - m10) / m10
                dist_20 = (curr_p - m20) / m20
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    # 執行影片邏輯補充
                    pro_metrics = check_professional_metrics(df.tail(20))
                    # 結構停損：最近5日低點
                    struct_stop = df['Low'].iloc[-5:].min()
                    
                    hit_data = {
                        "id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, 
                        "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(40), 
                        "status": "🛡️ 回檔支撐", "pro": pro_metrics, "stop": struct_stop
                    }

        elif mode_choice == "均線糾撐 (底部突破)":
            # (此處可依樣畫葫蘆，先保留你原有的簡單邏輯)
            pass 

        return hit_data
    except:
        return None

# --- 4. 側邊欄與執行 ---
with st.sidebar:
    st.header("🔍 模式選擇")
    mode = st.radio("選擇監測模式", ["均線回檔 (趨勢追蹤)", "均線糾撐 (底部突破)"])
    industry_choice = st.selectbox("選擇產業類別", ["★台積電大聯盟 (設備/耗材/IP)", "半導體", "電機機械"])
    sensitivity = st.slider("靠近均線門檻 (%)", 0.1, 8.0, 3.5) / 100
    run_btn = st.button("🚀 開始掃描")

# --- 5. 結果顯示 ---
if run_btn:
    # 這裡請確保你有 stock_list.json，或是手動定義清單
    # 簡化範例：
    full_list = ["2330.TW", "3010.TW", "3028.TW", "6187.TW", "3131.TW"] 
    
    hits = []
    bar = st.progress(0)
    for i, s in enumerate(full_list):
        res = analyze_stock(s, mode, sensitivity)
        if res: hits.append(res)
        bar.progress((i + 1) / len(full_list))

    if hits:
        for hit in hits:
            with st.container():
                clean_id = hit['id'].replace(".TW", "")
                st.markdown(f"### [{hit['id']} {hit['status']}](https://tw.tradingview.com/symbols/TWSE-{clean_id}/)")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("現價", f"{hit['price']:.1f}")
                c2.metric("量能變動", f"{hit['vol_diff']:.1f}%")
                c3.metric("距20MA", f"{hit['d20']:.2f}%")

                # --- 影片補充：操作面板 ---
                pro = hit['pro']
                st.info(f"💡 **職業視角分析**：\n- 動能衰減：{'✅ 賣壓竭盡' if pro['decay'] else '❌ 仍有壓力'}\n- 訊號狀態：{pro['signal']}\n- **策略節奏：{pro['action']}**\n- 🛑 **結構停損位：{hit['stop']:.1f}**")

                # 畫圖代碼 (省略，請沿用你原本的 Plotly 代碼)
                st.divider()
    else:
        st.warning("查無標的")
