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
                          significant_low: float = None) -> Dict:
    """
    Complete Jenkins analysis combining all methods.

    Args:
        candles: List of OHLC candles
        current_price: Current price (default: last close)
        significant_high: Major high to analyze (default: period high)
        significant_low: Major low to analyze (default: period low)

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

        # Time-Price Square
        'time_price_square_high': calculate_time_price_square(significant_high),
        'time_price_square_low': calculate_time_price_square(significant_low),

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
        'retrograde_status': get_retrograde_status()
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
