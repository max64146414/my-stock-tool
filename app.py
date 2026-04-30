import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
import time
import json
import datetime

# --- 0. 簡易密碼鎖函數定義 ---
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🐝 🐝 🐝 🐝 🐝</h1>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>阿峰的回測追蹤測試</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>專屬雷達系統，請輸入通關密語</p>", unsafe_allow_html=True)
        
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            password = st.text_input("密碼", type="password")
            if st.button("確認登入"):
                if password == "19930522": 
                    st.session_state["password_correct"] = True
                    
                    # --- 訪客紀錄邏輯 ---
                    now = datetime.datetime.now() + datetime.timedelta(hours=8)
                    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    user_name = "阿峰" 
                    log_entry = f"{time_str} - {user_name} 登入系統\n"
                    with open("login_log.txt", "a", encoding="utf-8") as f:
                        f.write(log_entry)
                    
                    st.rerun()
                else:
                    st.error("🚫 密碼錯誤，請再試一次")
        
        st.markdown("<h3 style='text-align: center;'>🐝 🐝 🐝 🐝 🐝</h3>", unsafe_allow_html=True)
        return False
    return True

if not check_password():
    st.stop()

# --- 1. 配置 ---
st.set_page_config(page_title="台股量價全視角雷達", layout="wide")
st.title("🏹 台股量價監測：回檔 vs 糾纏突破")

# --- 2. 新增：職業動能分析邏輯 ---
def check_professional_metrics(df):
    """檢查黑K實體是否縮小、是否有轉強訊號"""
    try:
        bodies = abs(df['Close'] - df['Open'])
        is_black = df['Close'] < df['Open']
        black_bodies = bodies[is_black]
        
        # 動能衰減判斷
        recent_black = black_bodies.iloc[-3:].mean() if len(black_bodies) >= 3 else 0
        prev_black = black_bodies.iloc[-10:-3].mean() if len(black_bodies) >= 10 else 999
        momentum_decay = recent_black < prev_black
        
        # 止跌訊號判斷
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

# --- 3. 側邊欄 ---
with st.sidebar:
    st.header("🔍 模式選擇")
    mode = st.radio("選擇監測模式", ["均線回檔 (趨勢追蹤)", "均線糾纏 (底部突破)"])
    
    st.divider()
    st.header("⚙️ 掃描設定")
    industry_choice = st.selectbox("選擇產業類別", [
        "★台積電大聯盟 (設備/耗材/IP)", "半導體", "光電業", "電子零組件", 
        "電腦及週邊設備業", "通信網路業", "電機機械", "其他電子業"
    ])
    
    if mode == "均線回檔 (趨勢追蹤)":
        sensitivity = st.slider("靠近均線門檻 (%)", 0.1, 8.0, 3.5) / 100
    else:
        entangle_limit = st.slider("均線糾纏寬度 (%)", 0.5, 5.0, 2.0) / 100
        vol_boost = st.slider("帶量突破門檻 (倍)", 1.0, 5.0, 1.8)

    run_btn = st.button("🚀 開始掃描")

    st.divider()
    st.markdown("### 🐝 蜂巢足跡")
    try:
        with open("login_log.txt", "r", encoding="utf-8") as f:
            logs = f.readlines()
            for log in logs[-5:]:
                st.write(f"🕒 `{log.strip()}`")
    except:
        st.caption("📡 訊號掃描中... 暫無登入紀錄")

# --- 4. 清單抓取 ---
def get_full_industry_list(category):
    try:
        with open('stock_list.json', 'r', encoding='utf-8') as f:
            all_lists = json.load(f)
        if category in all_lists:
            return all_lists[category]
        dl = DataLoader()
        df = dl.taiwan_stock_info()
        stocks = df[df['industry_category'].str.contains(category.replace("業", ""))]
        stock_ids = stocks[stocks['stock_id'].str.len() == 4]['stock_id'].tolist()
        return [f"{s}.TW" for s in stock_ids]
    except:
        return ["2330.TW", "2454.TW", "2303.TW", "3711.TW", "3131.TW"]

