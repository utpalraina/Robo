#!/usr/bin/env python3
"""
Populate NY session high/low and breakout times in sbc_dr_combined table.
- session_high_full: High of full NY session (9:30 AM - 4:00 PM)
- session_low_full: Low of full NY session (9:30 AM - 4:00 PM)
- time_close_above_1hr_high: Time when first 5m candle closed above 1Hr High (after 10:30 AM)
- time_close_below_1hr_low: Time when first 5m candle closed below 1Hr Low (after 10:30 AM)
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

def get_session_data(date_str, first_hour_high, first_hour_low):
    """Get full NY session data and breakout times."""
    # Parse date and set times
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')

    # Full session: 9:30 AM - 4:00 PM NY
    session_start = NY_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 9, 30))
    session_end = NY_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 16, 0))

    # After first hour: 10:30 AM - 4:00 PM NY
    after_first_hour = NY_TZ.localize(datetime(date_obj.year, date_obj.month, date_obj.day, 10, 30))

    # Convert to UTC for Binance API
    utc_start = session_start.astimezone(UTC_TZ)
    utc_end = session_end.astimezone(UTC_TZ)

    # Fetch 5-minute candles for full session
    klines = get_binance_klines('BTCUSDT', '5m', utc_start, utc_end)

    if not klines or len(klines) == 0:
        return None

    # Calculate full session high and low
    session_high = max(float(k[2]) for k in klines)  # Highest high
    session_low = min(float(k[3]) for k in klines)   # Lowest low

    # Find first close above 1Hr High (after 10:30 AM)
    time_close_above = None
    time_close_below = None

    if first_hour_high and first_hour_low:
        for k in klines:
            candle_time_utc = datetime.fromtimestamp(k[0] / 1000, tz=UTC_TZ)
            candle_time_ny = candle_time_utc.astimezone(NY_TZ)
            candle_close = float(k[4])

            # Only check candles after 10:30 AM
            if candle_time_ny >= after_first_hour:
                # Check for close above 1Hr High
                if time_close_above is None and candle_close > first_hour_high:
                    time_close_above = candle_time_ny.strftime('%H:%M')

                # Check for close below 1Hr Low
                if time_close_below is None and candle_close < first_hour_low:
                    time_close_below = candle_time_ny.strftime('%H:%M')

                # If both found, no need to continue
                if time_close_above and time_close_below:
                    break

    return {
        'session_high_full': session_high,
        'session_low_full': session_low,
        'time_close_above_1hr_high': time_close_above,
        'time_close_below_1hr_low': time_close_below
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

    # Get all dates that need session data (from Sept 2017 onwards, with first hour data)
    cur.execute("""
        SELECT date, first_hour_high, first_hour_low FROM sbc_dr_combined
        WHERE date >= '2017-09-01'
        AND first_hour_high IS NOT NULL
        AND session_high_full IS NULL
        ORDER BY date
    """)
    rows = cur.fetchall()

    print(f"Found {len(rows)} dates to process")

    processed = 0
    errors = 0

    for row in rows:
        date = row[0]
        first_hour_high = row[1]
        first_hour_low = row[2]
        date_str = date.strftime('%Y-%m-%d')

        if processed % 50 == 0 and processed > 0:
            print(f"Processed {processed}/{len(rows)}...")
            conn.commit()
            time.sleep(1)  # Rate limit

        data = get_session_data(date_str, first_hour_high, first_hour_low)

        if data:
            cur.execute("""
                UPDATE sbc_dr_combined
                SET session_high_full = %s,
                    session_low_full = %s,
                    time_close_above_1hr_high = %s,
                    time_close_below_1hr_low = %s
                WHERE date = %s
            """, (
                data['session_high_full'],
                data['session_low_full'],
                data['time_close_above_1hr_high'],
                data['time_close_below_1hr_low'],
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
