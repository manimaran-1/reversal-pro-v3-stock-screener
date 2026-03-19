import streamlit as st
import pandas as pd
import scanner
import data_loader  # FIXED: changed from dataloader
import concurrent.futures

st.set_page_config(page_title="Reversal Pro v3 Scanner", layout="wide")

# Hide Streamlit default elements
hide_style = """
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
</style>
"""
st.markdown(hide_style, unsafe_allow_html=True)

# Secure password check using st.secrets
if "password_correct" not in st.session_state:
    st.session_state.password_correct = False

def check_password():
    if st.secrets.get("password"):
        if st.session_state.password_correct:
            return True
        st.markdown("""
            <h1 style='text-align: center; margin-top: 50px;'>🔐 Secure Access</h1>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                password = st.text_input("Password", type="password", key="login_password")
                submit = st.form_submit_button("Login", use_container_width=True)
            if submit:
                # Convert the secret to string to match input reliably
                if password == str(st.secrets.get("password", "")):
                    st.session_state.password_correct = True
                    st.rerun()
                else:
                    st.error("❌ Incorrect password")
        return False
    else:
        st.error("Secrets not configured. Please set password in Streamlit Cloud Advanced Settings.")
        return False

if not check_password():
    st.stop()

# Main app starts here
st.title("🔄 Reversal Detection Pro v3.0 Scanner")
st.markdown("Scan NSE stocks for non-repainting reversal signals based on V3 logic.")

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")

# 1. Universe Selection
indices = data_loader.get_all_indices_dict()
index_options = ["Custom List"] + list(indices.keys())
selected_index = st.sidebar.selectbox("Select Index", index_options, index=0)

# Custom symbols input
custom_symbols = []
if selected_index == "Custom List":
    custom_input = st.sidebar.text_area("Enter symbols (comma separated)", 
                                        placeholder="RELIANCE.NS, ALKEM.NS, INFY.NS")
    if custom_input:
        custom_symbols = [s.strip() for s in custom_input.split(",")]

# 2. Timeframe Selection
timeframes = ["1d", "1wk", "1mo", "1m", "5m", "15m", "30m", "1h"]
selected_timeframe = st.sidebar.selectbox("Select Timeframe", timeframes, index=0)

# Quick search
st.sidebar.markdown("---")
quick_search = st.sidebar.text_input("Quick Search Stock (Overrides Selection)", 
                                     placeholder="e.g. TATASTEEL.NS")
st.sidebar.markdown("---")

# 3. Sensitivity Settings
sensitivity = st.sidebar.select_slider("Sensitivity Preset", 
                                       options=["Very High", "High", "Medium", "Low", "Very Low", "Custom"], 
                                       value="Medium")

custom_settings = None
if sensitivity == "Custom":
    with st.sidebar.expander("Custom Settings"):
        custom_settings = {
            "atr_mult": st.number_input("ATR Multiplier", 0.1, 10.0, 2.0),
            "pct_threshold": st.number_input("Percentage Threshold", 0.001, 1.0, 0.1),
            "fixed_reversal": st.number_input("Fixed Reversal Amount", 0.0, 100.0, 0.05),
            "atr_length": st.number_input("ATR Length", 1, 50, 5),
            "avg_length": st.number_input("Average Length", 1, 50, 5)
        }

# 4. Calculation Method
calc_method = st.sidebar.selectbox("Calculation Method", ["average", "highlow"])

# 5. Date Range Filter
from datetime import datetime, timedelta
default_start = datetime.now() - timedelta(days=30)
default_end = datetime.now()
start_date = st.sidebar.date_input("Start Date", default_start)
end_date = st.sidebar.date_input("End Date", default_end)

# Run Scan Button
if st.button("🚀 Run Scan", type="primary"):
    symbols = []
    if quick_search:
        symbols = [quick_search.strip()]
        st.info(f"Scanning Single Stock: {quick_search}")
    elif selected_index == "Custom List":
        symbols = custom_symbols
        if not symbols:
            st.error("Please enter symbols in Custom List.")
    else:
        with st.spinner(f"Fetching symbols for {selected_index}..."):
            if selected_index == "Nifty 500":
                symbols = data_loader.get_nifty500_symbols()
            elif selected_index == "Nifty 200":
                symbols = data_loader.get_nifty200_symbols()
            elif selected_index == "Nifty 50":
                # FIXED: method corrected
                symbols = data_loader.get_nifty200_symbols()[:50]
            else:
                symbols = data_loader.get_index_constituents(selected_index)
        if not symbols:
            if not quick_search and selected_index != "Custom List":
                st.error("Could not fetch symbols. Try another index.")

    if symbols:
        scan_settings = {
            "sensitivity": sensitivity,
            # FIXED: Handle "highlow" from UI dropdown binding it to scanner expectation
            "calculation_method": calc_method if calc_method == "average" else "high_low",
            "custom_settings": custom_settings if sensitivity == "Custom" else None,
            "start_date": start_date,
            "end_date": end_date
        }

        progress_bar = st.progress(0)
        status_text = st.empty()
        results = []
        total_symbols = len(symbols)
        completed = 0
        status_text.text(f"Starting scan for {total_symbols} symbols...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_symbol = {
                executor.submit(scanner.scan_symbol_reversal, sym, selected_timeframe, scan_settings): sym 
                for sym in symbols
            }
            for future in concurrent.futures.as_completed(future_to_symbol):
                sym = future_to_symbol[future]
                try:
                    res = future.result()
                    if res:
                        results.extend(res)
                except Exception as e:
                    # Ignoring exception output intentionally so UI doesn't clutter
                    pass
                completed += 1
                progress = completed / total_symbols
                progress_bar.progress(progress)
                status_text.text(f"Scanning {completed}/{total_symbols} symbols...")

        progress_bar.empty()
        status_text.empty()

        results_df = pd.DataFrame(results)
        if not results_df.empty:
            st.success(f"✅ Found {len(results_df)} signals!")
            st.dataframe(
                results_df,
                column_config={
                    "Stock": st.column_config.Column("Stock"),
                    "Reversal Time": st.column_config.DatetimeColumn("Reversal Time", format="D MMM YYYY, HH:mm Z"),
                    "LTP": st.column_config.NumberColumn("LTP", format="₹ %.2f"),
                    "Signal Type": st.column_config.Column("Signal Type"),
                    "Signal Price": st.column_config.NumberColumn("Signal Price", format="₹ %.2f"),
                    "Trend": st.column_config.Column("Trend"),
                    "EMA9": st.column_config.NumberColumn("EMA 9", format="%.2f"),
                    "EMA21": st.column_config.NumberColumn("EMA 21", format="%.2f"),
                    # FIXED: number column string formatting
                    "Volume": st.column_config.NumberColumn("Volume", format="%d")
                },
                hide_index=True,
                use_container_width=True
            )

            csv = results_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name="reversal_scan_results.csv",
                mime="text/csv",
                key="download-csv"
            )
        else:
            st.warning("⚠️ No signals found matching criteria.")
