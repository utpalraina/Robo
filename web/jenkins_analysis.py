"""
Jenkins Trading Methods Analysis Module

Based on Michael S. Jenkins' methodologies from:
- Basic Day Trading Techniques
- Square the Range Trading System
- Day Trading for 50 Years
- Private Seminar

Core Concepts:
1. Time & Price are interchangeable vectors
2. Square roots define support/resistance
3. Time Conversion Bars (TCB) predict corrections
4. Geometric angles and circles for turns
5. Each asset has a birth date/price that seeds all cycles
"""

import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import numpy as np

# Planetary calculations using ephem
try:
    import ephem
    EPHEM_AVAILABLE = True
except ImportError:
    EPHEM_AVAILABLE = False


# =============================================================================
# ASSET PROFILES - Birth data for specific assets (Jenkins: "from the date of
# birth of the stock it could be determined for once and for all time what
# time factor would be used")
# =============================================================================

ASSET_PROFILES = {
    # Cryptocurrencies
    'BTC': {
        'name': 'Bitcoin',
        'type': 'crypto',
        'birth_date': '2009-01-03',  # Genesis block
        'birth_price': 0.0,  # No price initially
        'first_trade_date': '2010-07-17',  # First exchange trade
        'first_trade_price': 0.05,  # ~$0.05
        'ath_price': 108364,  # All-time high
        'ath_date': '2024-12-17',
        'atl_price': 0.05,
        'atl_date': '2010-07-17',
        'exchange_longitude': -74.006,  # NYC (major exchange hub)
        'notes': 'Genesis block mined by Satoshi'
    },
    'ETH': {
        'name': 'Ethereum',
        'type': 'crypto',
        'birth_date': '2015-07-30',  # Frontier launch
        'birth_price': 0.31,  # ICO price ~$0.31
        'first_trade_date': '2015-08-07',
        'first_trade_price': 2.77,
        'ath_price': 4878,
        'ath_date': '2021-11-10',
        'atl_price': 0.42,
        'atl_date': '2015-10-21',
        'exchange_longitude': -74.006,
        'notes': 'Vitalik Buterin launch'
    },
    'SOL': {
        'name': 'Solana',
        'type': 'crypto',
        'birth_date': '2020-03-16',  # Mainnet beta
        'birth_price': 0.22,
        'first_trade_date': '2020-04-10',
        'first_trade_price': 0.95,
        'ath_price': 263.83,
        'ath_date': '2024-11-23',
        'atl_price': 0.50,
        'atl_date': '2020-05-11',
        'exchange_longitude': -74.006,
        'notes': 'High-speed blockchain'
    },

    # Stock Indices
    'SPY': {
        'name': 'S&P 500 ETF',
        'type': 'index',
        'birth_date': '1993-01-22',  # SPY inception
        'birth_price': 43.94,
        'first_trade_date': '1993-01-29',
        'first_trade_price': 43.97,
        'ath_price': 609.07,
        'ath_date': '2024-12-06',
        'atl_price': 43.94,
        'atl_date': '1993-01-29',
        'exchange_longitude': -74.006,  # NYSE
        'notes': 'Tracks S&P 500 index'
    },
    'QQQ': {
        'name': 'Nasdaq 100 ETF',
        'type': 'index',
        'birth_date': '1999-03-10',
        'birth_price': 51.13,
        'first_trade_date': '1999-03-10',
        'first_trade_price': 51.13,
        'ath_price': 538.28,
        'ath_date': '2024-12-16',
        'atl_price': 19.76,
        'atl_date': '2002-10-10',
        'exchange_longitude': -74.006,  # NASDAQ
        'notes': 'Tracks Nasdaq 100'
    },
    'DJI': {
        'name': 'Dow Jones Industrial',
        'type': 'index',
        'birth_date': '1896-05-26',  # DJIA inception
        'birth_price': 40.94,
        'first_trade_date': '1896-05-26',
        'first_trade_price': 40.94,
        'ath_price': 45073,
        'ath_date': '2024-12-04',
        'atl_price': 28.48,
        'atl_date': '1896-08-08',
        'exchange_longitude': -74.006,  # NYSE
        'notes': 'Oldest US index'
    },

    # Precious Metals
    'GOLD': {
        'name': 'Gold',
        'type': 'metal',
        'birth_date': '1971-08-15',  # Nixon ends gold standard
        'birth_price': 35.00,  # Fixed price before
        'first_trade_date': '1975-01-01',  # US citizens allowed
        'first_trade_price': 175.00,
        'ath_price': 2790,
        'ath_date': '2024-10-30',
        'atl_price': 35.00,
        'atl_date': '1971-08-15',
        'exchange_longitude': -74.006,  # COMEX NYC
        'notes': 'Free float after Nixon shock'
    },
    'SILVER': {
        'name': 'Silver',
        'type': 'metal',
        'birth_date': '1971-08-15',
        'birth_price': 1.29,
        'first_trade_date': '1975-01-01',
        'first_trade_price': 4.50,
        'ath_price': 49.82,
        'ath_date': '2011-04-28',
        'atl_price': 1.29,
        'atl_date': '1971-08-15',
        'exchange_longitude': -74.006,
        'notes': 'Hunt Brothers squeeze in 1980'
    },

    # Commodities
    'CL': {
        'name': 'Crude Oil (WTI)',
        'type': 'commodity',
        'birth_date': '1983-03-30',  # NYMEX futures start
        'birth_price': 29.00,
        'first_trade_date': '1983-03-30',
        'first_trade_price': 29.00,
        'ath_price': 147.27,
        'ath_date': '2008-07-11',
        'atl_price': -37.63,  # Apr 2020 negative!
        'atl_date': '2020-04-20',
        'exchange_longitude': -74.006,  # NYMEX NYC
        'notes': 'Went negative in Apr 2020'
    },
    'NG': {
        'name': 'Natural Gas',
        'type': 'commodity',
        'birth_date': '1990-04-03',
        'birth_price': 1.64,
        'first_trade_date': '1990-04-03',
        'first_trade_price': 1.64,
        'ath_price': 15.78,
        'ath_date': '2005-12-13',
        'atl_price': 1.02,
        'atl_date': '1992-01-28',
        'exchange_longitude': -74.006,
        'notes': 'Highly volatile commodity'
    },

    # S&P 500 Futures (ES)
    'ES': {
        'name': 'S&P 500 E-mini Futures',
        'type': 'index',
        'birth_date': '1997-09-09',
        'birth_price': 927.00,
        'first_trade_date': '1997-09-09',
        'first_trade_price': 927.00,
        'ath_price': 6100,
        'ath_date': '2024-12-06',
        'atl_price': 666.75,
        'atl_date': '2009-03-06',
        'exchange_longitude': -87.630,  # CME Chicago
        'notes': 'Most liquid futures contract'
    },
    'NQ': {
        'name': 'Nasdaq 100 E-mini Futures',
        'type': 'index',
        'birth_date': '1999-06-21',
        'birth_price': 2100.00,
        'first_trade_date': '1999-06-21',
        'first_trade_price': 2100.00,
        'ath_price': 22000,
        'ath_date': '2024-12-16',
        'atl_price': 795.00,
        'atl_date': '2002-10-10',
        'exchange_longitude': -87.630,  # CME Chicago
        'notes': 'Tech-heavy index futures'
    },

    # Major Stocks (Jenkins recommends 20-30 stocks for life)
    'AAPL': {
        'name': 'Apple Inc',
        'type': 'stock',
        'birth_date': '1980-12-12',  # IPO
        'birth_price': 22.00,  # IPO price
        'first_trade_date': '1980-12-12',
        'first_trade_price': 29.00,  # First trade
        'ath_price': 260.10,
        'ath_date': '2024-12-26',
        'atl_price': 0.10,  # Split adjusted
        'atl_date': '1982-07-01',
        'exchange_longitude': -74.006,  # NASDAQ
        'notes': 'Split adjusted prices'
    },
    'MSFT': {
        'name': 'Microsoft',
        'type': 'stock',
        'birth_date': '1986-03-13',
        'birth_price': 21.00,
        'first_trade_date': '1986-03-13',
        'first_trade_price': 28.00,
        'ath_price': 468.35,
        'ath_date': '2024-07-05',
        'atl_price': 0.07,  # Split adjusted
        'atl_date': '1986-03-13',
        'exchange_longitude': -74.006,
        'notes': 'Split adjusted'
    },
    'NVDA': {
        'name': 'NVIDIA',
        'type': 'stock',
        'birth_date': '1999-01-22',
        'birth_price': 12.00,
        'first_trade_date': '1999-01-22',
        'first_trade_price': 12.00,
        'ath_price': 152.89,
        'ath_date': '2024-11-21',
        'atl_price': 0.03,  # Split adjusted
        'atl_date': '2002-10-08',
        'exchange_longitude': -74.006,
        'notes': 'AI chip leader'
    },
    'TSLA': {
        'name': 'Tesla',
        'type': 'stock',
        'birth_date': '2010-06-29',
        'birth_price': 17.00,
        'first_trade_date': '2010-06-29',
        'first_trade_price': 19.00,
        'ath_price': 488.54,
        'ath_date': '2024-12-18',
        'atl_price': 1.00,  # Split adjusted
        'atl_date': '2010-07-01',
        'exchange_longitude': -74.006,
        'notes': 'EV pioneer'
    }
}

