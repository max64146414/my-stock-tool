import streamlit as st
import pandas as pd
import yfinance as yf
from FinMind.data import DataLoader
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import json
import datetime
import requests 

# ==========================================
# 🔒 模組 1：簡易密碼鎖
# ==========================================
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<h1 style='text-align: center;'>🐝 🐝 🐝 🐝 🐝</h1>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center;'>阿峰的回測追蹤測試</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>專屬雷達系統，請輸入通關密語</p>", unsafe_allow_html=True)
        
        _, col_mid, _ = st.columns([1, 2, 1])
        with col_mid:
            password = st.text_input("密碼", type="password")
            if st.button("確認登入"):
                user_map = {"19930522": "阿峰", "820522": "脆皮", "0522": "柔", "159632": "阿曼達"}
                if password in user_map:
                    st.session_state["password_correct"] = True
                    user_name = user_map[password]
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
st.title("🏹 台股量價監測：多維度動能雷達")

# --- 2. 職業動能分析與型態偵測 ---
def check_professional_metrics(df):
    try:
        bodies = abs(df['Close'] - df['Open'])
        is_black = df['Close'] < df['Open']
        black_bodies = bodies[is_black]
        recent_black = black_bodies.iloc[-3:].mean() if len(black_bodies) >= 2 else 0
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

def detect_patterns(df):
    patterns = []
    close, high, low = df['Close'], df['High'], df['Low']
    
    # W 底
    recent_lows = low.tail(40).nsmallest(2)
    if len(recent_lows) == 2 and abs(recent_lows.iloc[0] - recent_lows.iloc[1]) / recent_lows.iloc[0] < 0.03:
        neckline = high.loc[recent_lows.index[0] : recent_lows.index[1]].max()
        if close.iloc[-1] > neckline * 0.99: 
            patterns.append({"name": "W底型態 (雙重底)", "icon": "📈", "adv": "底部成型，若突破頸線可視為強烈買訊，停損設右腳低點。"})
            
    # 多頭旗型
    ma20 = close.rolling(20).mean()
    if close.iloc[-1] > ma20.iloc[-1] and close.iloc[-1] < close.iloc[-5:].max():
         if (close.iloc[-5:].max() - close.iloc[-1]) / close.iloc[-1] < 0.05:
             patterns.append({"name": "多頭旗型整理", "icon": "🚩", "adv": "強勢股中繼休息，隨時可能發動下一波，可沿 10MA 試單。"})

    # 布林壓縮
    std20 = close.rolling(20).std()
    bb_width = (4 * std20.iloc[-1]) / ma20.iloc[-1]
    if bb_width < 0.08: 
        patterns.append({"name": "布林極度壓縮 (洗盤尾聲)", "icon": "🗜️", "adv": "變盤在即！即將表態，請密切關注出量方向，帶量長紅即進場。"})

    return patterns

