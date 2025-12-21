#!/usr/bin/env python3
"""
Recalculate DR signals based on breakout times.

DR Signal Logic:
- BULLISH: First 5m candle closed above 1Hr High (after 10:30 AM) AND no close below 1Hr Low
- BEARISH: First 5m candle closed below 1Hr Low (after 10:30 AM) AND no close above 1Hr High
- If both break, whichever happened FIRST determines the signal
- NEUTRAL: No breakout in either direction

This replaces the old DR signal calculation which was based on end-of-day close.
"""

import psycopg2

def recalculate_dr_signals():
    """Recalculate DR signals based on breakout times."""
    conn = psycopg2.connect(
        host='localhost',
        database='robo_trader',
        user='utpalraina',
        password=''
    )
    cur = conn.cursor()

    # Step 1: Update DR signal based on breakout times
    print("Step 1: Updating DR signals based on breakout times...")
    cur.execute("""
        UPDATE sbc_dr_combined
        SET dr_signal = CASE
            -- Only break high happened -> BULLISH
            WHEN time_close_above_1hr_high IS NOT NULL AND time_close_below_1hr_low IS NULL THEN 'BULLISH'
            -- Only break low happened -> BEARISH
            WHEN time_close_below_1hr_low IS NOT NULL AND time_close_above_1hr_high IS NULL THEN 'BEARISH'
            -- Both happened -> whichever was first wins
            WHEN time_close_above_1hr_high IS NOT NULL AND time_close_below_1hr_low IS NOT NULL THEN
                CASE WHEN time_close_above_1hr_high < time_close_below_1hr_low THEN 'BULLISH' ELSE 'BEARISH' END
            -- No breakout -> NEUTRAL
            ELSE 'NEUTRAL'
        END
        WHERE date >= '2017-09-01' AND session_high_full IS NOT NULL
    """)
    dr_updated = cur.rowcount
    print(f"  Updated {dr_updated} DR signals")

    # Step 2: Update signals_agree based on new DR signals
    print("Step 2: Updating signals_agree...")
    cur.execute("""
        UPDATE sbc_dr_combined
        SET signals_agree = CASE
            -- DR is NEUTRAL -> no agreement possible
            WHEN dr_signal = 'NEUTRAL' THEN NULL
            -- SBC bullish + DR bullish -> agree
            WHEN v6_signal IN ('STRONGLY_BULLISH', 'MODERATELY_BULLISH', 'SLIGHTLY_BULLISH') AND dr_signal = 'BULLISH' THEN TRUE
            -- SBC bearish + DR bearish -> agree
            WHEN v6_signal IN ('STRONGLY_BEARISH', 'MODERATELY_BEARISH', 'SLIGHTLY_BEARISH') AND dr_signal = 'BEARISH' THEN TRUE
            -- SBC is NEUTRAL -> no agreement
            WHEN v6_signal = 'NEUTRAL' THEN NULL
            -- Otherwise they conflict
            ELSE FALSE
        END
        WHERE date >= '2017-09-01' AND session_high_full IS NOT NULL
    """)
    agree_updated = cur.rowcount
    print(f"  Updated {agree_updated} signals_agree values")

    # Step 3: Update combined_signal
    print("Step 3: Updating combined_signal...")
    cur.execute("""
        UPDATE sbc_dr_combined
        SET combined_signal = CASE
            WHEN dr_signal = 'NEUTRAL' THEN 'NO_DR_SIGNAL'
            WHEN v6_signal IN ('STRONGLY_BULLISH', 'MODERATELY_BULLISH', 'SLIGHTLY_BULLISH') AND dr_signal = 'BULLISH' THEN 'BULLISH'
            WHEN v6_signal IN ('STRONGLY_BEARISH', 'MODERATELY_BEARISH', 'SLIGHTLY_BEARISH') AND dr_signal = 'BEARISH' THEN 'BEARISH'
            WHEN v6_signal = 'NEUTRAL' THEN 'SBC_NEUTRAL'
            ELSE 'CONFLICT'
        END
        WHERE date >= '2017-09-01' AND session_high_full IS NOT NULL
    """)
    combined_updated = cur.rowcount
    print(f"  Updated {combined_updated} combined_signal values")

    # Step 4: Update combined_correct
    print("Step 4: Updating combined_correct...")
    cur.execute("""
        UPDATE sbc_dr_combined
        SET combined_correct = CASE
            WHEN combined_signal = 'BULLISH' AND actual_direction = 'BULLISH' THEN TRUE
            WHEN combined_signal = 'BEARISH' AND actual_direction = 'BEARISH' THEN TRUE
            WHEN combined_signal IN ('BULLISH', 'BEARISH') THEN FALSE
            ELSE NULL
        END
        WHERE date >= '2017-09-01' AND session_high_full IS NOT NULL
    """)
    correct_updated = cur.rowcount
    print(f"  Updated {correct_updated} combined_correct values")

    conn.commit()

    # Print summary stats
    print("\n=== ACCURACY STATS ===")

    cur.execute("""
        SELECT
            COUNT(*) as trades,
            ROUND(100.0 * SUM(CASE WHEN combined_correct THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy
        FROM sbc_dr_combined
        WHERE signals_agree = TRUE AND combined_correct IS NOT NULL AND date >= '2017-09-01'
    """)
    row = cur.fetchone()
    print(f"Combined (SBC+DR agree): {row[0]} trades, {row[1]}% accuracy")

    cur.execute("""
        SELECT
            COUNT(*) as trades,
            ROUND(100.0 * SUM(CASE WHEN
                (dr_signal = 'BULLISH' AND actual_direction = 'BULLISH') OR
                (dr_signal = 'BEARISH' AND actual_direction = 'BEARISH')
            THEN 1 ELSE 0 END) / COUNT(*), 1) as accuracy
        FROM sbc_dr_combined
        WHERE dr_signal IN ('BULLISH', 'BEARISH') AND actual_direction IS NOT NULL AND date >= '2017-09-01'
    """)
    row = cur.fetchone()
    print(f"DR Alone: {row[0]} trades, {row[1]}% accuracy")

    cur.close()
    conn.close()
    print("\nDone!")

if __name__ == '__main__':
    recalculate_dr_signals()