# Exchange longitudes for market offset calculations
EXCHANGE_LONGITUDES = {
    'NYSE': -74.006,      # New York
    'NASDAQ': -74.006,    # New York
    'CME': -87.630,       # Chicago
    'LSE': -0.076,        # London
    'TSE': 139.691,       # Tokyo
    'HKEX': 114.158,      # Hong Kong
    'ASX': 151.209,       # Sydney
    'FSE': 8.682,         # Frankfurt
    'SGX': 103.851,       # Singapore
    'BSE': 72.835,        # Mumbai
}


def get_asset_profile(symbol: str) -> Optional[Dict]:
    """Get predefined asset profile by symbol."""
    return ASSET_PROFILES.get(symbol.upper())


def calculate_birth_cycles(profile: Dict, current_date: datetime = None) -> Dict:
    """
    Calculate Jenkins cycles from asset birth date.

    Jenkins: "from the date of birth of the stock it could be determined
    for once and for all time what time factor would be used"

    Args:
        profile: Asset profile dict with birth_date, birth_price, etc.
        current_date: Date to calculate cycles to (default: today)

    Returns:
        Dict with birth-based cycle calculations
    """
    if current_date is None:
        current_date = datetime.now()

    birth_date = datetime.strptime(profile['birth_date'], '%Y-%m-%d')
    birth_price = profile.get('birth_price', 0) or profile.get('first_trade_price', 0)

    # Days since birth
    days_since_birth = (current_date - birth_date).days

    # Calculate various cycle measurements
    cycles = {
        'symbol': profile.get('name', 'Unknown'),
        'type': profile.get('type', 'unknown'),
        'birth_date': profile['birth_date'],
        'birth_price': birth_price,
        'days_since_birth': days_since_birth,
        'weeks_since_birth': round(days_since_birth / 7, 1),
        'months_since_birth': round(days_since_birth / 30.4375, 1),
        'years_since_birth': round(days_since_birth / 365.25, 2),

        # Birth price cycles
        'birth_price_as_days': round(birth_price, 0),
        'birth_price_as_weeks': round(birth_price / 7, 1),
        'birth_price_sqrt': round(math.sqrt(birth_price) if birth_price > 0 else 0, 2),
        'birth_price_as_degrees': round(birth_price % 360, 2),

        # Time = Birth Price square-outs
        'time_squares_birth_price': abs(days_since_birth - birth_price) < 5 if birth_price > 0 else False,

        # Degree-based cycles from birth
        'degrees_traveled': round((days_since_birth % 360), 2),
        'full_rotations': days_since_birth // 360,

        # Key anniversary dates
        'anniversaries': []
    }

    # Calculate upcoming anniversaries
    for years in range(1, 6):
        anniversary = birth_date + timedelta(days=years * 365.25)
        if anniversary > current_date:
            days_until = (anniversary - current_date).days
            cycles['anniversaries'].append({
                'years': years,
                'date': anniversary.strftime('%Y-%m-%d'),
                'days_until': days_until
            })

    # ATH/ATL cycles if available
    if profile.get('ath_date'):
        ath_date = datetime.strptime(profile['ath_date'], '%Y-%m-%d')
        days_from_ath = (current_date - ath_date).days
        cycles['ath'] = {
            'price': profile['ath_price'],
            'date': profile['ath_date'],
            'days_ago': days_from_ath,
            'ath_as_degrees': round(profile['ath_price'] % 360, 2),
            'time_squares_ath': abs(days_from_ath - (profile['ath_price'] % 1000)) < 5
        }

    if profile.get('atl_date'):
        atl_date = datetime.strptime(profile['atl_date'], '%Y-%m-%d')
        days_from_atl = (current_date - atl_date).days
        cycles['atl'] = {
            'price': profile['atl_price'],
            'date': profile['atl_date'],
            'days_ago': days_from_atl,
            'atl_as_degrees': round(profile['atl_price'] % 360, 2)
        }

    # Planetary cycles from birth (if ephem available)
    if EPHEM_AVAILABLE:
        cycles['planetary_from_birth'] = calculate_planetary_movement_from_date(
            profile['birth_date'], current_date.strftime('%Y-%m-%d')
        )

    return cycles


def calculate_planetary_movement_from_date(start_date: str, end_date: str) -> Dict:
    """
    Calculate how much each planet has moved since a start date.

    Jenkins uses this to find when planet movement = price or time.
    Example from his book: "IPO @96, Jupiter moved 96 by 8/14/04"

    Args:
        start_date: Birth/IPO date string 'YYYY-MM-DD'
        end_date: Current/target date string 'YYYY-MM-DD'

    Returns:
        Dict with degrees moved for each planet
    """
    if not EPHEM_AVAILABLE:
        return {'error': 'ephem not available'}

    start = ephem.Date(start_date)
    end = ephem.Date(end_date)

    planets = {
        'Sun': ephem.Sun,
        'Moon': ephem.Moon,
        'Mercury': ephem.Mercury,
        'Venus': ephem.Venus,
        'Mars': ephem.Mars,
        'Jupiter': ephem.Jupiter,
        'Saturn': ephem.Saturn,
        'Uranus': ephem.Uranus,
        'Neptune': ephem.Neptune
    }

    movements = {}
    for name, planet_class in planets.items():
        planet = planet_class()

        # Position at start
        planet.compute(start)
        start_lon = math.degrees(float(planet.hlon))  # Heliocentric

        # Position at end
        planet.compute(end)
        end_lon = math.degrees(float(planet.hlon))

        # Calculate movement (accounting for 360° wrap)
        movement = end_lon - start_lon
        if movement < 0:
            movement += 360

        # For slow planets, calculate total degrees including full rotations
        days_elapsed = end - start
        if name == 'Jupiter':
            # Jupiter: ~12 years per orbit
            full_orbits = int(days_elapsed / (12 * 365.25))
            movement += full_orbits * 360
        elif name == 'Saturn':
            # Saturn: ~29.5 years per orbit
            full_orbits = int(days_elapsed / (29.5 * 365.25))
            movement += full_orbits * 360
        elif name == 'Mars':
            # Mars: ~1.88 years per orbit
            full_orbits = int(days_elapsed / (1.88 * 365.25))
            movement += full_orbits * 360

        movements[name] = {
            'degrees_moved': round(movement, 2),
            'current_longitude': round(end_lon, 2)
        }

    return movements


