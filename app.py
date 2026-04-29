import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
import time

# --- 0. 簡易密碼鎖 ---
def check_password():
    """如果輸入正確密碼則回傳 True"""
    if "password_correct" not in st.session_state:
        # 顯示輸入框
        password = st.text_input("請輸入密碼以存取雷達：", type="password")
        if st.button("登入"):
            if password == "19930522": # 在這裡設定你要給朋友的密碼
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("密碼錯誤！")
        return False
    return True

if not check_password():
    st.stop() # 密碼錯誤就不跑下面的內容

# --- 接下來才是原本的 1. 配置、2. 側邊欄... ---

# --- 1. 配置 ---
st.set_page_config(page_title="台股量價全視角雷達", layout="wide")
st.title("🏹 台股量價監測：回檔 vs 糾纏突破")

# --- 2. 側邊欄 ---
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

# --- 3. 清單抓取 ---
@st.cache_data(ttl=3600)
def get_full_industry_list(category):
    if category == "★台積電大聯盟 (設備/耗材/IP)":
        return ["2330.TW", "2454.TW", "2303.TW", "3711.TW", "3131.TW", "3583.TW", "6187.TW", "2467.TW", "3680.TW", "6196.TW", "3443.TW", "3661.TW", "4770.TW", "3010.TW", "8028.TW", "3376.TW", "1773.TW", "1560.TW"]
    try:
        dl = DataLoader()
        df = dl.taiwan_stock_info()
        stocks = df[df['industry_category'].str.contains(category.replace("業", ""))]
        stock_ids = stocks[stocks['stock_id'].str.len() == 4]['stock_id'].tolist()
        return [f"{s}.TW" for s in stock_ids]
    except: return ["2330.TW", "2317.TW"]

# --- 4. 核心分析函數 ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="100d")
        if df is None or len(df) < 65: return None

        pe_ratio = ticker.info.get('trailingPE', None)
        close = df['Close'].astype(float)
        volume = df['Volume'].astype(float)
        ma10, ma20, ma60 = close.rolling(10).mean(), close.rolling(20).mean(), close.rolling(60).mean()
        
        today_vol = volume.iloc[-1]
        avg_vol_5d = volume.iloc[-6:-1].mean()
        vol_diff_pct = ((today_vol - avg_vol_5d) / avg_vol_5d) * 100 if avg_vol_5d > 0 else 0
        curr_p = float(close.iloc[-1])
        m10, m20, m60_curr = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma60.iloc[-1])
        m60_prev = float(ma60.iloc[-2])

        if mode_choice == "均線回檔 (趨勢追蹤)":
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200:
                dist_10, dist_20 = ((curr_p - m10) / m10), ((curr_p - m20) / m20)
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    return {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "pe": pe_ratio, "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(40), "status": "🛡️ 回檔支撐"}

        elif mode_choice == "均線糾纏 (底部突破)":
            ma_list = [m10, m20, m60_curr]
            spread = (max(ma_list) - min(ma_list)) / min(ma_list)
            is_entangled = spread < param1
            is_trending_up = m60_curr >= m60_prev * 0.998
            is_above = curr_p > max(ma_list)
            is_vol_boost = (today_vol / avg_vol_5d) >= param2 if avg_vol_5d > 0 else False

            if is_entangled and is_trending_up and is_above:
                status_text = "🚀 帶量突破" if is_vol_boost else "💤 糾纏待變"
                return {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "pe": pe_ratio, "d10": ((curr_p-m10)/m10)*100, "d20": ((curr_p-m20)/m20)*100, "df": df.tail(40), "status": status_text, "spread": spread*100}
        return None
    except: return None

# --- 5. 執行顯示 ---
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
        cols = st.columns(3)
        for idx, hit in enumerate(hits):
            with cols[idx % 3]:
                clean_id = hit['id'].replace(".TW", "")
                
                # 本益比標記
                pe_val = hit['pe']
                pe_str = f"{pe_val:.1f}" if pe_val else "N/A"
                pe_display = f":green[{pe_str}]" if pe_val and pe_val < 15 else (f":red[{pe_str}]" if pe_val and pe_val > 30 else pe_str)

                st.markdown(f"### {hit['id']} {hit['status']}")
                st.write(f"現價: **{hit['price']:.1f}** | **本益比: {pe_display}**")
                
                v_color = ":red" if hit['vol_diff'] > 50 else (":green" if hit['vol_diff'] < -30 else "")
                st.write(f"🔄 量能變動: {v_color}[{hit['vol_diff']:.1f}%]")
                
                if mode == "均線糾纏 (底部突破)":
                    st.write(f"📏 糾纏寬度: **{hit['spread']:.2f}%**")
                else:
                    st.write(f"📏 距10MA: {hit['d10']:.2f}% | 距20MA: {hit['d20']:.2f}%")

                fig = go.Figure(data=[go.Candlestick(x=hit['df'].index, open=hit['df']['Open'], high=hit['df']['High'], low=hit['df']['Low'], close=hit['df']['Close'], name="K")])
                fig.add_trace(go.Scatter(x=hit['df'].index, y=hit['df']['Close'].rolling(10).mean(), name="10", line=dict(color='orange', width=1)))
                fig.add_trace(go.Scatter(x=hit['df'].index, y=hit['df']['Close'].rolling(20).mean(), name="20", line=dict(color='red', width=1)))
                fig.add_trace(go.Scatter(x=hit['df'].index, y=hit['df']['Close'].rolling(60).mean(), name="60", line=dict(color='green', width=2)))
                fig.update_layout(xaxis_rangeslider_visible=False, height=230, margin=dict(l=5, r=5, t=5, b=5), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
                
                # --- 這裡按鈕區 (穩健修正版) ---
                c1, c2 = st.columns(2)
                c1.link_button("籌碼", f"https://www.wantgoo.com/stock/{clean_id}/chips")
                c2.link_button("法人", f"https://tw.stock.yahoo.com/quote/{clean_id}/institutional-trading")
                
                # 改用摺疊面板，點開就一定會看到，不會沒反應
                with st.expander(f"📋 點我生成 Gemini 復盤資料"):
                    draft_content = f"教練，幫我復盤這檔標的：\n代號: {hit['id']}\n模式: {mode}\n狀態: {hit['status']}\n數據: 現價{hit['price']}, 距20MA {hit['d20']:.2f}%, 量比 {hit['vol_diff']:.1f}%, PE {pe_str}"
                    st.code(draft_content)
                    st.caption("☝️ 點擊上方小方塊右上角的按鈕即可複製")
                
                st.divider()
    else:
        st.warning("查無符合標的。")