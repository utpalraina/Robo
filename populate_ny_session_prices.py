#!/usr/bin/env python3
"""
Populate NY session first hour prices (9:30-10:30 AM NY) in sbc_dr_combined table.
Fetches 5-minute candle data from Binance for each date.
"""

import psycopg2
import requests
from datetime import datetime, timedelta
import pytz
import time

NY_TZ = pytz.timezone('America/New_York')
UTC_TZ = pytz.UTC

def get_binance_klines(symbol, interval, start_time, end_time):
    """Fetch klines from Binance API."""
    url = 'https://api.binance.com/api/v3/klines'
    params = {
        'symbol': symbol,
        'interval': interval,
        'startTime': int(start_time.timestamp() * 1000),
        'endTime': int(end_time.timestamp() * 1000),
        'limit': 1000
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"Error fetching klines: {e}")
    return None

def get_first_hour_data(date_str):
    """Get NY session first hour OHLC data (9:30-10:30 AM NY)."""
    # Parse date and set to 9:30 AM NY
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    ny_open_time = NY_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 9, 30))
    ny_close_time = NY_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 10, 30))

    # Convert to UTC for Binance API
    utc_start = ny_open_time.astimezone(UTC_TZ)
    utc_end = ny_close_time.astimezone(UTC_TZ)

    # Fetch 5-minute candles for the first hour
    klines = get_binance_klines('BTCUSDT', '5m', utc_start, utc_end)

    if not klines or len(klines) == 0:
        return None

    # Calculate OHLC for the first hour
    ny_open = float(klines[0][1])  # Open of first candle
    ny_close_1030 = float(klines[-1][4])  # Close of last candle
    first_hour_high = max(float(k[2]) for k in klines)  # Highest high
    first_hour_low = min(float(k[3]) for k in klines)  # Lowest low

    return {
        'ny_open': ny_open,
        'first_hour_high': first_hour_high,
        'first_hour_low': first_hour_low,
        'ny_close_1030': ny_close_1030
    }

def main():
    # Connect to database
    conn = psycopg2.connect(
        host='localhost',
        database='robo_trader',
        user='utpalraina',
        password=''
    )
    cur = conn.cursor()

    # Get all dates that need NY session data (from Sept 2017 onwards - Binance data available)
    cur.execute("""
        SELECT date FROM sbc_dr_combined
        WHERE date >= '2017-09-01'
        AND ny_open IS NULL
        ORDER BY date
    """)
    dates = [row[0] for row in cur.fetchall()]

    print(f"Found {len(dates)} dates to process")

    processed = 0
    errors = 0

    for date in dates:
        date_str = date.strftime('%Y-%m-%d')

        if processed % 50 == 0 and processed > 0:
            print(f"Processed {processed}/{len(dates)}...")
            conn.commit()
            time.sleep(1)  # Rate limit

        data = get_first_hour_data(date_str)

        if data:
            cur.execute("""
                UPDATE sbc_dr_combined
                SET ny_open = %s,
                    first_hour_high = %s,
                    first_hour_low = %s,
                    ny_close_1030 = %s
                WHERE date = %s
            """, (
                data['ny_open'],
                data['first_hour_high'],
                data['first_hour_low'],
                data['ny_close_1030'],
                date
            ))
            processed += 1
        else:
            errors += 1
            print(f"No data for {date_str}")

        time.sleep(0.1)  # Rate limit

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nDone! Processed: {processed}, Errors: {errors}")

if __name__ == '__main__':
    main()