def get_all_asset_profiles() -> Dict:
    """Return all predefined asset profiles."""
    return ASSET_PROFILES


def get_assets_by_type(asset_type: str) -> Dict:
    """Get all assets of a specific type (crypto, stock, index, metal)."""
    return {k: v for k, v in ASSET_PROFILES.items() if v.get('type') == asset_type}


def calculate_daily_square_outs(high: float, low: float, high_idx: int, low_idx: int,
                                 current_idx: int, asset_type: str = 'crypto') -> Dict:
    """
    Jenkins Time = Price for Daily High/Low analysis.

    For intraday/daily charts, different scale factors work:
    - Crypto (5-6 digits): ÷10000, √÷10, mod360
    - Stocks (2-3 digits): ÷10, √, direct
    - Indices (3-4 digits): ÷100, √, mod360

    Args:
        high: Daily/swing high price
        low: Daily/swing low price
        high_idx: Bar index of high
        low_idx: Bar index of low
        current_idx: Current bar index
        asset_type: 'crypto', 'stock', 'index', 'metal'

    Returns:
        Dict with daily square-out analysis
    """
    range_size = high - low
    bars_from_high = current_idx - high_idx
    bars_from_low = current_idx - low_idx
    bars_in_range = abs(high_idx - low_idx)

    # Scale factors based on asset type
    if asset_type == 'crypto':
        # BTC ~100000, ETH ~3000
        scale_factors = [
            ('÷10000', lambda p: p / 10000),
            ('÷1000', lambda p: p / 1000),
            ('√÷10', lambda p: math.sqrt(p) / 10),
            ('√', lambda p: math.sqrt(p)),
            ('mod360', lambda p: p % 360),
            ('last2dig', lambda p: p % 100),
        ]
    elif asset_type == 'stock':
        # AAPL ~200, TSLA ~400
        scale_factors = [
            ('direct', lambda p: p),
            ('÷10', lambda p: p / 10),
            ('√', lambda p: math.sqrt(p)),
            ('mod360', lambda p: p % 360),
        ]
    elif asset_type == 'index':
        # SPY ~500, QQQ ~500
        scale_factors = [
            ('direct', lambda p: p),
            ('÷10', lambda p: p / 10),
            ('÷100', lambda p: p / 100),
            ('√', lambda p: math.sqrt(p)),
        ]
    elif asset_type == 'commodity':
        # CL ~70, NG ~3
        scale_factors = [
            ('direct', lambda p: p),
            ('×10', lambda p: p * 10),
            ('√', lambda p: math.sqrt(p)),
            ('mod360', lambda p: p % 360),
        ]
    else:  # metal
        # GOLD ~2700, SILVER ~30
        scale_factors = [
            ('direct', lambda p: p),
            ('÷10', lambda p: p / 10),
            ('÷100', lambda p: p / 100),
            ('√', lambda p: math.sqrt(p)),
        ]

    def find_matches(price: float, bars: int, label: str) -> List[Dict]:
        """Find scale factors where time ≈ price."""
        matches = []
        for scale_name, scale_fn in scale_factors:
            scaled = scale_fn(price)
            if scaled > 0 and bars > 0:
                diff = abs(bars - scaled)
                pct = (diff / bars) * 100
                if pct < 20:  # Within 20%
                    matches.append({
                        'price_label': label,
                        'scale': scale_name,
                        'scaled_price': round(scaled, 1),
                        'bars': bars,
                        'diff': round(diff, 1),
                        'pct_diff': round(pct, 1),
                        'is_exact': pct < 3,
                        'is_close': pct < 10
                    })
        return sorted(matches, key=lambda x: x['pct_diff'])

    # Check square-outs from high
    high_matches = find_matches(high, bars_from_high, 'High')

    # Check square-outs from low
    low_matches = find_matches(low, bars_from_low, 'Low')

    # Check range vs time
    range_matches = find_matches(range_size, bars_in_range, 'Range')

    # Project upcoming square-outs
    upcoming = []
    for price, label, origin_idx in [(high, 'High', high_idx), (low, 'Low', low_idx)]:
        for scale_name, scale_fn in scale_factors:
            scaled = scale_fn(price)
            if scaled > 0:
                target_bar = origin_idx + int(scaled)
                bars_away = target_bar - current_idx
                if -5 <= bars_away <= 30:
                    upcoming.append({
                        'from': label,
                        'scale': scale_name,
                        'target_bar': target_bar,
                        'bars_away': bars_away,
                        'status': 'NOW!' if abs(bars_away) <= 1 else ('SOON' if bars_away <= 5 else 'UPCOMING')
                    })

    upcoming.sort(key=lambda x: abs(x['bars_away']))

    return {
        'high': high,
        'low': low,
        'range': range_size,
        'bars_from_high': bars_from_high,
        'bars_from_low': bars_from_low,
        'bars_in_range': bars_in_range,
        'asset_type': asset_type,

        # Best matches found
        'high_matches': high_matches[:3],
        'low_matches': low_matches[:3],
        'range_matches': range_matches[:3],

        # All exact matches (< 3%)
        'exact_matches': [m for m in high_matches + low_matches + range_matches if m['is_exact']],

        # Upcoming square-outs
        'upcoming': upcoming[:10],

        # Summary
        'has_active_square_out': any(m['is_exact'] for m in high_matches + low_matches + range_matches)
    }


def calculate_square_root_levels(price: float, increments: int = 4) -> Dict[str, List[float]]:
    """
    Jenkins Natural Ratio - Square root support/resistance levels.

    Take sqrt of price, add/subtract 0.25 increments, re-square.

    Args:
        price: Current price or significant high/low
        increments: Number of levels to calculate (default 4)

    Returns:
        Dict with 'support' and 'resistance' levels
    """
    sqrt_price = math.sqrt(price)

    support = []
    resistance = []

    for i in range(1, increments + 1):
        # Support: sqrt - (0.25 * i) then square
        sup_sqrt = sqrt_price - (0.25 * i)
        if sup_sqrt > 0:
            support.append(round(sup_sqrt ** 2, 2))

        # Resistance: sqrt + (0.25 * i) then square
        res_sqrt = sqrt_price + (0.25 * i)
        resistance.append(round(res_sqrt ** 2, 2))

    return {
        'price': price,
        'sqrt': round(sqrt_price, 4),
        'support': support,
        'resistance': resistance
    }


def calculate_sqrt_sqrt_levels(price: float, increments: int = 4) -> Dict[str, List[float]]:
    """
    Square root of square root levels for finer granularity.

    Used for intraday and shorter-term cycles.

    Args:
        price: Current price or significant high/low
        increments: Number of levels to calculate

    Returns:
        Dict with support and resistance levels
    """
    sqrt_sqrt = math.sqrt(math.sqrt(price))

    support = []
    resistance = []

    for i in range(1, increments + 1):
        # Support
        sup = sqrt_sqrt - (0.125 * i)  # Finer increment for sqrt(sqrt)
        if sup > 0:
            support.append(round(sup ** 4, 2))

        # Resistance
        res = sqrt_sqrt + (0.125 * i)
        resistance.append(round(res ** 4, 2))

    return {
        'price': price,
        'sqrt_sqrt': round(sqrt_sqrt, 4),
        'support': support,
        'resistance': resistance
    }


