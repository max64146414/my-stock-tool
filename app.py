import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
import time
import json
import datetime

# ==========================================
# 📊 新增：FinMind 抓取法人籌碼工具
# ==========================================
@st.cache_data(ttl=3600) # 快取一小時，避免重複抓取被鎖 IP
def get_institutional_data(stock_id, days=60):
    try:
        from FinMind.data import DataLoader
        import datetime
        dl = DataLoader()
        
        # 抓取過去 60 天的資料來算 20 日均線
        start_dt = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime('%Y-%m-%d')
        df_inst = dl.taiwan_stock_institutional_investors_buy_sell(stock_id=stock_id, start_date=start_dt)
        
        if df_inst.empty:
            return pd.DataFrame()
            
        # 計算每天的「三大法人淨買賣超」(買進 - 賣出)
        df_inst['net_buy'] = df_inst['buy'] - df_inst['sell']
        
        # 依照日期加總 (把外資、投信、自營商加總成一個數字)
        df_net = df_inst.groupby('date')['net_buy'].sum().reset_index()
        df_net['date'] = pd.to_datetime(df_net['date'])
        df_net.set_index('date', inplace=True)
        
        return df_net
    except Exception as e:
        print(f"籌碼抓取失敗: {e}")
        return pd.DataFrame()

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