# --- 3. 側邊欄 ---
with st.sidebar:
    st.header("🔍 模式選擇")
    mode = st.radio("選擇監測模式", ["均線回檔 (趨勢追蹤)", "均線糾纏 (底部突破)", "箱型突破 (達華斯動能)"])
    
    st.divider()
    st.header("⚙️ 掃描設定")
    industry_choice = st.selectbox("選擇產業類別", [
        "★台積電大聯盟 (設備/耗材/IP)", "半導體", "光電業", "電子零組件", 
        "電腦及週邊設備業", "通信網路業", "電機機械", "其他電子業"
    ])
    
    if mode == "均線回檔 (趨勢追蹤)":
        sensitivity = st.slider("靠近均線門檻 (%)", 0.1, 8.0, 3.5) / 100
    elif mode == "均線糾纏 (底部突破)":
        entangle_limit = st.slider("均線糾纏寬度 (%)", 0.5, 5.0, 2.0) / 100
        vol_boost = st.slider("帶量突破門檻 (倍)", 1.0, 5.0, 1.8)
    elif mode == "箱型突破 (達華斯動能)": 
        box_period = st.slider("箱型觀察期 (天)", 10, 60, 20)
        box_width = st.slider("箱體最大振幅 (%)", 5.0, 25.0, 15.0) / 100

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
    backup_map = {"電子零組件": ["2317.TW", "2308.TW", "3037.TW", "2367.TW", "2313.TW", "2368.TW", "8046.TW", "6213.TW"]}
    try:
        with open('stock_list.json', 'r', encoding='utf-8') as f:
            all_lists = json.load(f)
        clean_cat = category.replace("★", "").replace("業", "").strip()
        for raw_key in all_lists.keys():
            clean_key = raw_key.replace("★", "").replace("業", "").strip()
            if clean_cat in clean_key or clean_key in clean_cat:
                res = all_lists[raw_key]
                if len(res) > 0: return res
        dl = DataLoader()
        df = dl.taiwan_stock_info()
        stocks = df[df['industry_category'].str.contains(clean_cat)]
        res = [f"{s}.TW" for s in stocks['stock_id'].tolist() if len(s) == 4]
        return res if len(res) > 0 else backup_map.get(category, ["2330.TW"])
    except:
        return backup_map.get(category, ["2330.TW"])