def calculate_time_conversion_bar(bar_height: float, scale_factor: float = 1.0) -> Dict:
    """
    Jenkins Time Conversion Bar (TCB).

    The height of a significant price bar, when rotated 90 degrees,
    represents the time duration of the expected correction/continuation.

    Args:
        bar_height: High - Low of the significant bar
        scale_factor: Scaling factor for time conversion (chart dependent)

    Returns:
        Dict with time projections in various units
    """
    time_units = bar_height * scale_factor

    return {
        'bar_height': bar_height,
        'time_units': round(time_units, 2),
        'minutes': round(time_units, 0),
        'hours': round(time_units / 60, 2),
        'days': round(time_units / 390, 2),  # 390 min trading day
        'weeks': round(time_units / (390 * 5), 2),
        'calendar_days': round(time_units, 0)
    }


def calculate_reversal_signals(candles: List[Dict]) -> List[Dict]:
    """
    Jenkins Reversal Signals.

    BUY: Price exceeds high of the lowest low bar
    SELL: Price exceeds low of the highest high bar

    Args:
        candles: List of OHLC candles

    Returns:
        List of signal dicts with type and price level
    """
    if len(candles) < 3:
        return []

    signals = []

    for i in range(2, len(candles)):
        prev_candle = candles[i - 1]
        curr_candle = candles[i]

        # Find lowest low in recent bars
        recent_lows = [c['low'] for c in candles[max(0, i-5):i]]
        lowest_low_idx = recent_lows.index(min(recent_lows))
        lowest_low_bar = candles[max(0, i-5) + lowest_low_idx]

        # Find highest high in recent bars
        recent_highs = [c['high'] for c in candles[max(0, i-5):i]]
        highest_high_idx = recent_highs.index(max(recent_highs))
        highest_high_bar = candles[max(0, i-5) + highest_high_idx]

        # BUY signal: break above high of lowest low bar
        if curr_candle['high'] > lowest_low_bar['high'] and prev_candle['high'] <= lowest_low_bar['high']:
            signals.append({
                'type': 'BUY',
                'index': i,
                'price': lowest_low_bar['high'],
                'timestamp': curr_candle.get('timestamp'),
                'description': f"Break above high of low bar ({lowest_low_bar['high']})"
            })

        # SELL signal: break below low of highest high bar
        if curr_candle['low'] < highest_high_bar['low'] and prev_candle['low'] >= highest_high_bar['low']:
            signals.append({
                'type': 'SELL',
                'index': i,
                'price': highest_high_bar['low'],
                'timestamp': curr_candle.get('timestamp'),
                'description': f"Break below low of high bar ({highest_high_bar['low']})"
            })

    return signals


def calculate_measured_moves(candles: List[Dict], lookback: int = 50) -> Dict:
    """
    Calculate typical measured move distances.

    Track average and extreme move distances for projections.

    Args:
        candles: List of OHLC candles
        lookback: Number of bars to analyze

    Returns:
        Dict with measured move statistics
    """
    if len(candles) < lookback:
        lookback = len(candles)

    recent = candles[-lookback:]

    # Calculate ranges
    ranges = [c['high'] - c['low'] for c in recent]
    avg_range = np.mean(ranges)
    max_range = max(ranges)

    # Calculate net changes
    net_changes = []
    for i in range(1, len(recent)):
        net_changes.append(abs(recent[i]['close'] - recent[i-1]['close']))

    avg_net = np.mean(net_changes) if net_changes else 0
    max_net = max(net_changes) if net_changes else 0

    # Find swing moves (multi-bar advances/declines)
    swings = []
    swing_start = 0
    direction = 1 if recent[1]['close'] > recent[0]['close'] else -1

    for i in range(2, len(recent)):
        new_direction = 1 if recent[i]['close'] > recent[i-1]['close'] else -1
        if new_direction != direction:
            swing_size = abs(recent[i-1]['close'] - recent[swing_start]['close'])
            swings.append(swing_size)
            swing_start = i - 1
            direction = new_direction

    return {
        'avg_bar_range': round(avg_range, 2),
        'max_bar_range': round(max_range, 2),
        'avg_net_change': round(avg_net, 2),
        'max_net_change': round(max_net, 2),
        'avg_swing': round(np.mean(swings), 2) if swings else 0,
        'max_swing': round(max(swings), 2) if swings else 0,
        'typical_moves': {
            '1x': round(avg_range, 2),
            '1.5x': round(avg_range * 1.5, 2),
            '2x': round(avg_range * 2, 2),
            '2.5x': round(avg_range * 2.5, 2),
            '3x': round(avg_range * 3, 2)
        }
    }


def calculate_overlap_zones(prev_high: float, prev_low: float) -> Dict:
    """
    Jenkins Overlap Method for counter-trend entries.

    Prior day high/low ± 1/4 prior day range defines entry zones.

    Args:
        prev_high: Previous bar/day high
        prev_low: Previous bar/day low

    Returns:
        Dict with buy and sell overlap zones
    """
    range_size = prev_high - prev_low
    quarter_range = range_size * 0.25

    return {
        'prev_high': prev_high,
        'prev_low': prev_low,
        'range': round(range_size, 2),
        'buy_zone': {
            'upper': round(prev_low + quarter_range, 2),
            'lower': round(prev_low - quarter_range, 2)
        },
        'sell_zone': {
            'upper': round(prev_high + quarter_range, 2),
            'lower': round(prev_high - quarter_range, 2)
        }
    }


def calculate_gann_angles(price: float, time_units: int, scale: float = 1.0) -> Dict:
    """
    Calculate Gann angle price levels from a pivot point.

    Standard angles: 1x1 (45°), 2x1, 1x2, 4x1, 1x4, 8x1, 1x8

    Args:
        price: Starting price (pivot high or low)
        time_units: Number of time units forward
        scale: Price/time scaling factor

    Returns:
        Dict with angle projections
    """
    angles = {
        '8x1': 8,    # Steepest up
        '4x1': 4,
        '2x1': 2,
        '1x1': 1,    # 45 degrees
        '1x2': 0.5,
        '1x4': 0.25,
        '1x8': 0.125  # Flattest
    }

    up_levels = {}
    down_levels = {}

    for name, rate in angles.items():
        move = time_units * rate * scale
        up_levels[name] = round(price + move, 2)
        down_levels[name] = round(price - move, 2)

    return {
        'origin_price': price,
        'time_units': time_units,
        'scale': scale,
        'up': up_levels,
        'down': down_levels
    }


def calculate_time_price_square(price: float) -> Dict:
    """
    Time & Price Squaring - when price = time units.

    A significant high/low in price will square out when
    that many time units have passed.

    Args:
        price: Significant high or low price

    Returns:
        Dict with square-out time projections
    """
    return {
        'price': price,
        'square_out_minutes': round(price, 0),
        'square_out_hours': round(price / 60, 2),
        'square_out_days': round(price, 0),
        'square_out_weeks': round(price / 5, 1),
        'square_out_months': round(price / 21, 1),  # ~21 trading days/month
        'sqrt_time': round(math.sqrt(price), 2),
        'sqrt_sqrt_time': round(math.sqrt(math.sqrt(price)), 2)
    }


