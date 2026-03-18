import yfinance as yf
import pandas as pd
import requests
import io
import pytz
from datetime import datetime, timedelta

# Define IST timezone
IST = pytz.timezone('Asia/Kolkata')

def get_nifty500_symbols():
    """
    Fetches the list of Nifty 500 symbols.
    """
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            return [f"{sym}.NS" for sym in df['Symbol'].tolist()]
    except Exception as e:
        print(f"Error fetching Nifty 500 list: {e}")
    
    # Fallback
    return [
        "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
        "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS", "LT.NS"
    ]

def get_nifty200_symbols():
    """
    Fetches Nifty 200 symbols.
    """
    try:
        url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
            return [f"{sym}.NS" for sym in df['Symbol'].tolist()]
    except Exception as e:
        print(f"Error fetching Nifty 200 list: {e}")
    return get_nifty500_symbols()[:50]


# Validated Index Slugs (Verified via verify_indices.py)
INDICES_SLUGS = {
    # Custom
    "Total Market": "total_market_custom",
    
    # Broad Based
    "Nifty 50": "nifty50",
    "Nifty Next 50": "niftynext50",
    "Nifty 100": "nifty100",
    "Nifty 200": "nifty200",
    "Nifty 500": "nifty500",
    "Nifty Midcap 50": "niftymidcap50",
    "Nifty Midcap 100": "niftymidcap100",
    "Nifty Midcap 150": "niftymidcap150",
    "Nifty Smallcap 50": "niftysmallcap50",
    "Nifty Smallcap 100": "niftysmallcap100",
    "Nifty Smallcap 250": "niftysmallcap250",
    "Nifty LargeMidcap 250": "niftylargemidcap250",
    "Nifty MidSmallcap 400": "niftymidsmallcap400",
    
    # Sectoral
    "Nifty Auto": "niftyauto",
    "Nifty Bank": "niftybank",
    "Nifty Consumer Durables": "niftyconsumerdurables",
    "Nifty Financial Services": "niftyfinancelist",
    "Nifty FMCG": "niftyfmcg",
    "Nifty Healthcare": "niftyhealthcare",
    "Nifty IT": "niftyit",
    "Nifty Media": "niftymedia",
    "Nifty Metal": "niftymetal",
    "Nifty Pharma": "niftypharma",
    "Nifty Private Bank": "nifty_privatebank",
    "Nifty PSU Bank": "niftypsubank",
    "Nifty Realty": "niftyrealty",
    
    # Thematic
    "Nifty Commodities": "niftycommodities",
    "Nifty CPSE": "niftycpse",
    "Nifty Energy": "niftyenergy",
    "Nifty Infrastructure": "niftyinfra",
    "Nifty MNC": "niftymnc",
    "Nifty PSE": "niftypse",
    "Nifty Services Sector": "niftyservicesector"
}

def get_index_constituents(index_name):
    """
    Returns symbols for a specific index using the validated CSV slug.
    """
    if index_name in INDICES_SLUGS:
        slug = INDICES_SLUGS[index_name]
        
        # Special handling for Custom Total Market
        if slug == "total_market_custom":
            try:
                # Read from local file
                import os
                
                # Assume file is in the same directory as this script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(current_dir, "total_market.txt")
                
                if os.path.exists(file_path):
                    with open(file_path, "r") as f:
                        content = f.read().strip()
                        # Allow comma or newline separated
                        if "," in content:
                            symbols = [s.strip() for s in content.split(",") if s.strip()]
                        else:
                            symbols = [s.strip() for s in content.split("\n") if s.strip()]
                        return symbols
                else:
                    print(f"Error: {file_path} not found.")
                    return []
            except Exception as e:
                print(f"Error reading total_market.txt: {e}")
                return []
        
        try:
            url = f"https://archives.nseindia.com/content/indices/ind_{slug}list.csv"
            # Special case for Financial Services which uses full name in slug sometimes, but here we mapped it.
            
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.content.decode('utf-8')))
                return [f"{sym}.NS" for sym in df['Symbol'].tolist()]
        except Exception as e:
            print(f"Error fetching {index_name}: {e}")
            pass
            
    # Fallback: Return empty
    return []

