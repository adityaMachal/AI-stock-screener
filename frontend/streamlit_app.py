import os
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import yfinance as yf

# Environment configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AlphaScreener AI | Executive Financial Analytics",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------
# Custom Modern SaaS CSS
# ---------------------------------------------------------
st.markdown("""
<style>
    /* Global styles */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    
    /* Card Container */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    
    /* Custom Badges */
    .badge-triggered {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid #fecaca;
    }
    .badge-monitoring {
        background-color: #e0f2fe;
        color: #0369a1;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
        border: 1px solid #bae6fd;
    }
    .badge-symbol {
        background-color: #f1f5f9;
        color: #334155;
        padding: 3px 8px;
        border-radius: 6px;
        font-family: monospace;
        font-weight: 700;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
    }
    
    /* Sidebar user card */
    .user-profile-badge {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 0.8rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------
if "token" not in st.session_state:
    st.session_state["token"] = None
if "user" not in st.session_state:
    st.session_state["user"] = None
if "query_history" not in st.session_state:
    st.session_state["query_history"] = []
if "search_query" not in st.session_state:
    st.session_state["search_query"] = ""

def logout():
    st.session_state["token"] = None
    st.session_state["user"] = None
    st.session_state["query_history"] = []
    st.session_state["search_query"] = ""
    st.rerun()

def check_auth_response(res):
    """Detects 401 Unauthorized / expired JWT and resets session state gracefully."""
    if res.status_code == 401:
        st.session_state["token"] = None
        st.session_state["user"] = None
        st.session_state["query_history"] = []
        st.session_state["search_query"] = ""
        st.error("⚠️ Your session has expired or is invalid. Please sign in again.")
        st.rerun()

# ---------------------------------------------------------
# VIEW 1: UNAUTHENTICATED GATEWAY (Sign In / Create Account)
# ---------------------------------------------------------
if not st.session_state["token"]:
    col_l, col_center, col_r = st.columns([1, 2, 1])
    
    with col_center:
        st.markdown("<h1 style='text-align: center; margin-bottom: 0;'>📈 AlphaScreener AI</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #64748b; font-size: 1.1rem; margin-bottom: 2rem;'>Institutional-Grade Financial Screening & Portfolio Intelligence</p>", unsafe_allow_html=True)
        
        tab_login, tab_register = st.tabs(["🔐 Sign In", "✨ Create Account"])
        
        with tab_login:
            st.markdown("#### Welcome Back")
            st.caption("Sign in with your username or email to access your portfolio and screener.")
            
            login_id = st.text_input("Username or Email", key="login_id")
            login_pass = st.text_input("Password", type="password", key="login_pass")
            
            col_b1, col_b2 = st.columns([2, 1])
            with col_b1:
                if st.button("Sign In to Platform", type="primary", use_container_width=True):
                    if not login_id or not login_pass:
                        st.error("Please enter both username/email and password.")
                    else:
                        with st.spinner("Authenticating..."):
                            try:
                                res = requests.post(
                                    f"{API_URL}/auth/login",
                                    data={"username": login_id.strip(), "password": login_pass},
                                    timeout=20.0
                                )
                                if res.status_code == 200:
                                    data = res.json()
                                    st.session_state["token"] = data.get("access_token")
                                    st.session_state["user"] = data.get("user")
                                    st.success("Authenticated successfully!")
                                    st.rerun()
                                else:
                                    err_msg = res.json().get("detail", "Invalid username or password.")
                                    st.error(f"❌ {err_msg}")
                            except requests.exceptions.Timeout:
                                st.error("❌ Authentication request timed out after 20 seconds.")
                            except Exception as e:
                                st.error(f"❌ Connection error: {e}")
            
            with col_b2:
                if st.button("Quick Demo", help="Fill with test credentials", use_container_width=True):
                    with st.spinner("Logging in as demo user..."):
                        try:
                            res = requests.post(
                                f"{API_URL}/auth/login",
                                data={"username": "testuser", "password": "password123"},
                                timeout=20.0
                            )
                            if res.status_code == 200:
                                data = res.json()
                                st.session_state["token"] = data.get("access_token")
                                st.session_state["user"] = data.get("user")
                                st.rerun()
                            else:
                                st.error("Demo account not seeded yet. Use Create Account.")
                        except Exception as e:
                            st.error(f"Connection failed: {e}")
        
        with tab_register:
            st.markdown("#### Create Your Account")
            st.caption("Register for personalized stock screening, alerts, and portfolio tracking.")
            
            reg_name = st.text_input("Full Name", placeholder="e.g. Warren Buffett", key="reg_name")
            reg_email = st.text_input("Email Address", placeholder="e.g. investor@fund.com", key="reg_email")
            reg_user = st.text_input("Choose Username", placeholder="e.g. wbuffett", key="reg_user")
            reg_pass1 = st.text_input("Create Password (min 6 characters)", type="password", key="reg_pass1")
            reg_pass2 = st.text_input("Confirm Password", type="password", key="reg_pass2")
            
            if st.button("Register Account", type="primary", use_container_width=True):
                if not reg_user or not reg_email or not reg_pass1:
                    st.error("Please fill in all required fields.")
                elif reg_pass1 != reg_pass2:
                    st.error("Passwords do not match.")
                elif len(reg_pass1) < 6:
                    st.error("Password must be at least 6 characters.")
                elif "@" not in reg_email or "." not in reg_email:
                    st.error("Please enter a valid email address.")
                else:
                    with st.spinner("Creating account..."):
                        try:
                            res = requests.post(
                                f"{API_URL}/auth/register",
                                json={
                                    "username": reg_user.strip(),
                                    "email": reg_email.strip().lower(),
                                    "full_name": reg_name.strip() if reg_name else None,
                                    "password": reg_pass1
                                },
                                timeout=20.0
                            )
                            if res.status_code == 201:
                                data = res.json()
                                st.session_state["token"] = data.get("access_token")
                                st.session_state["user"] = data.get("user")
                                st.success("🎉 Account created! Welcome to AlphaScreener.")
                                st.rerun()
                            else:
                                err_msg = res.json().get("detail", "Registration failed.")
                                st.error(f"❌ {err_msg}")
                        except requests.exceptions.Timeout:
                            st.error("❌ Registration request timed out.")
                        except Exception as e:
                            st.error(f"❌ Connection error: {e}")

# ---------------------------------------------------------
# VIEW 2: AUTHENTICATED EXECUTIVE DASHBOARD
# ---------------------------------------------------------
else:
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    
    # Auto-validate active session token; reset session gracefully if expired or invalid
    try:
        verify_res = requests.get(f"{API_URL}/auth/me", headers=headers, timeout=5.0)
        if verify_res.status_code == 401:
            st.session_state["token"] = None
            st.session_state["user"] = None
            st.session_state["query_history"] = []
            st.session_state["search_query"] = ""
            st.warning("⚠️ Your session has expired. Please sign in again.")
            st.rerun()
        elif verify_res.status_code == 200:
            st.session_state["user"] = verify_res.json()
    except Exception:
        pass

    user_info = st.session_state.get("user") or {}
    display_name = user_info.get("full_name") or user_info.get("username") or "Investor"
    user_email = user_info.get("email") or "Active Session"
    
    # --- Sidebar Navigation ---
    with st.sidebar:
        st.markdown("### 📈 AlphaScreener AI")
        
        # User profile badge
        st.markdown(f"""
        <div class="user-profile-badge">
            <div style="font-weight: 700; font-size: 1rem; color: #0f172a;">👤 {display_name}</div>
            <div style="font-size: 0.8rem; color: #64748b;">{user_email}</div>
        </div>
        """, unsafe_allow_html=True)
        
        page = st.radio(
            "Navigation",
            ["🔍 AI Screener", "💼 Portfolio Tracker", "🔔 Smart Alerts", "👤 My Profile"],
            label_visibility="collapsed"
        )
        
        st.divider()
        if st.button("🚪 Sign Out", use_container_width=True):
            logout()
            
        st.divider()
        st.markdown("##### 🕒 Recent Searches")
        if st.session_state["query_history"]:
            for q in reversed(st.session_state["query_history"][-5:]):
                if st.button(f"🔍 {q}", key=f"hist_{q}", use_container_width=True):
                    st.session_state["search_query"] = q
                    st.rerun()
        else:
            st.caption("No recent queries yet.")

    # -----------------------------------------------------
    # PAGE: 🔍 AI Screener
    # -----------------------------------------------------
    if page == "🔍 AI Screener":
        st.title("Natural Language Stock Screener")
        st.caption("Ask questions in plain English. The AI parses your criteria into SQL and filters 100+ global stocks.")
        
        # Suggestion Chips
        st.markdown("**Try a sample prompt:**")
        chip_col1, chip_col2, chip_col3, chip_col4 = st.columns(4)
        with chip_col1:
            if st.button("💡 Tech with PE < 35", use_container_width=True):
                st.session_state["search_query"] = "Tech stocks with PE < 35"
                st.rerun()
        with chip_col2:
            if st.button("💡 Healthcare Companies", use_container_width=True):
                st.session_state["search_query"] = "Healthcare companies"
                st.rerun()
        with chip_col3:
            if st.button("💡 Financials Cap > 50B", use_container_width=True):
                st.session_state["search_query"] = "Financials with market cap > 50B"
                st.rerun()
        with chip_col4:
            if st.button("💡 Growth > 10%", use_container_width=True):
                st.session_state["search_query"] = "Companies with growth > 10"
                st.rerun()

        # Search bar
        col_q, col_btn = st.columns([5, 1])
        with col_q:
            query_val = st.text_input(
                "Enter investment query:",
                value=st.session_state.get("search_query", ""),
                placeholder="e.g. 'Technology stocks with PE < 30 and revenue growth > 10'",
                label_visibility="collapsed"
            )
        with col_btn:
            run_btn = st.button("Analyze & Run", type="primary", use_container_width=True)

        if (run_btn or st.session_state.get("search_query")) and query_val:
            if query_val not in st.session_state["query_history"]:
                st.session_state["query_history"].append(query_val)
                
            with st.spinner("🤖 Translating query and searching market database..."):
                try:
                    res = requests.post(f"{API_URL}/query/", json={"query": query_val}, headers=headers, timeout=20.0)
                    if res.status_code == 200:
                        data = res.json()
                        results = data.get("results", [])
                        
                        if results:
                            df = pd.DataFrame(results)
                            st.success(f"✅ Found {len(results)} matching stocks!")
                            
                            # KPI Cards
                            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
                            kpi1.metric("Matches Found", len(results))
                            kpi2.metric("Average P/E", f"{df['pe_ratio'].mean():.2f}" if 'pe_ratio' in df.columns and not df['pe_ratio'].dropna().empty else "N/A")
                            kpi3.metric("Median Market Cap", f"${df['market_cap'].median() / 1e9:,.1f}B" if 'market_cap' in df.columns and not df['market_cap'].dropna().empty else "N/A")
                            kpi4.metric("Leading Sector", df['sector'].mode()[0] if 'sector' in df.columns and not df['sector'].dropna().empty else "N/A")
                            
                            # Results Table
                            st.markdown("#### Matched Companies")
                            st.dataframe(df, use_container_width=True)
                            
                            # Visualizations
                            col_c1, col_c2 = st.columns(2)
                            with col_c1:
                                if 'pe_ratio' in df.columns and not df['pe_ratio'].dropna().empty:
                                    st.markdown("##### Valuation Comparison (P/E Ratio)")
                                    fig_pe = px.bar(
                                        df, x="symbol", y="pe_ratio", color="sector",
                                        title="P/E Multiples by Symbol",
                                        template="plotly_white",
                                        text_auto=".1f"
                                    )
                                    st.plotly_chart(fig_pe, use_container_width=True)
                            with col_c2:
                                if 'sector' in df.columns:
                                    st.markdown("##### Sector Diversification")
                                    fig_sec = px.pie(
                                        df, names="sector", hole=0.45,
                                        title="Sector Distribution of Results"
                                    )
                                    st.plotly_chart(fig_sec, use_container_width=True)
                        else:
                            st.warning("No companies matched your specified criteria. Try widening your thresholds.")
                    elif res.status_code == 401:
                        check_auth_response(res)
                    elif res.status_code == 504:
                        st.error("⏱️ Query timed out after 20 seconds. Please try a more specific search.")
                    else:
                        st.error(f"❌ Backend Error: {res.json().get('detail', 'Unknown error')}")
                except requests.exceptions.Timeout:
                    st.error("⏱️ Request timed out after 20 seconds.")
                except Exception as e:
                    st.error(f"❌ Connection error: {e}")

    # -----------------------------------------------------
    # PAGE: 💼 Portfolio Tracker
    # -----------------------------------------------------
    elif page == "💼 Portfolio Tracker":
        st.title("Portfolio & Position Management")
        st.caption("Real-time valuation, profit & loss analytics, position trimming, and sector diversification.")
        
        try:
            res = requests.get(f"{API_URL}/portfolio/", headers=headers, timeout=20.0)
            if res.status_code == 401:
                check_auth_response(res)
            elif res.status_code == 200:
                p_data = res.json()
                if p_data:
                    df_p = pd.DataFrame(p_data)
                    
                    total_val = df_p['total_value'].sum()
                    total_cost = (df_p['purchase_price'] * df_p['quantity']).sum()
                    total_pl = df_p['profit_loss'].sum()
                    pl_pct = (total_pl / total_cost * 100) if total_cost > 0 else 0.0
                    
                    # Executive Metrics Row
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Total Market Value", f"${total_val:,.2f}")
                    m2.metric("Total Unrealized P/L", f"${total_pl:,.2f}", delta=f"{pl_pct:+.2f}%")
                    m3.metric("Total Invested", f"${total_cost:,.2f}")
                    m4.metric("Active Holdings", len(df_p))
                    
                    st.divider()
                    
                    # 30-Day Trend Chart
                    st.markdown("#### 📈 30-Day Cumulative Portfolio Value")
                    with st.spinner("Compiling historical performance..."):
                        try:
                            symbols = df_p['symbol'].unique().tolist()
                            if symbols:
                                df_hist = yf.download(symbols, period="1mo", progress=False)
                                if 'Close' in df_hist.columns:
                                    close_df = df_hist['Close']
                                    if isinstance(close_df, pd.Series):
                                        close_df = close_df.to_frame(name=symbols[0])
                                    close_df = close_df.ffill()
                                    
                                    quantities = df_p.set_index('symbol')['quantity'].to_dict()
                                    trend_series = pd.Series(0, index=close_df.index)
                                    for sym in close_df.columns:
                                        if sym in quantities:
                                            trend_series += close_df[sym] * quantities[sym]
                                            
                                    trend_df = trend_series.reset_index()
                                    trend_df.columns = ["Date", "Portfolio Value"]
                                    fig_trend = px.line(
                                        trend_df, x="Date", y="Portfolio Value",
                                        title="Portfolio Net Worth Over Time",
                                        template="plotly_white"
                                    )
                                    st.plotly_chart(fig_trend, use_container_width=True)
                        except Exception as e:
                            st.caption(f"Historical trend unavailable: {e}")
                    
                    # Holdings Table & Actions
                    col_holdings, col_charts = st.columns([3, 2])
                    
                    with col_holdings:
                        st.markdown("#### Active Positions")
                        display_df = df_p[['id', 'symbol', 'company_name', 'quantity', 'purchase_price', 'current_price', 'total_value', 'profit_loss', 'pl_percent']]
                        st.dataframe(
                            display_df.style.format({
                                'purchase_price': '${:,.2f}',
                                'current_price': '${:,.2f}',
                                'total_value': '${:,.2f}',
                                'profit_loss': '${:+,.2f}',
                                'pl_percent': '{:+.2f}%'
                            }),
                            use_container_width=True
                        )
                        
                        # Position Trade Operations
                        st.markdown("##### 🔄 Trade / Manage Positions")
                        tab_buy, tab_sell, tab_del = st.tabs(["➕ Buy / Add", "➖ Sell / Trim", "🗑️ Delete Position"])
                        
                        with tab_buy:
                            c_b1, c_b2, c_b3 = st.columns(3)
                            with c_b1: buy_sym = st.text_input("Ticker Symbol", placeholder="e.g. AAPL", key="buy_sym")
                            with c_b2: buy_qty = st.number_input("Shares", min_value=1, value=10, key="buy_qty")
                            with c_b3: buy_px = st.number_input("Price Paid ($)", min_value=0.01, value=150.0, key="buy_px")
                            if st.button("Execute Buy Order", type="primary"):
                                if buy_sym:
                                    b_res = requests.post(
                                        f"{API_URL}/portfolio/",
                                        json={"symbol": buy_sym.strip().upper(), "quantity": buy_qty, "purchase_price": buy_px},
                                        headers=headers
                                    )
                                    if b_res.status_code == 200:
                                        st.success(b_res.json().get("message", "Shares added!"))
                                        st.rerun()
                                    else:
                                        st.error(b_res.json().get("detail", "Failed to add shares."))
                                        
                        with tab_sell:
                            owned_symbols = df_p['symbol'].tolist()
                            c_s1, c_s2, c_s3 = st.columns(3)
                            with c_s1:
                                sell_sym = st.selectbox("Select Holding", owned_symbols, key="sell_sym")
                            
                            max_shares = int(df_p.loc[df_p['symbol'] == sell_sym, 'quantity'].values[0]) if sell_sym in owned_symbols else 1
                            with c_s2:
                                sell_qty = st.number_input("Shares to Sell", min_value=1, max_value=max_shares, value=min(5, max_shares), key="sell_qty")
                            with c_s3:
                                live_px = float(df_p.loc[df_p['symbol'] == sell_sym, 'current_price'].values[0]) if sell_sym in owned_symbols else 100.0
                                sell_px = st.number_input("Selling Price ($)", min_value=0.01, value=live_px, key="sell_px")
                                
                            if st.button("Execute Sell Order", type="primary"):
                                s_res = requests.post(
                                    f"{API_URL}/portfolio/sell",
                                    json={"symbol": sell_sym, "quantity": sell_qty, "sell_price": sell_px},
                                    headers=headers
                                )
                                if s_res.status_code == 200:
                                    res_data = s_res.json()
                                    st.success(f"🎉 {res_data.get('message')}")
                                    st.rerun()
                                else:
                                    st.error(s_res.json().get("detail", "Sell order failed."))
                                    
                        with tab_del:
                            del_target = st.selectbox("Position to Remove", df_p['symbol'].tolist(), key="del_sym")
                            target_id = int(df_p.loc[df_p['symbol'] == del_target, 'id'].values[0])
                            st.caption("⚠️ Direct deletion permanently clears this holding without booking realized P/L.")
                            if st.button("Confirm Delete Position", type="secondary"):
                                d_res = requests.delete(f"{API_URL}/portfolio/{target_id}", headers=headers)
                                if d_res.status_code == 200:
                                    st.success(f"Removed {del_target} from portfolio.")
                                    st.rerun()
                                else:
                                    st.error("Failed to delete position.")

                    with col_charts:
                        st.markdown("#### Allocation & Diversification")
                        fig_alloc = px.pie(df_p, values="total_value", names="symbol", hole=0.45, title="Holding Distribution")
                        st.plotly_chart(fig_alloc, use_container_width=True)
                        
                        fig_sec = px.pie(df_p, values="total_value", names="sector", title="Sector Exposure")
                        st.plotly_chart(fig_sec, use_container_width=True)
                        
                    # Treemap heatmap
                    st.markdown("#### 🗺️ Portfolio Heatmap (Performance & Weight)")
                    fig_tree = px.treemap(
                        df_p, path=['sector', 'symbol'], values='total_value',
                        color='pl_percent', color_continuous_scale='RdYlGn',
                        title="Holdings Heatmap (Colored by Profit %)"
                    )
                    st.plotly_chart(fig_tree, use_container_width=True)
                else:
                    st.info("💼 Your portfolio is currently empty. Add your first position below!")
                    with st.expander("➕ Add Initial Position", expanded=True):
                        c1, c2, c3 = st.columns(3)
                        with c1: init_sym = st.text_input("Symbol", value="AAPL")
                        with c2: init_qty = st.number_input("Shares", min_value=1, value=10)
                        with c3: init_px = st.number_input("Price Paid ($)", min_value=0.01, value=150.0)
                        if st.button("Add to Portfolio", type="primary"):
                            res = requests.post(f"{API_URL}/portfolio/", json={"symbol": init_sym.strip().upper(), "quantity": init_qty, "purchase_price": init_px}, headers=headers)
                            if res.status_code == 200:
                                st.success("Position added!")
                                st.rerun()
                            else:
                                st.error(res.json().get("detail", "Error adding stock."))
        except Exception as e:
            st.error(f"Failed to load portfolio: {e}")

    # -----------------------------------------------------
    # PAGE: 🔔 Smart Alerts
    # -----------------------------------------------------
    elif page == "🔔 Smart Alerts":
        st.title("Smart Fundamental Alerts")
        st.caption("Active monitoring engine that checks live company metrics against your custom price/valuation thresholds.")
        
        col_create, col_list = st.columns([1, 2])
        
        with col_create:
            st.markdown("#### Create New Alert")
            a_sym = st.text_input("Target Symbol (Optional)", placeholder="e.g. AAPL or leave blank for market-wide")
            a_field = st.selectbox("Financial Metric", ["pe_ratio", "eps", "revenue_growth", "market_cap"], format_func=lambda x: {
                "pe_ratio": "P/E Ratio",
                "eps": "Earnings Per Share (EPS)",
                "revenue_growth": "Revenue Growth (%)",
                "market_cap": "Market Capitalization ($)"
            }.get(x, x))
            a_op = st.selectbox("Condition Operator", ["<", "<=", ">", ">=", "="])
            a_val = st.number_input("Threshold Value", value=30.0)
            
            if st.button("Activate Alert", type="primary", use_container_width=True):
                payload = {
                    "field": a_field,
                    "operator": a_op,
                    "threshold": float(a_val),
                    "symbol": a_sym.strip().upper() if a_sym else None
                }
                res = requests.post(f"{API_URL}/alerts/", json=payload, headers=headers)
                if res.status_code == 201:
                    st.success("Alert active and monitoring!")
                    st.rerun()
                else:
                    st.error(res.json().get("detail", "Failed to create alert."))
                    
        with col_list:
            st.markdown("#### Live Monitoring & Triggered Alerts")
            try:
                eval_res = requests.get(f"{API_URL}/alerts/evaluated", headers=headers, timeout=15.0)
                if eval_res.status_code == 401:
                    check_auth_response(eval_res)
                elif eval_res.status_code == 200:
                    alerts = eval_res.json()
                    if alerts:
                        for al in alerts:
                            st_badge = "🟢 TRIGGERED" if al.get("status") == "TRIGGERED" else "🔵 MONITORING"
                            sym_display = al.get("symbol") or "MARKET_WIDE"
                            
                            with st.container():
                                c_info, c_act = st.columns([4, 1])
                                with c_info:
                                    st.markdown(f"**{st_badge}** | `{sym_display}`: {al.get('field')} {al.get('operator')} {al.get('threshold'):,.2f}")
                                    st.caption(al.get("message", ""))
                                with c_act:
                                    if st.button("🗑️ Delete", key=f"del_alert_{al.get('id')}", use_container_width=True):
                                        del_res = requests.delete(f"{API_URL}/alerts/{al.get('id')}", headers=headers)
                                        if del_res.status_code == 200:
                                            st.rerun()
                                st.divider()
                    else:
                        st.info("No active alerts set. Configure an alert on the left to start monitoring.")
                else:
                    st.error("Failed to load alerts.")
            except Exception as e:
                st.error(f"Error checking alerts: {e}")

    # -----------------------------------------------------
    # PAGE: 👤 My Profile
    # -----------------------------------------------------
    elif page == "👤 My Profile":
        st.title("User Account & Security Settings")
        st.caption("Manage your profile credentials and view your investor account details.")
        
        try:
            p_res = requests.get(f"{API_URL}/auth/me", headers=headers, timeout=10.0)
            if p_res.status_code == 401:
                check_auth_response(p_res)
            elif p_res.status_code == 200:
                p_info = p_res.json()
                
                col_p_info, col_p_edit = st.columns([1, 1])
                
                with col_p_info:
                    st.markdown("#### Account Information")
                    st.markdown(f"**Username:** `{p_info.get('username')}`")
                    st.markdown(f"**Email:** `{p_info.get('email')}`")
                    st.markdown(f"**Full Name:** `{p_info.get('full_name') or 'Not set'}`")
                    st.markdown(f"**Account Status:** `{'Active' if p_info.get('is_active') else 'Suspended'}`")
                    
                    st.divider()
                    st.markdown("#### Activity Statistics")
                    st.markdown(f"💼 **Active Positions:** {p_info.get('portfolio_count', 0)}")
                    st.markdown(f"🔔 **Configured Alerts:** {p_info.get('alerts_count', 0)}")
                    
                with col_p_edit:
                    st.markdown("#### Update Profile")
                    new_fname = st.text_input("Update Full Name", value=p_info.get("full_name") or "")
                    new_mail = st.text_input("Update Email Address", value=p_info.get("email") or "")
                    
                    st.markdown("##### Change Password")
                    cur_pwd = st.text_input("Current Password", type="password")
                    new_pwd = st.text_input("New Password (min 6 chars)", type="password")
                    
                    if st.button("Save Profile Changes", type="primary", use_container_width=True):
                        update_payload = {}
                        if new_fname: update_payload["full_name"] = new_fname.strip()
                        if new_mail: update_payload["email"] = new_mail.strip().lower()
                        if new_pwd:
                            update_payload["current_password"] = cur_pwd
                            update_payload["new_password"] = new_pwd
                            
                        u_res = requests.put(f"{API_URL}/auth/me", json=update_payload, headers=headers)
                        if u_res.status_code == 200:
                            st.success("Profile updated successfully!")
                            st.session_state["user"] = u_res.json().get("user")
                            st.rerun()
                        else:
                            st.error(u_res.json().get("detail", "Failed to update profile."))
            else:
                st.error("Could not fetch user profile.")
        except Exception as e:
            st.error(f"Error loading profile: {e}")