def calculate_time_equals_price(high: float, low: float, high_bar: int, low_bar: int,
                                 current_bar: int) -> Dict:
    """
    Jenkins Time = Price Analysis.

    Core principle: Time and Price are interchangeable.
    - A $50 high spins out 50 unit time harmonics
    - When time passed = price level, a turn (square out) occurs

    Three types of square outs:
    1. Square the High: time from high = high price
    2. Square the Low: time from low = low price
    3. Square the Range: time duration = price range

    For large prices (like BTC), we use scaled versions:
    - Direct price
    - Price / 10, / 100, / 1000
    - Sqrt(price)
    - Sqrt(sqrt(price))

    Args:
        high: The significant high price
        low: The significant low price
        high_bar: Bar index of the high
        low_bar: Bar index of the low
        current_bar: Current bar index

    Returns:
        Dict with time=price analysis and projected square-out bars
    """
    range_size = high - low
    bars_from_high = current_bar - high_bar
    bars_from_low = current_bar - low_bar
    bars_in_range = abs(high_bar - low_bar)

    # Calculate various price-to-time conversions
    # For large prices like BTC at 96000, we need scaled versions

    def get_time_harmonics(price: float, label: str) -> Dict:
        """Get time harmonics for a price level."""
        return {
            'label': label,
            'price': price,
            'direct': round(price, 0),
            'div_10': round(price / 10, 1),
            'div_100': round(price / 100, 2),
            'div_1000': round(price / 1000, 3),
            'sqrt': round(math.sqrt(price), 2),
            'sqrt_sqrt': round(math.sqrt(math.sqrt(price)), 2)
        }

    # Square the High projections
    high_harmonics = get_time_harmonics(high, 'High')

    # Square the Low projections
    low_harmonics = get_time_harmonics(low, 'Low')

    # Square the Range projections
    range_harmonics = get_time_harmonics(range_size, 'Range')

    # Find upcoming square-out bars
    square_outs = []

    # Check which harmonics are approaching
    for harmonics, origin_bar, origin_name in [
        (high_harmonics, high_bar, 'High'),
        (low_harmonics, low_bar, 'Low')
    ]:
        for scale_name in ['direct', 'div_10', 'div_100', 'div_1000', 'sqrt', 'sqrt_sqrt']:
            time_units = harmonics[scale_name]
            if time_units > 0:
                target_bar = origin_bar + int(time_units)
                bars_away = target_bar - current_bar

                # Only show upcoming or recent square-outs
                if -10 <= bars_away <= 100:
                    square_outs.append({
                        'type': f'Square {origin_name}',
                        'scale': scale_name,
                        'price_value': harmonics['price'],
                        'time_units': time_units,
                        'target_bar': target_bar,
                        'bars_away': bars_away,
                        'status': 'NOW' if abs(bars_away) <= 2 else ('PAST' if bars_away < 0 else 'UPCOMING')
                    })

    # Sort by bars_away (closest first)
    square_outs.sort(key=lambda x: abs(x['bars_away']))

    # 45-degree angle analysis (1x1 line where time = price)
    # From the high going down, where does 1x1 line hit key levels?
    angle_45_from_high = []
    for bars_forward in [10, 20, 30, 50, 100]:
        price_at_angle = high - bars_forward  # 1 point per bar down
        angle_45_from_high.append({
            'bars': bars_forward,
            'price': round(price_at_angle, 2)
        })

    # From the low going up
    angle_45_from_low = []
    for bars_forward in [10, 20, 30, 50, 100]:
        price_at_angle = low + bars_forward  # 1 point per bar up
        angle_45_from_low.append({
            'bars': bars_forward,
            'price': round(price_at_angle, 2)
        })

    return {
        'high': high,
        'low': low,
        'range': range_size,
        'high_bar': high_bar,
        'low_bar': low_bar,
        'current_bar': current_bar,
        'bars_from_high': bars_from_high,
        'bars_from_low': bars_from_low,
        'bars_in_range': bars_in_range,

        # Time harmonics for each price level
        'high_harmonics': high_harmonics,
        'low_harmonics': low_harmonics,
        'range_harmonics': range_harmonics,

        # Upcoming square-outs
        'square_outs': square_outs[:15],  # Top 15 closest

        # 45-degree (1x1) projections
        'angle_45_from_high': angle_45_from_high,
        'angle_45_from_low': angle_45_from_low,

        # Key insight: Range should equal time
        'range_time_equality': {
            'range_points': range_size,
            'bars_in_range': bars_in_range,
            'ratio': round(range_size / bars_in_range, 2) if bars_in_range > 0 else 0,
            'is_squared': abs(range_size - bars_in_range) < (range_size * 0.1)  # Within 10%
        }
    }


def calculate_time_as_longitude(price: float, time_minutes: int = None,
                                 time_days: int = None) -> Dict:
    """
    Jenkins Time-Longitude Conversion.

    Core principle: Earth rotates 360° in 24 hours.
    - 1 degree = 4 minutes
    - 15 degrees = 1 hour (sun moves 15° per hour)
    - 360 degrees = 1 day

    Price can be converted to degrees, then to time:
    - Price as degrees → time cycles
    - Price / 10 (move decimal) → degrees → months/days

    Args:
        price: Price to convert to time via longitude
        time_minutes: Optional - convert minutes to degrees
        time_days: Optional - convert days to degrees

    Returns:
        Dict with time-longitude conversions
    """
    # Constants
    DEGREES_PER_DAY = 360
    DEGREES_PER_HOUR = 15
    MINUTES_PER_DEGREE = 4
    DAYS_PER_MONTH_AVG = 30.4375  # Jenkins uses this

    result = {
        'price': price,
        'conversions': {}
    }

    # Price as degrees → time conversions
    price_as_degrees = price % 360  # Normalize to 360 circle

    # Direct price interpretations
    result['conversions']['price_as_degrees'] = round(price_as_degrees, 2)
    result['conversions']['price_to_minutes'] = round(price * MINUTES_PER_DEGREE, 0)
    result['conversions']['price_to_hours'] = round(price / DEGREES_PER_HOUR, 2)
    result['conversions']['price_to_days'] = round(price / DEGREES_PER_DAY, 4)

    # Scaled price versions (for large prices like BTC)
    scaled_versions = {
        'div_10': price / 10,
        'div_100': price / 100,
        'div_1000': price / 1000,
        'move_decimal_2': price / 100,  # 96000 → 960
        'move_decimal_3': price / 1000,  # 96000 → 96
    }

    result['scaled_time_cycles'] = {}
    for label, scaled_price in scaled_versions.items():
        # Convert scaled price to days using Jenkins' month formula
        # Price (with decimal moved) × 30.4375 = days
        days_from_price = scaled_price * DAYS_PER_MONTH_AVG
        result['scaled_time_cycles'][label] = {
            'scaled_price': round(scaled_price, 2),
            'as_months': round(scaled_price, 2),
            'as_days': round(days_from_price, 0),
            'as_degrees': round(scaled_price % 360, 2)
        }

    # If time_minutes provided, convert to degrees
    if time_minutes is not None:
        result['time_to_degrees'] = {
            'minutes': time_minutes,
            'degrees': round(time_minutes / MINUTES_PER_DEGREE, 2),
            'hours': round(time_minutes / 60, 2)
        }

    # If time_days provided, convert to degrees
    if time_days is not None:
        result['days_to_degrees'] = {
            'days': time_days,
            'degrees': round(time_days * DEGREES_PER_DAY, 0),
            'full_rotations': time_days,
            'longitude_equivalent': round((time_days * DEGREES_PER_DAY) % 360, 2)
        }

    # Geographic longitude market offsets (Jenkins arbitrage concept)
    # New York to London = ~5 hours = 75°
    # New York to Tokyo = ~14 hours = 210°
    result['market_longitude_offsets'] = {
        'ny_to_london': {'hours': 5, 'degrees': 75},
        'ny_to_tokyo': {'hours': 14, 'degrees': 210},
        'ny_to_hong_kong': {'hours': 13, 'degrees': 195},
        'ny_to_sydney': {'hours': 16, 'degrees': 240}
    }

    # Natural chart intervals based on Earth rotation
    result['natural_chart_intervals'] = {
        '4_min': {'degrees': 1, 'reason': '1 degree Earth rotation'},
        '15_min': {'degrees': 3.75, 'reason': '1/24th of day'},
        '60_min': {'degrees': 15, 'reason': '1 hour = 15° longitude'},
        '240_min': {'degrees': 60, 'reason': '4 hours = 60°'},
        '390_min': {'degrees': 97.5, 'reason': 'NYSE trading day (6.5 hours)'},
        '1440_min': {'degrees': 360, 'reason': 'Full day = 360°'}
    }

    return result


