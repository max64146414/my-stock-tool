import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
import time

import streamlit as st
# ... 其他 import ...

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
                    
                    # --- 新增：訪客紀錄邏輯 ---
                    import datetime
                    # 取得現在時間 (台北時間)
                    now = datetime.datetime.now() + datetime.timedelta(hours=8)
                    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 這裡可以寫死是「阿峰」，或者未來你有給別人密碼，可以根據密碼判斷是誰
                    user_name = "阿峰" 
                    
                    # 建立一條紀錄
                    log_entry = f"{time_str} - {user_name} 登入系統\n"
                    
                    # 將紀錄寫入一個叫 login_log.txt 的檔案 (append 模式)
                    with open("login_log.txt", "a", encoding="utf-8") as f:
                        f.write(log_entry)
                    # ------------------------
                    
                    st.rerun()
                else:
                    st.error("🚫 密碼錯誤，請再試一次")
        
        st.markdown("<h3 style='text-align: center;'>🐝 🐝 🐝 🐝 🐝</h3>", unsafe_allow_html=True)
        return False
    return True

# --- 這裡最重要：先檢查密碼，沒過就攔截！ ---
if not check_password():
    st.stop()  # 這一行是保門員，密碼沒過，下面的代碼通通不執行

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

# --- 這裡加入「訪客紀錄」顯示 ---
    st.divider()
    st.subheader("👤 最近訪客紀錄")
    try:
        # 讀取 login_log.txt
        with open("login_log.txt", "r", encoding="utf-8") as f:
            logs = f.readlines()
            # 用 reversed 讓最新時間在最上面
            for log in reversed(logs[-5:]): 
                st.caption(f"🕒 {log.strip()}")
    except:
        st.caption("📡 尚無連線紀錄")

import json # 確保你的 app.py 最上方有這行

# --- 3. 清單抓取 (讀取本地 JSON 版) ---
def get_full_industry_list(category):
    try:
        # 讀取我們剛剛建立的 json 檔案
        with open('stock_list.json', 'r', encoding='utf-8') as f:
            all_lists = json.load(f)
        
        # 如果選的分類在檔案裡，就直接回傳
        if category in all_lists:
            return all_lists[category]
        
        # 如果選了沒在檔案裡的分類，才去問 FinMind (備援)
        dl = DataLoader()
        df = dl.taiwan_stock_info()
        stocks = df[df['industry_category'].str.contains(category.replace("業", ""))]
        stock_ids = stocks[stocks['stock_id'].str.len() == 4]['stock_id'].tolist()
        return [f"{s}.TW" for s in stock_ids]
    except:
        # 最後的保險絲
        return ["2330.TW", "2454.TW", "2303.TW", "3711.TW", "3131.TW", "3583.TW", "6187.TW"]
    
# --- 4. 核心分析函數 ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        # 改用 yf.download 並增加 period 確保均線計算有足夠歷史資料
        df = yf.download(symbol, period="200d", progress=False, threads=False)
        
        if df.empty or len(df) < 65:
            return None

        # 處理雲端抓取時可能出現的多層索引問題 (這對大聯盟清單非常重要)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # 強制將所有欄位名稱轉為首字母大寫，預防大小寫不一導致查無資料
        df.columns = [str(c).capitalize() for c in df.columns]

        close = df['Close'].astype(float)
        volume = df['Volume'].astype(float)
        
        # 確保數據是 Series 格式並移除空值
        close = close.squeeze().dropna()
        volume = volume.squeeze().dropna()

        if len(close) < 65:
            return None

        ma10, ma20, ma60 = close.rolling(10).mean(), close.rolling(20).mean(), close.rolling(60).mean()
        
        today_vol = volume.iloc[-1]
        avg_vol_5d = volume.iloc[-6:-1].mean()
        vol_diff_pct = ((today_vol - avg_vol_5d) / avg_vol_5d) * 100 if avg_vol_5d > 0 else 0
        curr_p = float(close.iloc[-1])
        m10, m20, m60_curr = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma60.iloc[-1])
        m60_prev = float(ma60.iloc[-2])

        # 這裡獲取本益比（雲端有時會抓不到，給予預設值）
        try:
            ticker = yf.Ticker(symbol)
            pe_ratio = ticker.info.get('trailingPE', None)
        except:
            pe_ratio = None

        if mode_choice == "均線回檔 (趨勢追蹤)":
            # 判斷條件：站上季線且季線向上，且 5 日均量 > 200 張
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200:
                dist_10, dist_20 = ((curr_p - m10) / m10), ((curr_p - m20) / m20)
                # 判斷是否回測 10MA 或 20MA (param1 是你滑桿拉的 % 數)
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    return {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "pe": pe_ratio, "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(40), "status": "🛡️ 回檔支撐"}

        elif mode_choice == "均線糾纏 (底部突破)":
            ma_list = [m10, m20, m60_curr]
            spread = (max(ma_list) - min(ma_list)) / min(ma_list)
            # 判斷條件：均線糾纏小於 param1，且現價突破所有均線
            if spread < param1 and m60_curr >= m60_prev * 0.998 and curr_p > max(ma_list):
                is_vol_boost = (today_vol / avg_vol_5d) >= param2 if avg_vol_5d > 0 else False
                status_text = "🚀 帶量突破" if is_vol_boost else "💤 糾纏待變"
                return {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "pe": pe_ratio, "d10": ((curr_p-m10)/m10)*100, "d20": ((curr_p-m20)/m20)*100, "df": df.tail(40), "status": status_text, "spread": spread*100}
        return None
    except Exception as e:
        print(f"分析 {symbol} 時出錯: {e}")
        return None
        
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
