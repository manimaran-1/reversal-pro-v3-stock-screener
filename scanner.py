import pandas as pd
import indicators
import data_loader
import concurrent.futures
import pytz
from datetime import datetime

IST = pytz.timezone('Asia/Kolkata')

def scan_symbol_reversal(symbol, interval, settings):
    """
    Scans a single symbol fetching its own data.
    """
    df = data_loader.fetch_data(symbol, interval=interval)
    return scan_symbol_reversal_prefetched(symbol, df, interval, settings)

def scan_symbol_reversal_prefetched(symbol, df, interval, settings):
    """
    Scans a single symbol for Reversal V3 signals using a pre-fetched DataFrame.
    """
    try:
        if df is None or df.empty or len(df) < 50:
            return None
            
        # Calculate Reversal Logic
        sensitivity = settings.get("sensitivity", "Medium")
        calc_method = settings.get("calculation_method", "average")
        
        # Calculate Reversal
        res_df = indicators.calculate_reversal_v3(
            df, 
            sensitivity=sensitivity, 
            calculation_method=calc_method,
            is_custom=(sensitivity == "Custom"),
            custom_settings=settings.get("custom_settings")
        )
        
        if res_df.empty:
            return None
            
        signals = res_df[res_df['Signal'] != 0].copy()
        
        if signals.empty:
            return None
            
        # Date Range Filtering
        start_date = settings.get("start_date")
        end_date = settings.get("end_date")
        
        if start_date and end_date:
            try:
                tz = pytz.timezone('Asia/Kolkata')
                s_dt = tz.localize(datetime.combine(start_date, datetime.min.time()))
                e_dt = tz.localize(datetime.combine(end_date, datetime.max.time()))
                signals = signals[(signals.index >= s_dt) & (signals.index <= e_dt)]
            except Exception as e:
                pass
        
        if signals.empty:
            return []
            
        current_bar = res_df.iloc[-1]
        current_ltp = current_bar['close']
        
        symbol_results = []
        
        # Iterate over all signals in the filtered date range
        for idx, signal_row in signals.iterrows():
            signal_price = round(signal_row['Signal_Price'], 2)
            signal_type_str = "Bullish" if signal_row['Signal'] == 1 else "Bearish"
            
            pivot_time = signal_row.get('Pivot_Time')
            
            # Extract indicators precisely at the time of the chart pivot (not the confirmation signal)
            if pd.notna(pivot_time) and pivot_time in res_df.index:
                source_row = res_df.loc[pivot_time]
            else:
                source_row = signal_row
                
            atr_val = source_row.get('ATR', 0)
            bb_lower = source_row.get('BBL', 0)
            bb_upper = source_row.get('BBU', 0)
            pivot_high = source_row.get('high', signal_price)
            pivot_low = source_row.get('low', signal_price)
            signal_trend = source_row.get('Trend', current_bar.get('Trend', 'N/A'))
            signal_ema9 = source_row.get('EMA9', current_bar.get('EMA9', 0))
            signal_ema21 = source_row.get('EMA21', current_bar.get('EMA21', 0))
            signal_volume = source_row.get('volume', current_bar.get('volume', 0))
            
            # Calculate Dynamic Stop Loss & Take Profit based on ATR and BB
            if signal_type_str == "Bullish":
                # Pure ATR
                atr_sl = signal_price - atr_val
                atr_tp = signal_price + (atr_val * 2)
                # BB + ATR
                bb_atr_sl = bb_lower - atr_val if bb_lower > 0 else atr_sl
                bb_atr_tp = bb_upper + atr_val if bb_upper > 0 else atr_tp
                # Pivot / Structural
                pivot_sl = pivot_low
                # Make sure TP is valid even if price equals pivot
                pivot_tp = signal_price + max(signal_price - pivot_sl, 0.01) * 2
                # EMA
                ema_sl_str = f"₹{round(signal_ema21, 2)}" if signal_ema21 < signal_price else f"₹{round(signal_ema21, 2)} ⏳"
            else:
                # Pure ATR
                atr_sl = signal_price + atr_val
                atr_tp = signal_price - (atr_val * 2)
                # BB + ATR
                bb_atr_sl = bb_upper + atr_val if bb_upper > 0 else atr_sl
                bb_atr_tp = bb_lower - atr_val if bb_lower > 0 else atr_tp
                # Pivot / Structural
                pivot_sl = pivot_high
                pivot_tp = signal_price - max(pivot_sl - signal_price, 0.01) * 2
                # EMA
                ema_sl_str = f"₹{round(signal_ema21, 2)}" if signal_ema21 > signal_price else f"₹{round(signal_ema21, 2)} ⏳"

            # Reversal Time: where the REVERSAL label appears on TradingView chart (pivot candle)
            pivot_time_val = signal_row['Pivot_Time']
            reversal_time = pivot_time_val if pd.notna(pivot_time_val) else idx

            symbol_results.append({
                "Stock": symbol,
                "LTP": round(current_ltp, 2),
                "Reversal Time": reversal_time,
                "Type": signal_type_str,
                "Signal Price": signal_price,
                "Pivot (Best SL/TP)": f"₹{round(pivot_sl, 2)} / ₹{round(pivot_tp, 2)}",
                "EMA SL": ema_sl_str,
                "ATR (SL/TP)": f"₹{round(atr_sl, 2)} / ₹{round(atr_tp, 2)}",
                "BB+ATR (SL/TP)": f"₹{round(bb_atr_sl, 2)} / ₹{round(bb_atr_tp, 2)}",
                "ATR": round(atr_val, 2),
                "BB Lower": round(bb_lower, 2),
                "BB Upper": round(bb_upper, 2),
                "Trend": signal_trend,
                "EMA9": round(signal_ema9, 2),
                "EMA21": round(signal_ema21, 2),
                "Volume": int(signal_volume)
            })
            
        return symbol_results

    except Exception as e:
        return None

def scan_market(symbols, interval='1d', settings=None, progress_callback=None):
    """
    Parallel bulk scan of market symbols using pre-fetched block data.
    """
    results = []
    if settings is None:
        settings = {}
        
    # Pre-fetch all data simultaneously (Chunked)
    bulk_data_dict = data_loader.fetch_bulk_data(symbols, interval=interval, progress_callback=progress_callback)
        
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(scan_symbol_reversal_prefetched, sym, bulk_data_dict.get(sym), interval, settings): sym 
            for sym in symbols
        }
        
        for future in concurrent.futures.as_completed(futures):
            res_list = future.result()
            if res_list:
                results.extend(res_list)
                
    return pd.DataFrame(results)