def calculate_circle_projection(high: float, low: float, bars: int) -> Dict:
    """
    Circular arc projection from a swing.

    Draw a circle from the high to low, extending forward to
    find where price might return.

    Args:
        high: Swing high price
        low: Swing low price
        bars: Number of bars in the swing

    Returns:
        Dict with circle projection data
    """
    range_size = high - low
    midpoint = (high + low) / 2
    radius = math.sqrt((range_size/2)**2 + (bars/2)**2)

    return {
        'high': high,
        'low': low,
        'midpoint': round(midpoint, 2),
        'range': round(range_size, 2),
        'bars': bars,
        'radius': round(radius, 2),
        'circle_high': round(midpoint + radius, 2),
        'circle_low': round(midpoint - radius, 2),
        'time_projection': round(radius * 2, 0)
    }


def calculate_natural_squares_time(start_bar: int = 0) -> List[int]:
    """
    Natural square time cycles.

    Time tends to turn at square numbers: 4, 9, 16, 25, 36, 49, 64, 81...

    Args:
        start_bar: Starting bar index

    Returns:
        List of square number bar indices
    """
    squares = []
    for i in range(2, 20):
        squares.append(start_bar + i**2)
    return squares


def calculate_fibonacci_time(start_bar: int = 0) -> List[int]:
    """
    Fibonacci time cycles.

    Args:
        start_bar: Starting bar index

    Returns:
        List of Fibonacci bar indices
    """
    fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]
    return [start_bar + f for f in fib]


def calculate_moon_cycles(start_date: datetime) -> List[Dict]:
    """
    Moon cycle turning points.

    Full cycle = ~29.5 days (360 degrees)
    Key points: 0°, 90°, 180°, 270°

    Args:
        start_date: Starting date for calculations

    Returns:
        List of moon cycle dates with degree positions
    """
    lunar_month = 29.53059  # days

    cycles = []
    for i in range(8):  # 2 full cycles
        for degree, name in [(0, 'New Moon'), (90, 'First Quarter'),
                              (180, 'Full Moon'), (270, 'Last Quarter')]:
            days_offset = (i * lunar_month) + (degree / 360 * lunar_month)
            cycle_date = start_date + timedelta(days=days_offset)
            cycles.append({
                'date': cycle_date.strftime('%Y-%m-%d'),
                'degree': degree,
                'name': name,
                'days_from_start': round(days_offset, 1)
            })

    return sorted(cycles, key=lambda x: x['days_from_start'])


def calculate_pi_cycles(price_or_time: float) -> Dict:
    """
    PI-based cycle projections.

    PI (3.14159) is used as a multiplier for time cycles.

    Args:
        price_or_time: Base value for PI calculation

    Returns:
        Dict with PI projections
    """
    pi = math.pi

    return {
        'base': price_or_time,
        'pi_1': round(price_or_time * pi, 2),
        'pi_2': round(price_or_time * pi * 2, 2),
        'pi_half': round(price_or_time * pi / 2, 2),
        'pi_quarter': round(price_or_time * pi / 4, 2),
        'pi_sqrt': round(price_or_time * math.sqrt(pi), 2)
    }


# ================== PLANETARY CALCULATIONS (Jenkins Astro Methods) ==================

def get_planetary_positions(date: datetime = None,
                           location: Tuple[float, float] = (40.7128, -74.0060)) -> Dict:
    """
    Calculate geocentric and heliocentric planetary positions.

    Jenkins uses both geocentric (Earth-centered) and heliocentric (Sun-centered)
    positions for "square outs" where price = planetary longitude.

    Args:
        date: Date for calculations (default: now)
        location: (latitude, longitude) tuple (default: NYC)

    Returns:
        Dict with planetary positions in degrees
    """
    if not EPHEM_AVAILABLE:
        return {'error': 'ephem library not available'}

    if date is None:
        date = datetime.utcnow()

    # Set up observer for location-based calculations (MC, ASC)
    observer = ephem.Observer()
    observer.lat = str(location[0])
    observer.lon = str(location[1])
    observer.date = date

    # Planets to calculate
    planets = {
        'Sun': ephem.Sun(),
        'Moon': ephem.Moon(),
        'Mercury': ephem.Mercury(),
        'Venus': ephem.Venus(),
        'Mars': ephem.Mars(),
        'Jupiter': ephem.Jupiter(),
        'Saturn': ephem.Saturn(),
        'Uranus': ephem.Uranus(),
        'Neptune': ephem.Neptune(),
        'Pluto': ephem.Pluto()
    }

    positions = {
        'date': date.strftime('%Y-%m-%d %H:%M:%S'),
        'location': {'lat': location[0], 'lon': location[1]},
        'geocentric': {},
        'heliocentric': {}
    }

    for name, planet in planets.items():
        planet.compute(observer)

        # Geocentric longitude (degrees)
        geo_lon = math.degrees(float(planet.hlon)) if hasattr(planet, 'hlon') else math.degrees(float(planet.ra))
        # For proper ecliptic longitude
        geo_lon_ecliptic = math.degrees(float(planet.g_ra)) if hasattr(planet, 'g_ra') else geo_lon

        positions['geocentric'][name] = {
            'longitude': round(geo_lon_ecliptic % 360, 2),
            'latitude': round(math.degrees(float(planet.dec)), 2) if hasattr(planet, 'dec') else 0,
        }

        # Heliocentric (Sun-centered) - only for planets, not Sun/Moon
        if name not in ['Sun', 'Moon']:
            try:
                helio_lon = math.degrees(float(planet.hlon))
                helio_lat = math.degrees(float(planet.hlat))
                positions['heliocentric'][name] = {
                    'longitude': round(helio_lon % 360, 2),
                    'latitude': round(helio_lat, 2)
                }
            except:
                pass

    # Calculate MC (Midheaven) and ASC (Ascendant)
    try:
        # Sidereal time for MC calculation
        sidereal = float(observer.sidereal_time())
        mc_degrees = math.degrees(sidereal) % 360

        # Simple ASC approximation (90 degrees from MC adjusted for latitude)
        lat_rad = math.radians(location[0])
        asc_degrees = (mc_degrees + 90 + math.degrees(lat_rad) * 0.5) % 360

        positions['angles'] = {
            'MC': round(mc_degrees, 2),
            'ASC': round(asc_degrees, 2)
        }
    except:
        pass

    return positions