# --- 5. 核心分析函數 ---
def analyze_stock(symbol, mode_choice, param1, param2=None):
    try:
        df = yf.download(symbol, period="2y", progress=False, threads=False)
        if df.empty or len(df) < 100: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df.columns = [str(c).capitalize() for c in df.columns]

        df_weekly = df.resample('W-FRI').agg({'Close': 'last'}).dropna()
        if len(df_weekly) >= 20:
            w_ma20 = df_weekly['Close'].rolling(20).mean()
            is_weekly_up = w_ma20.iloc[-1] >= w_ma20.iloc[-2]  
        else:
            is_weekly_up = True 

        close = df['Close'].astype(float).squeeze().dropna()
        volume = df['Volume'].astype(float).squeeze().dropna()
        
        ma10_all, ma20_all, ma60_all = close.rolling(10).mean(), close.rolling(20).mean(), close.rolling(60).mean()
        df['MA10'], df['MA20'], df['MA60'] = ma10_all, ma20_all, ma60_all
        std20 = close.rolling(20).std()
        df['BB_Upper'], df['BB_Lower'] = ma20_all + 2 * std20, ma20_all - 2 * std20
        
        today_vol = volume.iloc[-1]
        avg_vol_5d = volume.iloc[-6:-1].mean()
        vol_diff_pct = ((today_vol - avg_vol_5d) / avg_vol_5d) * 100 if avg_vol_5d > 0 else 0
        
        curr_p = float(close.iloc[-1])
        m10, m20, m60_curr = float(ma10_all.iloc[-1]), float(ma20_all.iloc[-1]), float(ma60_all.iloc[-1])
        m60_prev = float(ma60_all.iloc[-2])

        hit_data = None
        
        if mode_choice == "均線回檔 (趨勢追蹤)":
            if curr_p > m60_curr and m60_curr > m60_prev and avg_vol_5d > 200 and is_weekly_up:
                dist_10, dist_20 = (curr_p - m10) / m10, (curr_p - m20) / m20
                if abs(dist_10) < param1 or abs(dist_20) < param1:
                    hit_data = {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "d10": dist_10*100, "d20": dist_20*100, "df": df.tail(60), "status": "🛡️ 回檔支撐", "pro": check_professional_metrics(df.tail(40)), "w_trend": True}

        elif mode_choice == "均線糾纏 (底部突破)":
            ma_list = [m10, m20, m60_curr]
            spread = (max(ma_list) - min(ma_list)) / min(ma_list)
            if spread < param1 and m60_curr >= m60_prev * 0.998 and curr_p > max(ma_list) and is_weekly_up:
                is_vol_boost = (today_vol / avg_vol_5d) >= param2 if avg_vol_5d > 0 else False
                status_text = "🚀 帶量突破" if is_vol_boost else "💤 糾纏待變"
                hit_data = {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "df": df.tail(60), "status": status_text, "spread": spread*100, "w_trend": True}

        elif mode_choice == "箱型突破 (達華斯動能)":
            period, max_width = int(param1), param2
            past_highs, past_lows = df['High'].iloc[-period-1:-1], df['Low'].iloc[-period-1:-1]
            box_top, box_bottom = past_highs.max(), past_lows.min()
            
            if box_bottom > 0 and ((box_top - box_bottom) / box_bottom) <= max_width:
                if curr_p > box_top and today_vol > avg_vol_5d * 1.5 and is_weekly_up:
                    hit_data = {"id": symbol, "price": curr_p, "vol_diff": vol_diff_pct, "df": df.tail(80), "status": "📦 箱型突破", "w_trend": True, "box_top": box_top, "box_bot": box_bottom}

        if hit_data:
            hit_data['patterns'] = detect_patterns(df)
            
            wins, total_signals = 0, 0
            try:
                if mode_choice == "均線糾纏 (底部突破)":
                    max_h, min_h = pd.concat([ma10_all, ma20_all, ma60_all], axis=1).max(axis=1), pd.concat([ma10_all, ma20_all, ma60_all], axis=1).min(axis=1)
                    hist_signals = ((max_h - min_h) / min_h < param1) & (close > max_h) & (close.shift(1) <= max_h.shift(1))
                elif mode_choice == "均線回檔 (趨勢追蹤)":
                    hist_signals = (close > ma60_all) & (abs((close - ma20_all)/ma20_all) < param1) & (close.shift(1) > ma20_all * 1.05)
                else:
                    hist_signals = pd.Series([False]*len(df), index=df.index) 
                
                for d in df[hist_signals].index[:-1]: 
                    idx = df.index.get_loc(d)
                    if idx + 20 < len(df): 
                        if df['Close'].iloc[idx+1 : idx+21].max() > float(df['Close'].iloc[idx]) * 1.10: wins += 1
                        total_signals += 1
                hit_data['backtest'] = {"wins": wins, "total": total_signals, "rate": (wins / total_signals * 100) if total_signals > 0 else 0}
            except:
                hit_data['backtest'] = {"wins": 0, "total": 0, "rate": 0}
            
            try:
                info = yf.Ticker(symbol).info 
                hit_data['pe'] = info.get('trailingPE') or info.get('forwardPE')
                hit_data['pb'] = info.get('priceToBook') 
            except:
                hit_data['pe'] = hit_data['pb'] = None
            
            struct_stop = df['Low'].iloc[-5:].min()
            hit_data["stop_price"] = struct_stop
            hit_data["profit_stop"] = m20            
            hit_data["risk_pct"] = ((curr_p - struct_stop) / curr_p) * 100
            return hit_data
        return None
    except Exception as e:
        return None