# --- 5. 核心分析函數 (已添加分析指標) ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        df = yf.download(symbol, period="200d", progress=False, threads=False)
        if df.empty or len(df) < 65: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]

        close = df['Close'].astype(float).squeeze().dropna()
        volume = df['Volume'].astype(float).squeeze().dropna()
        ma10, ma20, ma60 = close.rolling(10).mean(), close.rolling(20).mean(), close.rolling(60).mean()
        
        today_vol = volume.iloc[-1]
        avg_vol_5d = volume.iloc[-6:-1].mean()
        vol_diff_pct = ((today_vol - avg_vol_5d) / avg_vol_5d) * 100 if avg_vol_5d > 0 else 0
        curr_p = float(close.iloc[-1])
        m10, m20, m60_curr = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma60.iloc[-1])
        m60_prev = float(ma60.iloc[-2])

        hit_data = None
        if mode_choice == "均線回檔 (趨勢追蹤)":
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200:
                dist_10, dist_20 = (curr_p - m10) / m10, (curr_p - m20) / m20
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    # 添加職業指標與停損位
                    pro_metrics = check_professional_metrics(df.tail(20))
                    struct_stop = df['Low'].iloc[-5:].min()
                    hit_data = {
                        "id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, 
                        "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(40), 
                        "status": "🛡️ 回檔支撐", "pro": pro_metrics, "stop": struct_stop
                    }

        elif mode_choice == "均線糾纏 (底部突破)":
            ma_list = [m10, m20, m60_curr]
            spread = (max(ma_list) - min(ma_list)) / min(ma_list)
            if spread < param1 and m60_curr >= m60_prev * 0.998 and curr_p > max(ma_list):
                is_vol_boost = (today_vol / avg_vol_5d) >= param2 if avg_vol_5d > 0 else False
                status_text = "🚀 帶量突破" if is_vol_boost else "💤 糾纏待變"
                hit_data = {
                    "id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, 
                    "d10": ((curr_p-m10)/m10)*100, "d20": ((curr_p-m20)/m20)*100, 
                    "df": df.tail(40), "status": status_text, "spread": spread*100
                }

        # 統一抓取 PE
        if hit_data:
            try:
                t_obj = yf.Ticker(symbol)
                hit_data['pe'] = t_obj.info.get('trailingPE')
            except:
                hit_data['pe'] = None
            return hit_data
        return None
    except:
        return None

# --- 6. 執行顯示 ---
if run_btn:
    full_list = get_full_industry_list(industry_choice)
    st.info(f"🔎 模式：{mode} | 正在掃描 {len(full_list)} 檔標的...")
    hits = []
    bar = st.progress(0)
    for i, s in enumerate(full_list):
        p1 = sensitivity if mode == "均線回檔 (趨勢追蹤)" else entangle_limit
        p2 = vol_boost if mode == "均線糾纏 (底部突破)" else None
        res = analyze_stock(s, mode, p1, p2)
        if res: hits.append(res)
        bar.progress((i + 1) / len(full_list))
    
    if hits:
        st.divider()
        for hit in hits:
            with st.container():
                clean_id = hit['id'].replace(".TW", "")
                tv_url = f"https://tw.tradingview.com/symbols/TWSE-{clean_id}/"
                
                # PE 處理
                pe_val = hit.get('pe')
                pe_display = f"{pe_val:.1f}" if pe_val else "N/A"
                
                st.markdown(f"### [{hit['id']} {hit['status']}]({tv_url})")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("現價", f"{hit['price']:.1f}")
                c2.metric("量能變動", f"{hit['vol_diff']:.1f}%")
                c3.metric("本益比(PE)", pe_display)
                
                # 職業分析看板 (新增在畫圖上方，方便手機閱讀)
                if "pro" in hit:
                    pro = hit['pro']
                    st.info(f"💡 **職業視角分析**：\n- 動能衰減：{'✅ 賣壓竭盡' if pro['decay'] else '❌ 仍有壓力'}\n- 訊號狀態：{pro['signal']}\n- **策略節奏：{pro['action']}**\n- 🛑 **結構停損位：{hit['stop']:.1f}**")

                # 畫圖
                fig = go.Figure(data=[go.Candlestick(x=hit['df'].index, open=hit['df']['Open'], high=hit['df']['High'], low=hit['df']['Low'], close=hit['df']['Close'], name="K")])
                fig.add_trace(go.Scatter(x=hit['df'].index, y=hit['df']['Close'].rolling(10).mean(), name="10", line=dict(color='orange', width=1.5)))
                fig.add_trace(go.Scatter(x=hit['df'].index, y=hit['df']['Close'].rolling(20).mean(), name="20", line=dict(color='red', width=1.5)))
                fig.update_layout(xaxis_rangeslider_visible=False, height=300, margin=dict(l=10, r=10, t=10, b=10), template="plotly_dark", showlegend=False)
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
                # 功能按鈕
                b1, b2, b3 = st.columns(3)
                b1.link_button("📈 圖表", tv_url, use_container_width=True)
                b2.link_button("💰 籌碼", f"https://www.wantgoo.com/stock/{clean_id}/chips", use_container_width=True)
                b3.link_button("🏢 法人", f"https://tw.stock.yahoo.com/quote/{clean_id}/institutional-trading", use_container_width=True)
                
                with st.expander(f"📋 生成 Gemini 復盤資料"):
                    st.code(f"教練，幫我復盤這檔標的：\n代號: {hit['id']}\n模式: {mode}\n數據: 現價{hit['price']}, PE {pe_display}")
                st.divider()
    else:
        st.warning("查無符合標的。")