def calculate_planetary_square_outs(price: float,
                                    positions: Dict = None,
                                    date: datetime = None) -> Dict:
    """
    Jenkins Planetary Square Outs.

    Find planets whose longitude matches or is harmonically related to price.
    Price "squares out" when price = planet degree (or multiples of 360).

    Args:
        price: Current price to check for square outs
        positions: Pre-calculated positions (or will calculate)
        date: Date for calculations

    Returns:
        Dict with square out matches
    """
    if positions is None:
        positions = get_planetary_positions(date)

    if 'error' in positions:
        return positions

    # Normalize price to 0-360 range (for direct comparison)
    price_mod_360 = price % 360

    # Also check price / 10, / 100 for larger prices
    price_scales = [
        ('direct', price % 360),
        ('div_10', (price / 10) % 360),
        ('div_100', (price / 100) % 360),
    ]

    # For crypto, also check larger scales
    if price > 1000:
        price_scales.append(('div_1000', (price / 1000) % 360))

    square_outs = {
        'price': price,
        'matches': [],
        'near_matches': []
    }

    orb = 2.0  # Degrees of allowable orb for match

    for scale_name, scaled_price in price_scales:
        # Check geocentric positions
        for planet, data in positions.get('geocentric', {}).items():
            lon = data.get('longitude', 0)
            diff = abs(scaled_price - lon)
            diff = min(diff, 360 - diff)  # Account for wrap-around

            if diff <= orb:
                square_outs['matches'].append({
                    'planet': planet,
                    'type': 'geocentric',
                    'longitude': lon,
                    'price_scale': scale_name,
                    'scaled_price': round(scaled_price, 2),
                    'orb': round(diff, 2)
                })
            elif diff <= 5.0:
                square_outs['near_matches'].append({
                    'planet': planet,
                    'type': 'geocentric',
                    'longitude': lon,
                    'price_scale': scale_name,
                    'orb': round(diff, 2)
                })

        # Check heliocentric positions
        for planet, data in positions.get('heliocentric', {}).items():
            lon = data.get('longitude', 0)
            diff = abs(scaled_price - lon)
            diff = min(diff, 360 - diff)

            if diff <= orb:
                square_outs['matches'].append({
                    'planet': planet,
                    'type': 'heliocentric',
                    'longitude': lon,
                    'price_scale': scale_name,
                    'scaled_price': round(scaled_price, 2),
                    'orb': round(diff, 2)
                })
            elif diff <= 5.0:
                square_outs['near_matches'].append({
                    'planet': planet,
                    'type': 'heliocentric',
                    'longitude': lon,
                    'price_scale': scale_name,
                    'orb': round(diff, 2)
                })

    return square_outs


def calculate_planetary_aspects(positions: Dict = None,
                               date: datetime = None) -> List[Dict]:
    """
    Calculate major planetary aspects (angles between planets).

    Jenkins uses conjunctions (0°), squares (90°), trines (120°),
    oppositions (180°) for timing.

    Args:
        positions: Pre-calculated positions
        date: Date for calculations

    Returns:
        List of current aspects
    """
    if positions is None:
        positions = get_planetary_positions(date)

    if 'error' in positions:
        return []

    # Major aspects and their orbs
    aspects = {
        'conjunction': (0, 8),
        'sextile': (60, 4),
        'square': (90, 6),
        'trine': (120, 6),
        'opposition': (180, 8)
    }

    found_aspects = []
    geo_planets = positions.get('geocentric', {})
    planet_names = list(geo_planets.keys())

    for i, p1 in enumerate(planet_names):
        for p2 in planet_names[i+1:]:
            lon1 = geo_planets[p1].get('longitude', 0)
            lon2 = geo_planets[p2].get('longitude', 0)

            diff = abs(lon1 - lon2)
            if diff > 180:
                diff = 360 - diff

            for aspect_name, (angle, orb) in aspects.items():
                aspect_diff = abs(diff - angle)
                if aspect_diff <= orb:
                    found_aspects.append({
                        'planet1': p1,
                        'planet2': p2,
                        'aspect': aspect_name,
                        'angle': angle,
                        'actual_diff': round(diff, 2),
                        'orb': round(aspect_diff, 2),
                        'applying': lon1 < lon2  # Simplified
                    })

    # Sort by orb (tighter aspects first)
    found_aspects.sort(key=lambda x: x['orb'])

    return found_aspects


def calculate_mars_jupiter_cycle(date: datetime = None) -> Dict:
    """
    Mars/Jupiter synodic cycle - key Jenkins timing tool.

    The Mars/Jupiter conjunction cycle is approximately 2.24 years.
    Jenkins tracks degrees moved from conjunctions for "square outs".

    Args:
        date: Date for calculation

    Returns:
        Dict with cycle information
    """
    if not EPHEM_AVAILABLE:
        return {'error': 'ephem library not available'}

    if date is None:
        date = datetime.utcnow()

    observer = ephem.Observer()
    observer.date = date

    mars = ephem.Mars()
    jupiter = ephem.Jupiter()
    mars.compute(observer)
    jupiter.compute(observer)

    # Heliocentric longitudes
    mars_lon = math.degrees(float(mars.hlon)) % 360
    jupiter_lon = math.degrees(float(jupiter.hlon)) % 360

    # Angular separation
    separation = (mars_lon - jupiter_lon) % 360
    if separation > 180:
        separation = 360 - separation

    return {
        'date': date.strftime('%Y-%m-%d'),
        'mars_helio': round(mars_lon, 2),
        'jupiter_helio': round(jupiter_lon, 2),
        'separation': round(separation, 2),
        'cycle_position': round(separation / 360 * 100, 1),  # % through cycle
        'days_to_conjunction': round((360 - separation) / 0.44, 0) if separation > 10 else 0,
        'conjunction_price_levels': [
            round(mars_lon, 0),
            round(mars_lon + 360, 0),
            round(mars_lon + 720, 0)
        ]
    }


def calculate_jupiter_saturn_cycle(date: datetime = None) -> Dict:
    """
    Jupiter/Saturn 20-year cycle - major economic cycle.

    Jenkins emphasizes the 20-year conjunction cycle and its
    subdivision points (90°, 180°, 270°).

    Args:
        date: Date for calculation

    Returns:
        Dict with cycle information
    """
    if not EPHEM_AVAILABLE:
        return {'error': 'ephem library not available'}

    if date is None:
        date = datetime.utcnow()

    observer = ephem.Observer()
    observer.date = date

    jupiter = ephem.Jupiter()
    saturn = ephem.Saturn()
    jupiter.compute(observer)
    saturn.compute(observer)

    # Heliocentric longitudes
    jupiter_lon = math.degrees(float(jupiter.hlon)) % 360
    saturn_lon = math.degrees(float(saturn.hlon)) % 360

    # Angular separation
    separation = (jupiter_lon - saturn_lon) % 360

    # Determine phase
    if separation < 45:
        phase = 'Conjunction'
    elif separation < 135:
        phase = 'First Square'
    elif separation < 225:
        phase = 'Opposition'
    elif separation < 315:
        phase = 'Last Square'
    else:
        phase = 'Pre-Conjunction'

    return {
        'date': date.strftime('%Y-%m-%d'),
        'jupiter_helio': round(jupiter_lon, 2),
        'saturn_helio': round(saturn_lon, 2),
        'separation': round(separation, 2),
        'phase': phase,
        'cycle_position': round(separation / 360 * 100, 1),
        'years_in_cycle': round(separation / 360 * 20, 1)
    }


