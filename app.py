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
                # 建立密碼對應表
                user_map = {
                    "19930522": "阿峰",
                    "820522": "脆皮",  # 假設給阿嬤的密碼
                    "0522": "柔",
                    "159632": "阿曼達"
                }
                
                if password in user_map:
                    st.session_state["password_correct"] = True
                    user_name = user_map[password] # 自動抓取對應的人名
                    
                    # 紀錄登入
                    now = datetime.datetime.now() + datetime.timedelta(hours=8)
                    log_entry = f"{now.strftime('%Y-%m-%d %H:%M:%S')} - {user_name} 登入系統\n"
                    with open("login_log.txt", "a", encoding="utf-8") as f:
                        f.write(log_entry)
                    st.rerun()
                else:
                    st.error("🚫 密碼錯誤")
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
        recent_black = black_bodies.iloc[-3:].mean() if len(black_bodies) >= 2 else 0
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

# --- 4. 清單抓取 (修復 JSON 讀取失敗問題) ---
def get_full_industry_list(category):
    # 這就是你現在看到的 8 檔來源 (保險絲)
    backup_map = {
        "電子零組件": ["2317.TW", "2308.TW", "3037.TW", "2367.TW", "2313.TW", "2368.TW", "8046.TW", "6213.TW"]
    }

    try:
        # 1. 開啟 JSON
        with open('stock_list.json', 'r', encoding='utf-8') as f:
            all_lists = json.load(f)
        
        # --- 強化匹配邏輯 ---
        # 移除 category 的「★」符號與「業」字來做模糊比對
        clean_cat = category.replace("★", "").replace("業", "").strip()
        
        # 建立一個暫時的字典，把 JSON 裡所有的 Key 也都簡化來比對
        for raw_key in all_lists.keys():
            clean_key = raw_key.replace("★", "").replace("業", "").strip()
            if clean_cat in clean_key or clean_key in clean_cat:
                res = all_lists[raw_key]
                if len(res) > 0:
                    return res # 只要找到了，就直接回傳 JSON 裡那幾百檔

        # 2. 如果 JSON 真的找不到，才去問 FinMind
        dl = DataLoader()
        df = dl.taiwan_stock_info()
        stocks = df[df['industry_category'].str.contains(clean_cat)]
        res = [f"{s}.TW" for s in stocks['stock_id'].tolist() if len(s) == 4]
        return res if len(res) > 0 else backup_map.get(category, ["2330.TW"])

    except Exception as e:
        # 報錯時，回傳備援清單 (也就是你看到的 8 檔)
        return backup_map.get(category, ["2330.TW"])

# --- 5. 核心分析函數 (已整合風控與 PE 邏輯) ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        df = yf.download(symbol, period="200d", progress=False, threads=False)
        if df.empty or len(df) < 65: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]

        close = df['Close'].astype(float).squeeze().dropna()
        volume = df['Volume'].astype(float).squeeze().dropna()
        ma10, ma20, ma60 = close.rolling(10).mean(), close.rolling(20).mean(), close.rolling(60).mean()

        # --- 新增：計算布林通道並存入 DataFrame 以供畫圖使用 ---
        std20 = close.rolling(20).std()
        df['MA10'] = ma10
        df['MA20'] = ma20
        df['MA60'] = ma60
        df['BB_Upper'] = ma20 + 2 * std20
        df['BB_Lower'] = ma20 - 2 * std20
        today_vol = volume.iloc[-1]
        avg_vol_5d = volume.iloc[-6:-1].mean()
        vol_diff_pct = ((today_vol - avg_vol_5d) / avg_vol_5d) * 100 if avg_vol_5d > 0 else 0
        curr_p = float(close.iloc[-1])
        m10, m20, m60_curr = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma60.iloc[-1])
        m60_prev = float(ma60.iloc[-2])

        hit_data = None
        # --- 模式 A: 均線回檔 ---
        if mode_choice == "均線回檔 (趨勢追蹤)":
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200:
                dist_10, dist_20 = (curr_p - m10) / m10, (curr_p - m20) / m20
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    pro_metrics = check_professional_metrics(df.tail(40))
                    hit_data = {
                        "id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, 
                        "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(40), 
                        "status": "🛡️ 回檔支撐", "pro": pro_metrics
                    }

        # --- 模式 B: 均線糾纏 ---
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

        # --- 這裡就是你說的「尾端」：當股票符合條件，補上 PE 與 風控計算 ---
        # --- 這裡就是你說的「尾端」：當股票符合條件，補上 PE 與 風控計算 ---
        if hit_data:
            # 1. 抓取 PE 與 PB
            try:
                t_obj = yf.Ticker(symbol)
                info = t_obj.info # 先把 info 存起來，避免重複呼叫拖慢速度
                hit_data['pe'] = info.get('trailingPE') or info.get('forwardPE')
                hit_data['pb'] = info.get('priceToBook') # 新增這行抓 PB
            except:
                hit_data['pe'] = None
                hit_data['pb'] = None # 新增這行
            
            # 2. 計算風控價位 (這就是新增的地方)
            struct_stop = df['Low'].iloc[-5:].min()  # 近5日低點
            hit_data["stop_price"] = struct_stop
            hit_data["profit_stop"] = m20            # 移動停利參考 20MA
            hit_data["risk_pct"] = ((curr_p - struct_stop) / curr_p) * 100
            
            return hit_data
            
        return None
    except Exception as e:
        print(f"分析出錯: {e}")
        return None