def fetch_nifty500_stats(progress_callback=None):
    """
    Fetches raw statistics (Change, Volume, Value, 52W High/Low) for Nifty 500 symbols
    using the incredibly fast TradingView Scanner API.
    """
    try:
        symbols = get_nifty500_symbols()
        
        # Strip .NS to use with TV
        base_symbols = [s.replace(".NS", "") for s in symbols]
        tickers = [f"NSE:{sym}" for sym in base_symbols]
        
        url = "https://scanner.tradingview.com/india/scan"
        
        # Max payload size is usually large enough, we can split into 2 chunks of 250
        chunk_size = 250 
        ticker_chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
        
        stats = []
        
        print(f"Fetching full stats for {len(symbols)} symbols via TradingView...")
        
        for i, chunk in enumerate(ticker_chunks):
            if progress_callback:
                progress_callback(i + 1, len(ticker_chunks))
                
            payload = {
                "symbols": {"tickers": chunk},
                "columns": ["name", "close", "volume", "change", "price_52_week_high", "price_52_week_low"]
            }
            try:
                r = requests.post(url, json=payload, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                if r.status_code == 200:
                    data = r.json().get('data', [])
                    for item in data:
                        # name is item['d'][0]
                        sym_name = f"{item['d'][0]}.NS"
                        close = item['d'][1]
                        volume = item['d'][2]
                        change_pct = item['d'][3]
                        high_52 = item['d'][4]
                        low_52 = item['d'][5]
                        
                        value = close * volume if close and volume else 0
                        
                        dist_high = ((high_52 - close) / high_52) * 100 if high_52 and high_52 > 0 else 999.0
                        dist_low = ((close - low_52) / low_52) * 100 if low_52 and low_52 > 0 else 999.0
                        
                        stats.append({
                            'Symbol': sym_name,
                            'Change': change_pct if change_pct is not None else 0.0,
                            'Volume': volume if volume is not None else 0,
                            'Value': value,
                            'Close': close if close is not None else 0.0,
                            'High52': high_52 if high_52 is not None else 0.0,
                            'Low52': low_52 if low_52 is not None else 0.0,
                            'DistHigh': dist_high,
                            'DistLow': dist_low
                        })
            except Exception as e:
                print(f"Error fetching TV chunk {i}: {e}")
                pass
                
        return pd.DataFrame(stats)
        
    except Exception as e:
        print(f"Error fetching market movers: {e}")
        return pd.DataFrame()

def get_market_movers(category="Top Gainers", df_stats=None):
    """
    Returns top movers based on category from the provided (or fetched) DataFrame.
    """
    if df_stats is None or df_stats.empty:
        return []
        
    try:
        if category == "Top Gainers":
            top = df_stats.sort_values('Change', ascending=False).head(50)
            return top['Symbol'].tolist()
        elif category == "Top Losers":
            top = df_stats.sort_values('Change', ascending=True).head(50)
            return top['Symbol'].tolist()
        elif category == "Most Active (Value)":
            top = df_stats.sort_values('Value', ascending=False).head(50)
            return top['Symbol'].tolist()
        elif category == "Most Active (Volume)":
            top = df_stats.sort_values('Volume', ascending=False).head(50)
            return top['Symbol'].tolist()
        elif category == "52 Week High":
            top = df_stats.sort_values('DistHigh', ascending=True).head(50)
            return top['Symbol'].tolist()
        elif category == "52 Week Low":
            top = df_stats.sort_values('DistLow', ascending=True).head(50)
            return top['Symbol'].tolist()
            
    except Exception as e:
        print(f"Error sorting stats: {e}")
        return []

def get_all_indices_dict():
    """
    Returns a dictionary of Index Name -> Index Name (or Identifier).
    """
    # Return keys from our verified slugs dict
    # Maintain logical order? Regular dicts are insertion ordered in Python 3.7+
    # But for UI display, we might want to group them if possible, or just list them.
    # The keys in INDICES_SLUGS are already somewhat grouped by insertion above.
    return {k: k for k in INDICES_SLUGS.keys()}

def fetch_data(symbol, period='1y', interval='1d'):
    """
    Fetches historical data for a symbol.
    Converst index to Asia/Kolkata timezone.
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Adjust period based on interval to ensure enough data for indicators (e.g. EMA 200)
        # We need at least ~200 candles.
        if interval == '1m':
            period = '5d' # max allowed for 1m is 7d
        elif interval in ['2m', '5m', '15m', '30m', '60m', '90m', '1h']:
            period = '1mo' # Safe for intraday
        elif interval in ['1d', '5d', '1wk']:
            period = '1y' 
        elif interval == '1mo':
            period = '5y' # Need long history for monthly 200 EMA
            
        df = ticker.history(period=period, interval=interval)
        if not df.empty:
            # yfinance columns are Capitalized: Open, High, Low, Close, Volume
            # Standardize to lowercase for consistency
            df.columns = [c.lower() for c in df.columns]
            
            # Convert index to IST
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC').tz_convert(IST)
            else:
                df.index = df.index.tz_convert(IST)
                
            # Align NSE Intraday timestamps (especially 30m) which yfinance rounds to :00/:30 instead of :15/:45
            if symbol.endswith('.NS') and interval in ['1m', '2m', '5m', '15m', '30m']:
                df.index = df.index + pd.Timedelta(minutes=15)
                
            return df
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
    return pd.DataFrame()

def fetch_bulk_data(symbols, period='1y', interval='1d', progress_callback=None):
    """
    Fetches historical data for multiple symbols concurrently using yfinance.download.
    Returns a dictionary of symbol -> DataFrame.
    Handles both old yfinance (flat columns for single symbol) and new yfinance (MultiIndex always).
    """
    try:
        # Determine period
        if interval == '1m':
            period = '5d'
        elif interval in ['2m', '5m', '15m', '30m', '60m', '90m', '1h']:
            period = '1mo'
        elif interval in ['1d', '5d', '1wk']:
            period = '1y' 
        elif interval == '1mo':
            period = '5y'
            
        print(f"Bulk downloading {len(symbols)} symbols. Period={period}, Interval={interval}...")
        
        bulk_data = yf.download(symbols, period=period, interval=interval, group_by='ticker', threads=True, progress=False)
        
        results = {}
        if bulk_data.empty:
             return results

        def _process_df(df, sym):
            """Standardize columns and timezone for a single-symbol DataFrame."""
            df = df.dropna(how='all')
            if df.empty:
                return None
            # Standardize columns to lowercase strings
            if isinstance(df.columns, pd.MultiIndex):
                # Drop the ticker level — keep just price type
                df.columns = [str(c[0]).lower() if isinstance(c, tuple) else str(c).lower() for c in df.columns]
            else:
                df.columns = [str(c).lower() for c in df.columns]
            # Apply Timezone
            if df.index.tz is None:
                df.index = df.index.tz_localize('UTC').tz_convert(IST)
            else:
                df.index = df.index.tz_convert(IST)
                
            # Align NSE intraday timestamps (e.g. 30m) which yfinance rounds to :00/:30 instead of :15/:45
            if sym.endswith('.NS') and interval in ['1m', '2m', '5m', '15m', '30m']:
                df.index = df.index + pd.Timedelta(minutes=15)
                
            return df

        # Check if MultiIndex columns
        if isinstance(bulk_data.columns, pd.MultiIndex):
            # Get unique tickers from the column index
            # In newer yfinance: level 0 = Price type, level 1 = Ticker (with group_by='ticker' it swaps)
            # With group_by='ticker': level 0 = Ticker, level 1 = Price type
            # Without group_by or single symbol: level 0 = Price type, level 1 = Ticker
            level0_vals = bulk_data.columns.get_level_values(0).unique().tolist()
            level1_vals = bulk_data.columns.get_level_values(1).unique().tolist()
            
            # Determine which level has tickers vs price types
            price_names = {'open', 'high', 'low', 'close', 'volume', 'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close', 'adj close'}
            
            if set(str(v) for v in level0_vals) & price_names:
                # Level 0 = Price type, Level 1 = Ticker
                for sym in symbols:
                    try:
                        # Select columns where level 1 matches the symbol
                        if sym in level1_vals:
                            df = bulk_data.xs(sym, level=1, axis=1).copy()
                            df = _process_df(df, sym)
                            if df is not None:
                                results[sym] = df
                    except Exception:
                        pass
            else:
                # Level 0 = Ticker, Level 1 = Price type (group_by='ticker')
                for sym in symbols:
                    try:
                        if sym in level0_vals:
                            df = bulk_data[sym].copy()
                            df = _process_df(df, sym)
                            if df is not None:
                                results[sym] = df
                    except Exception:
                        pass
        else:
            # Flat columns (old yfinance, single symbol)
            sym = symbols[0]
            df = bulk_data.copy()
            df = _process_df(df, sym)
            if df is not None:
                results[sym] = df
                
        return results
    except Exception as e:
        print(f"Error in fetch_bulk_data: {e}")
        return {}