# --- 6. 執行顯示 ---
if run_btn:
    full_list = get_full_industry_list(industry_choice)
    st.info(f"🔎 模式：{mode} | 正在掃描 {len(full_list)} 檔標的...")
    hits, bar = [], st.progress(0)
    for i, s in enumerate(full_list):
        if mode == "均線回檔 (趨勢追蹤)": p1, p2 = sensitivity, None
        elif mode == "均線糾纏 (底部突破)": p1, p2 = entangle_limit, vol_boost
        else: p1, p2 = box_period, box_width
        
        res = analyze_stock(s, mode, p1, p2)
        if res: hits.append(res)
        bar.progress((i + 1) / len(full_list))
    
    if hits:
        if mode == "均線回檔 (趨勢追蹤)": hits = sorted(hits, key=lambda x: abs(x.get('d20', 100)))
        elif mode == "均線糾纏 (底部突破)": hits = sorted(hits, key=lambda x: x.get('spread', 100))
        else: hits = sorted(hits, key=lambda x: x.get('vol_diff', 0), reverse=True) 
        else:
        st.divider()
        st.warning(f"📭 **掃描完畢！** 在這個產業中，今天沒有股票符合【{mode}】的嚴格條件。\n\n💡 實戰建議：這代表目前沒有標準的進場訊號，請保持空手耐心等待，或是到左側把「帶量門檻」調低、「箱體振幅」調寬再試一次！")

        st.divider()
        st.success(f"🎯 掃描完成！共抓出 {len(hits)} 檔符合條件的標的。")

        @st.cache_data(ttl=86400)
        def get_stock_names():
            try:
                df_info = DataLoader().taiwan_stock_info()
                return dict(zip(df_info['stock_id'], df_info['stock_name']))
            except: return {}
        
        name_map = get_stock_names()

        for hit in hits:
            with st.container():
                clean_id = hit['id'].replace(".TW", "")
                stock_name = name_map.get(clean_id, "") 
                tv_url = f"https://tw.tradingview.com/symbols/TWSE-{clean_id}/"
                
                pe_val, pb_val = hit.get('pe'), hit.get('pb')
                pe_tag = f"🟢 低估 ({pe_val:.1f})" if pe_val and pe_val < 15 else (f"🟡 常態 ({pe_val:.1f})" if pe_val and pe_val < 25 else (f"🔴 偏高 ({pe_val:.1f})" if pe_val else "⚪ 暫無數據"))
                pb_tag = f"🟢 超跌便宜 ({pb_val:.2f})" if pb_val and pb_val < 1.5 else (f"🟡 常態 ({pb_val:.2f})" if pb_val and pb_val < 3.5 else (f"🔴 昂貴 ({pb_val:.2f})" if pb_val else "⚪ 暫無數據"))

                w_tag = "📈 週線多頭" if hit.get('w_trend') else "⚠️ 週線偏空"
                st.markdown(f"### [{clean_id} {stock_name} ｜ {hit['status']} ｜ {w_tag}]({tv_url})")
                
                if 'backtest' in hit and mode != "箱型突破 (達華斯動能)":
                    bt = hit['backtest']
                    if bt['total'] > 0:
                        st.warning(f"🔥 **大數據歷史回測 (近2年)**：觸發 `{bt['total']}` 次，波段達標(+10%)共 `{bt['wins']}` 次 👉 **歷史勝率 {bt['rate']:.1f}%**")
                    else:
                        st.info("ℹ️ 近兩年首次出現此訊號，無歷史回測數據。")

                c1, c2, c3, c4 = st.columns([1, 1, 1.2, 1.2])
                c1.metric("現價", f"{hit['price']:.1f}")
                vol_val = hit['vol_diff']
                c2.metric("量能變動", f"{vol_val:.1f}%", delta=f"{vol_val:.1f}%")
                c3.write("本益比(PE)")
                c3.markdown(f"<div style='font-size: 16px; font-weight: bold;'>{pe_tag}</div>", unsafe_allow_html=True)
                c4.write("淨值比(PB)")
                c4.markdown(f"<div style='font-size: 16px; font-weight: bold;'>{pb_tag}</div>", unsafe_allow_html=True)
                
                if "pro" in hit:
                    pro = hit['pro']
                    st.info(f"💡 **職業視角**：{'✅ 賣壓竭盡' if pro.get('decay') else '❌ 仍有賣壓'} | {pro.get('signal', '')} | **策略**：{pro.get('action', '')}")

                if "stop_price" in hit:
                    k1, k2, k3 = st.columns(3)
                    k1.metric("🛑 建議停損", f"{hit['stop_price']:.1f}", delta=f"-{hit['risk_pct']:.1f}%", delta_color="inverse")
                    k2.metric("🎯 移動停利", f"{hit['profit_stop']:.1f}")
                    k3.write(f"⚖️ **最大風險**\n`{hit['risk_pct']:.1f}%`")

                col_chart, col_table = st.columns([7, 3])

                # ====== 左半邊畫圖 (拔除法人籌碼，恢復雙層結構) ======
                with col_chart:
                    df_plot = hit['df'].copy()
                    df_plot.index = pd.to_datetime(df_plot.index).tz_localize(None).normalize()

                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.8, 0.2])

                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Upper'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), name="上軌", hoverinfo='none'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['BB_Lower'], line=dict(color='rgba(150, 150, 150, 0.5)', width=1, dash='dot'), fill='tonexty', fillcolor='rgba(150, 150, 150, 0.1)', name="下軌", hoverinfo='none'), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA10'], line=dict(color='#FFA500', width=1.5), name="10MA"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA20'], line=dict(color='#FF1493', width=1.5), name="20MA"), row=1, col=1)
                    fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['MA60'], line=dict(color='#32CD32', width=1.5), name="60MA"), row=1, col=1)

                    if mode == "箱型突破 (達華斯動能)" and "box_top" in hit:
                        fig.add_hline(y=hit["box_top"], line_dash="dash", line_color="red", row=1, col=1, annotation_text="箱頂")
                        fig.add_hline(y=hit["box_bot"], line_dash="dash", line_color="green", row=1, col=1, annotation_text="箱底")

                    fig.add_trace(go.Candlestick(
                        x=df_plot.index, open=df_plot['Open'], high=df_plot['High'], low=df_plot['Low'], close=df_plot['Close'], name="K棒",
                        increasing_line_color='#EF5350', decreasing_line_color='#26A69A'  
                    ), row=1, col=1)

                    colors = ['#EF5350' if c >= o else '#26A69A' for c, o in zip(df_plot['Close'], df_plot['Open'])]
                    fig.add_trace(go.Bar(x=df_plot.index, y=df_plot['Volume'], marker_color=colors, name="成交量"), row=2, col=1)

                    fig.update_layout(xaxis_rangeslider_visible=False, xaxis2_rangeslider_visible=False, margin=dict(l=10, r=10, t=30, b=10), height=450, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)

                # ====== 右半邊按鈕與 AI 提示 ======
                with col_table:
                    st.markdown("#### 🕵️‍♂️ 籌碼查哨站")
                    wantgoo_url = f"https://www.wantgoo.com/stock/{clean_id}/institutional-investors/trend"
                    goodinfo_url = f"https://goodinfo.tw/tw/ShowBuySaleChart.asp?STOCK_ID={clean_id}"
                    st.link_button("🟢 玩股網 (籌碼集中度)", wantgoo_url, use_container_width=True)
                    st.link_button("🔵 Goodinfo (看三大法人)", goodinfo_url, use_container_width=True)
                    
                    st.divider()
                    st.markdown("#### 📐 技術型態偵測")
                    if 'patterns' in hit and hit['patterns']:
                        for p in hit['patterns']:
                            st.success(f"**{p['icon']} {p['name']}**\n\n💡 {p['adv']}")
                    else:
                        st.info("目前無特殊型態，請依循策略邏輯操作。")
                        
                    st.divider()
                    st.markdown("#### 🤖 AI 深度診斷指令")
                    bt_str = f"近2年觸發 {hit['backtest']['total']} 次，勝率 {hit['backtest']['rate']:.1f}%" if 'backtest' in hit and hit['backtest']['total'] > 0 else "首次觸發或無回測資料"
                    
                    ai_prompt = (
                        f"阿峰雷達呼叫 🐝：請幫我深度分析【{clean_id} {stock_name}】。\n\n"
                        f"📊 目前雷達偵測數據：\n"
                        f"- 技術狀態：{hit['status']} ({w_tag})\n"
                        f"- 價格量能：現價 {hit['price']:.1f}，量能變化 {vol_val:.1f}%\n"
                        f"- 歷史勝率：{bt_str}\n\n"
                        f"👉 請結合目前的台股大環境，幫我評估這檔股票的【進場優勢】、【籌碼面可能隱患】，並給我具體的【實戰試單策略】。"
                    )
                    st.code(ai_prompt, language="text")

                st.divider()
                try:
                    send_discord_alert(hit, stock_name)
                except:
                    pass