# --- 6. 執行顯示 (確保量能與所有指標完整顯示) ---
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
    
    # 從這裡開始替換
    if hits:
        # --- 自動排序邏輯 ---
        if mode == "均線回檔 (趨勢追蹤)":
            hits = sorted(hits, key=lambda x: abs(x.get('d20', 100)))
        elif mode == "均線糾纏 (底部突破)":
            hits = sorted(hits, key=lambda x: x.get('spread', 100))

        st.divider()
        st.success(f"🎯 掃描完成！共抓出 {len(hits)} 檔符合條件的標的。")

        # ==========================================
        # 🌟 新增：利用 FinMind 建立「代碼對應中文名稱」的字典
        # 使用一天 (86400秒) 的快取，才不會每次掃描都重新下載名稱
        # ==========================================
        @st.cache_data(ttl=86400)
        def get_stock_names():
            try:
                from FinMind.data import DataLoader
                dl = DataLoader()
                df_info = dl.taiwan_stock_info()
                # 做出類似 {'2330': '台積電', '2317': '鴻海'} 的字典
                return dict(zip(df_info['stock_id'], df_info['stock_name']))
            except:
                return {}
        
        name_map = get_stock_names()

        for hit in hits:
            with st.container():
                # 清除 ".TW" 後綴，只保留數字代碼 (例如：2330)
                clean_id = hit['id'].replace(".TW", "")
                
                # 🌟 從字典中抓取中文名稱，如果抓不到就留空
                stock_name = name_map.get(clean_id, "") 
                
                tv_url = f"https://tw.tradingview.com/symbols/TWSE-{clean_id}/"
                
                # --- [A-1] PE 評價處理 ---
                pe_val = hit.get('pe')
                if pe_val:
                    if pe_val < 15: pe_tag = f"🟢 低估 ({pe_val:.1f})"
                    elif pe_val < 25: pe_tag = f"🟡 常態 ({pe_val:.1f})"
                    else: pe_tag = f"🔴 偏高 ({pe_val:.1f})"
                else:
                    pe_tag = "⚪ 暫無數據"

                # --- [A-2] PB 評價處理 ---
                pb_val = hit.get('pb')
                if pb_val:
                    if pb_val < 1.5: pb_tag = f"🟢 超跌便宜 ({pb_val:.2f})"
                    elif pb_val < 3.5: pb_tag = f"🟡 科技常態 ({pb_val:.2f})"
                    elif pb_val < 6.0: pb_tag = f"🟠 享有溢價 ({pb_val:.2f})"
                    else: pb_tag = f"🔴 極度昂貴 ({pb_val:.2f})"
                else:
                    pb_tag = "⚪ 暫無數據"

                # --- [B] 標題與核心指標 ---
                st.markdown(f"### [{clean_id} {stock_name} ｜ {hit['status']}]({tv_url})")
                
                c1, c2, c3, c4 = st.columns([1, 1, 1.2, 1.2])
                c1.metric("現價", f"{hit['price']:.1f}")
                
                vol_val = hit['vol_diff']
                c2.metric("量能變動", f"{vol_val:.1f}%", delta=f"{vol_val:.1f}%")
                
                c3.write("本益比(PE)")
                c3.markdown(f"<div style='font-size: 16px; font-weight: bold;'>{pe_tag}</div>", unsafe_allow_html=True)
                
                c4.write("淨值比(PB)")
                c4.markdown(f"<div style='font-size: 16px; font-weight: bold;'>{pb_tag}</div>", unsafe_allow_html=True)
                
                # ==========================================
                # 💡 保留的「職業視角」在這裡！(緊接在 PB 的下面)
                # ==========================================
                if "pro" in hit:
                    pro = hit['pro']
                    decay_icon = "✅ 賣壓竭盡" if pro.get('decay') else "❌ 仍有賣壓"
                    st.info(f"💡 **職業視角**：{decay_icon} | {pro.get('signal', '')} | **策略**：{pro.get('action', '')}")

                # ==========================================
                # 🛑 完整的「自動風控看板」(修復了重複顯示的問題)
                # ==========================================
                if "stop_price" in hit:
                    k1, k2, k3 = st.columns(3)
                    k1.metric("🛑 建議停損", f"{hit['stop_price']:.1f}", 
                              delta=f"-{hit['risk_pct']:.1f}%", delta_color="inverse")
                    k2.metric("🎯 移動停利", f"{hit['profit_stop']:.1f}", help="參考 20MA 位置")
                    k3.write(f"⚖️ **最大風險**\n`{hit['risk_pct']:.1f}%`")

                # --- [E] 畫圖 (K棒 + 均線 + 布林通道 + 成交量) ---
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                
                df_plot = hit['df']
                fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                    vertical_spacing=0.03, row_heights=[0.8, 0.2])

                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), name="上軌", hoverinfo='none'), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.1)', name="下軌", hoverinfo='none'), row=1, col=1)

                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA10'], line=dict(color='#FFA500', width=1.5), name="10MA"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], line=dict(color='#FF1493', width=1.5), name="20MA"), row=1, col=1)
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA60'], line=dict(color='#32CD32', width=1.5), name="60MA"), row=1, col=1)

                fig.add_trace(go.Candlestick(
                    x=df_plot.index, open=df_plot['Open'], 
                    high=df_plot['High'], low=df_plot['Low'], 
                    close=df_plot['Close'], name="K棒",
                    increasing_line_color='#EF5350', # 漲：台股專屬紅色
                    decreasing_line_color='#26A69A'  # 跌：台股專屬綠色
                ), row=1, col=1)

                colors = ['#EF5350' if c >= o else '#26A69A' for c, o in zip(df_plot['Close'], df_plot['Open'])]
                fig.add_trace(go.Bar(
                    x=df_plot.index, y=df_plot['Volume'], 
                    marker_color=colors, name="成交量"
                ), row=2, col=1)

                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    xaxis2_rangeslider_visible=False,
                    margin=dict(l=10, r=10, t=30, b=10),
                    height=450,
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
                # --- [E] 畫圖與籌碼查哨站 (左右分割排版) ---
                import plotly.graph_objects as go
                from plotly.subplots import make_subplots
                
                # 🌟 將畫面切割為左右兩塊 (比例 7 : 3)
                col_chart, col_table = st.columns([7, 3])

                # ==========================================
                # 左半邊：K線圖區塊
                # ==========================================
                with col_chart:
                    df_plot = hit['df']
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                                        vertical_spacing=0.03, row_heights=[0.8, 0.2])

                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), name="上軌", hoverinfo='none'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.1)', name="下軌", hoverinfo='none'), row=1, col=1)

                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA10'], line=dict(color='#FFA500', width=1.5), name="10MA"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], line=dict(color='#FF1493', width=1.5), name="20MA"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA60'], line=dict(color='#32CD32', width=1.5), name="60MA"), row=1, col=1)

                    fig.add_trace(go.Candlestick(
                        x=df_plot.index, open=df_plot['Open'], 
                        high=df_plot['High'], low=df_plot['Low'], 
                        close=df_plot['Close'], name="K棒",
                        increasing_line_color='#EF5350', # 漲：台股專屬紅色
                        decreasing_line_color='#26A69A'  # 跌：台股專屬綠色
                    ), row=1, col=1)

                    colors = ['#EF5350' if c >= o else '#26A69A' for c, o in zip(df_plot['Close'], df_plot['Open'])]
                    fig.add_trace(go.Bar(
                        x=df_plot.index, y=df_plot['Volume'], 
                        marker_color=colors, name="成交量"
                    ), row=2, col=1)

                    fig.update_layout(
                        xaxis_rangeslider_visible=False,
                        xaxis2_rangeslider_visible=False,
                        margin=dict(l=10, r=10, t=30, b=10),
                        height=400, # 高度稍微縮減配合旁邊按鈕
                        showlegend=False
                    )
                    st.plotly_chart(fig, use_container_width=True)

                # ==========================================
                # 右半邊：籌碼查哨站 (快捷按鈕區)
                # ==========================================
                with col_table:
                    st.markdown("#### 🕵️‍♂️ 籌碼查哨站")
                    st.caption("點擊直接查看主力動向")

                    # 設定各大免費籌碼網站的專屬網址
                    wantgoo_url = f"https://www.wantgoo.com/stock/{clean_id}/institutional-investors/trend"
                    goodinfo_url = f"https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={clean_id}"
                    yahoo_url = f"https://tw.stock.yahoo.com/quote/{clean_id}/institutional-investors"

                    # 建立三個大按鈕，點擊直接開新分頁
                    st.link_button("🟢 玩股網 (籌碼集中度)", wantgoo_url, use_container_width=True)
                    st.link_button("🔵 Goodinfo (看三大法人)", goodinfo_url, use_container_width=True)
                    
                    st.info("💡 **實戰提示**：\n用左邊雷達確認【型態與量能】後，點擊上方按鈕確認籌碼！")

                st.divider()