def get_retrograde_status(date: datetime = None) -> Dict:
    """
    Check retrograde status of planets.

    Jenkins notes that retrogrades mark important reversal zones.

    Args:
        date: Date for calculation

    Returns:
        Dict with retrograde status for each planet
    """
    if not EPHEM_AVAILABLE:
        return {'error': 'ephem library not available'}

    if date is None:
        date = datetime.utcnow()

    observer = ephem.Observer()
    observer.date = date

    # Check a day later to determine motion direction
    observer_next = ephem.Observer()
    observer_next.date = date + timedelta(days=1)

    planets = {
        'Mercury': ephem.Mercury(),
        'Venus': ephem.Venus(),
        'Mars': ephem.Mars(),
        'Jupiter': ephem.Jupiter(),
        'Saturn': ephem.Saturn(),
        'Uranus': ephem.Uranus(),
        'Neptune': ephem.Neptune(),
        'Pluto': ephem.Pluto()
    }

    retrograde_status = {}

    for name, planet in planets.items():
        planet.compute(observer)
        lon_today = math.degrees(float(planet.g_ra))

        planet2 = planets[name].__class__()
        planet2.compute(observer_next)
        lon_tomorrow = math.degrees(float(planet2.g_ra))

        # If longitude decreasing, planet is retrograde
        diff = lon_tomorrow - lon_today
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360

        retrograde_status[name] = {
            'retrograde': diff < 0,
            'daily_motion': round(diff, 3)
        }

    return {
        'date': date.strftime('%Y-%m-%d'),
        'planets': retrograde_status
    }


# ================== END PLANETARY CALCULATIONS ==================


def full_jenkins_analysis(candles: List[Dict],
                          current_price: float = None,
                          significant_high: float = None,
                          significant_low: float = None,
                          asset_type: str = 'crypto') -> Dict:
    """
    Complete Jenkins analysis combining all methods.

    Args:
        candles: List of OHLC candles
        current_price: Current price (default: last close)
        significant_high: Major high to analyze (default: period high)
        significant_low: Major low to analyze (default: period low)
        asset_type: 'crypto', 'stock', 'index', 'metal' for proper scaling

    Returns:
        Comprehensive Jenkins analysis dict
    """
    if not candles:
        return {}

    # Defaults
    if current_price is None:
        current_price = candles[-1]['close']
    if significant_high is None:
        significant_high = max(c['high'] for c in candles)
    if significant_low is None:
        significant_low = min(c['low'] for c in candles)

    # Previous bar for overlap
    prev_bar = candles[-2] if len(candles) > 1 else candles[-1]

    # Find largest bar (impulse bar)
    largest_bar = max(candles, key=lambda c: c['high'] - c['low'])
    impulse_height = largest_bar['high'] - largest_bar['low']

    # Find bar indices for high and low
    high_bar = 0
    low_bar = 0
    for i, c in enumerate(candles):
        if c['high'] == significant_high:
            high_bar = i
        if c['low'] == significant_low:
            low_bar = i
    current_bar = len(candles) - 1

    return {
        'timestamp': datetime.now().isoformat(),
        'current_price': current_price,
        'significant_high': significant_high,
        'significant_low': significant_low,

        # Square Root Levels
        'sqrt_levels_high': calculate_square_root_levels(significant_high),
        'sqrt_levels_low': calculate_square_root_levels(significant_low),
        'sqrt_levels_current': calculate_square_root_levels(current_price),

        # Sqrt of Sqrt (finer levels)
        'sqrt_sqrt_high': calculate_sqrt_sqrt_levels(significant_high),
        'sqrt_sqrt_low': calculate_sqrt_sqrt_levels(significant_low),

        # Time Conversion Bar
        'tcb': calculate_time_conversion_bar(impulse_height),

        # Reversal Signals
        'reversal_signals': calculate_reversal_signals(candles[-20:]),

        # Measured Moves
        'measured_moves': calculate_measured_moves(candles),

        # Overlap Zones
        'overlap_zones': calculate_overlap_zones(prev_bar['high'], prev_bar['low']),

        # Gann Angles from high and low
        'gann_angles_high': calculate_gann_angles(significant_high, 20),
        'gann_angles_low': calculate_gann_angles(significant_low, 20),

        # Time-Price Square (simple)
        'time_price_square_high': calculate_time_price_square(significant_high),
        'time_price_square_low': calculate_time_price_square(significant_low),

        # Time = Price Analysis (comprehensive Jenkins method)
        'time_equals_price': calculate_time_equals_price(
            significant_high, significant_low, high_bar, low_bar, current_bar
        ),

        # Circle Projection
        'circle_projection': calculate_circle_projection(
            significant_high, significant_low, len(candles)
        ),

        # Time Cycles
        'natural_squares': calculate_natural_squares_time(),
        'fibonacci_time': calculate_fibonacci_time(),
        'pi_cycles': calculate_pi_cycles(significant_high - significant_low),

        # Planetary Analysis (Jenkins Astro Methods)
        'planetary_positions': get_planetary_positions(),
        'planetary_square_outs': calculate_planetary_square_outs(current_price),
        'planetary_aspects': calculate_planetary_aspects(),
        'mars_jupiter_cycle': calculate_mars_jupiter_cycle(),
        'jupiter_saturn_cycle': calculate_jupiter_saturn_cycle(),
        'retrograde_status': get_retrograde_status(),

        # Time as Longitude (Earth rotation = degrees = time)
        'time_as_longitude': calculate_time_as_longitude(current_price),
        'time_as_longitude_high': calculate_time_as_longitude(significant_high),
        'time_as_longitude_low': calculate_time_as_longitude(significant_low),

        # Daily Square-Outs (Time = Price for daily high/low)
        'daily_square_outs': calculate_daily_square_outs(
            significant_high, significant_low, high_bar, low_bar, current_bar, asset_type
        )
    }


# Utility function to format analysis for display
def format_jenkins_summary(analysis: Dict) -> str:
    """Format Jenkins analysis as readable summary."""
    if not analysis:
        return "No analysis available"

    lines = [
        "=== JENKINS ANALYSIS SUMMARY ===",
        f"Current Price: {analysis['current_price']}",
        f"Significant High: {analysis['significant_high']}",
        f"Significant Low: {analysis['significant_low']}",
        "",
        "--- SQUARE ROOT SUPPORT/RESISTANCE ---",
        f"From High ({analysis['significant_high']}):",
        f"  Support: {analysis['sqrt_levels_high']['support'][:3]}",
        f"  Resistance: {analysis['sqrt_levels_high']['resistance'][:3]}",
        f"From Low ({analysis['significant_low']}):",
        f"  Support: {analysis['sqrt_levels_low']['support'][:3]}",
        f"  Resistance: {analysis['sqrt_levels_low']['resistance'][:3]}",
        "",
        "--- TIME CONVERSION BAR ---",
        f"Impulse Bar Height: {analysis['tcb']['bar_height']}",
        f"Projected Time: {analysis['tcb']['time_units']} units",
        f"  ~{analysis['tcb']['hours']} hours / ~{analysis['tcb']['days']} days",
        "",
        "--- OVERLAP ZONES ---",
        f"Buy Zone: {analysis['overlap_zones']['buy_zone']}",
        f"Sell Zone: {analysis['overlap_zones']['sell_zone']}",
        "",
        "--- MEASURED MOVES ---",
        f"Avg Bar Range: {analysis['measured_moves']['avg_bar_range']}",
        f"Typical Projections: {analysis['measured_moves']['typical_moves']}",
    ]

    if analysis['reversal_signals']:
        lines.append("")
        lines.append("--- REVERSAL SIGNALS ---")
        for sig in analysis['reversal_signals'][-3:]:
            lines.append(f"  {sig['type']}: {sig['description']}")

    return "\n".join(lines)