# --- 5. 核心分析函數 (🌟 整合週線保護與歷史回測) ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        # 🌟 為了算週線跟回測，我們把抓取時間拉長到 "2y" (兩年)
        df = yf.download(symbol, period="2y", progress=False, threads=False)
        if df.empty or len(df) < 100: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]

        # 🌟 新增：長線保護短線 (計算週線 20MA 趨勢)
        # 用 Pandas 把日線資料轉換成週線 (每週五收盤)
        df_weekly = df.resample('W-FRI').agg({'Close': 'last'}).dropna()
        if len(df_weekly) >= 20:
            w_ma20 = df_weekly['Close'].rolling(20).mean()
            w_ma20_curr = w_ma20.iloc[-1]
            w_ma20_prev = w_ma20.iloc[-2]
            is_weekly_up = w_ma20_curr >= w_ma20_prev  # 週線 20MA 是否向上
        else:
            is_weekly_up = True # 資料不足則預設放行

        close = df['Close'].astype(float).squeeze().dropna()
        volume = df['Volume'].astype(float).squeeze().dropna()
        
        # 為了回測，我們把所有的均線算出來
        ma10_all = close.rolling(10).mean()
        ma20_all = close.rolling(20).mean()
        ma60_all = close.rolling(60).mean()
        
        ma10, ma20, ma60 = ma10_all, ma20_all, ma60_all
        std20 = close.rolling(20).std()
        
        df['MA10'], df['MA20'], df['MA60'] = ma10, ma20, ma60
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
            # 🌟 加上 is_weekly_up (週線向上) 條件
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200 and is_weekly_up:
                dist_10, dist_20 = (curr_p - m10) / m10, (curr_p - m20) / m20
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    pro_metrics = check_professional_metrics(df.tail(40))
                    hit_data = {
                        "id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, 
                        "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(60), # 多抓一點給圖表
                        "status": "🛡️ 回檔支撐", "pro": pro_metrics, "w_trend": True
                    }

        # --- 模式 B: 均線糾纏 ---
        elif mode_choice == "均線糾纏 (底部突破)":
            ma_list = [m10, m20, m60_curr]
            spread = (max(ma_list) - min(ma_list)) / min(ma_list)
            # 🌟 加上 is_weekly_up (週線向上) 條件
            if spread < param1 and m60_curr >= m60_prev * 0.998 and curr_p > max(ma_list) and is_weekly_up:
                is_vol_boost = (today_vol / avg_vol_5d) >= param2 if avg_vol_5d > 0 else False
                status_text = "🚀 帶量突破" if is_vol_boost else "💤 糾纏待變"
                hit_data = {
                    "id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, 
                    "d10": ((curr_p-m10)/m10)*100, "d20": ((curr_p-m20)/m20)*100, 
                    "df": df.tail(60), "status": status_text, "spread": spread*100, "w_trend": True
                }

        # ==========================================
        # 🌟 新增：勝率回測引擎 (只針對有跳訊號的股票進行算力集中回測)
        # 邏輯：過去兩年內，只要發生類似訊號，20個交易日內有沒有賺到 10%？
        # ==========================================
        if hit_data:
            wins, total_signals = 0, 0
            try:
                # 建立歷史條件陣列
                if mode_choice == "均線糾纏 (底部突破)":
                    max_hist = pd.concat([ma10_all, ma20_all, ma60_all], axis=1).max(axis=1)
                    min_hist = pd.concat([ma10_all, ma20_all, ma60_all], axis=1).min(axis=1)
                    spread_hist = (max_hist - min_hist) / min_hist
                    # 找出歷史上「價格剛突破糾纏區」的日子
                    hist_signals = (spread_hist < param1) & (close > max_hist) & (close.shift(1) <= max_hist.shift(1))
                else:
                    # 找出歷史上「回測 20MA」的日子
                    hist_signals = (close > ma60_all) & (abs((close - ma20_all)/ma20_all) < param1) & (close.shift(1) > ma20_all * 1.05)
                
                signal_dates = df[hist_signals].index
                
                # 模擬進場：往後看 20 天，若最高價大於進場價 10% 即算贏
                for d in signal_dates[:-1]: # 排除掉今天
                    idx = df.index.get_loc(d)
                    if idx + 20 < len(df): 
                        entry_p = float(df['Close'].iloc[idx])
                        max_future = df['Close'].iloc[idx+1 : idx+21].max()
                        if max_future > entry_p * 1.10: 
                            wins += 1
                        total_signals += 1
                
                win_rate = (wins / total_signals * 100) if total_signals > 0 else 0
                hit_data['backtest'] = {"wins": wins, "total": total_signals, "rate": win_rate}
            except Exception as e:
                hit_data['backtest'] = {"wins": 0, "total": 0, "rate": 0}
            
            # --- 原本的 PE/PB 與 風控計算 ---
            try:
                t_obj = yf.Ticker(symbol)
                info = t_obj.info 
                hit_data['pe'] = info.get('trailingPE') or info.get('forwardPE')
                hit_data['pb'] = info.get('priceToBook') 
            except:
                hit_data['pe'], hit_data['pb'] = None, None
            
            struct_stop = df['Low'].iloc[-5:].min()
            hit_data["stop_price"] = struct_stop
            hit_data["profit_stop"] = m20            
            hit_data["risk_pct"] = ((curr_p - struct_stop) / curr_p) * 100
            
            return hit_data
            
        return None
    except Exception as e:
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
                # 🌟 新增 1：判斷週線趨勢標籤
                w_tag = "📈 週線多頭" if hit.get('w_trend') else "⚠️ 週線偏空"
                
                # 🌟 把週線標籤加進大標題裡面
                st.markdown(f"### [{clean_id} {stock_name} ｜ {hit['status']} ｜ {w_tag}]({tv_url})")
                
                # 🌟 新增 2：歷史回測戰績看板 (夾在標題跟價格中間)
                if 'backtest' in hit:
                    bt = hit['backtest']
                    if bt['total'] > 0:
                        st.warning(f"🔥 **大數據歷史回測 (近2年)**：本策略觸發 `{bt['total']}` 次，波段達標(+10%)共 `{bt['wins']}` 次 👉 **歷史勝率 {bt['rate']:.1f}%**")
                    else:
                        st.info("ℹ️ 近兩年首次出現此訊號，無歷史回測數據。")

                # (下面接著你原本的切欄位，完全不用動)
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
                # 左半邊：K線圖 + 成交量 + 法人籌碼曲線
                # ==========================================
                with col_chart:
                    df_plot = hit['df'].copy()
                    
                    # 🌟 呼叫籌碼函數，並將籌碼資料與 K 線資料對齊
                    df_inst = get_institutional_data(clean_id)
                    if not df_inst.empty:
                        # 把籌碼併入 K 線的 DataFrame
                        df_plot = df_plot.join(df_inst, how='left')
                        df_plot['net_buy'] = df_plot['net_buy'].fillna(0)
                        # 計算 20 日法人累計買賣超 (這就是你要的 20日籌碼趨勢)
                        df_plot['Inst_20d_Sum'] = df_plot['net_buy'].rolling(window=20, min_periods=1).sum()
                    else:
                        df_plot['Inst_20d_Sum'] = 0

                    # 🌟 將圖表切成 3 列 (K線 60%, 成交量 20%, 籌碼線 20%)
                    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                        vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2])

                    # --- 第一層：K線與均線 ---
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), name="上軌", hoverinfo='none'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.1)', name="下軌", hoverinfo='none'), row=1, col=1)

                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA10'], line=dict(color='#FFA500', width=1.5), name="10MA"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], line=dict(color='#FF1493', width=1.5), name="20MA"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA60'], line=dict(color='#32CD32', width=1.5), name="60MA"), row=1, col=1)

                    fig.add_trace(go.Candlestick(
                        x=df_plot.index, open=df_plot['Open'], 
                        high=df_plot['High'], low=df_plot['Low'], 
                        close=df_plot['Close'], name="K棒",
                        increasing_line_color='#EF5350', 
                        decreasing_line_color='#26A69A'  
                    ), row=1, col=1)

                    # --- 第二層：成交量 ---
                    colors = ['#EF5350' if c >= o else '#26A69A' for c, o in zip(df_plot['Close'], df_plot['Open'])]
                    fig.add_trace(go.Bar(
                        x=df_plot.index, y=df_plot['Volume'], 
                        marker_color=colors, name="成交量"
                    ), row=2, col=1)

                    # --- 第三層：🌟 20 日法人籌碼累計曲線 ---
                    # 如果 20 日累計大於 0 顯示紅色區塊，小於 0 顯示綠色區塊
                    fig.add_trace(go.Scatter(
                        x=df_plot.index, y=df_plot['Inst_20d_Sum'], 
                        line=dict(color='#9C27B0', width=2), 
                        fill='tozeroy', fillcolor='rgba(156, 39, 176, 0.2)',
                        name="20日法人累計"
                    ), row=3, col=1)

                    fig.update_layout(
                        xaxis_rangeslider_visible=False,
                        xaxis2_rangeslider_visible=False,
                        xaxis3_rangeslider_visible=False,
                        margin=dict(l=10, r=10, t=30, b=10),
                        height=550, # 稍微拉高一點容納三層圖表
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
