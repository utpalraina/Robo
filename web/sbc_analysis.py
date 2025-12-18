"""
Sarvato Bhadra Chakra (SBC) Analysis Module for BTC Trading
Calculates Vedhas (obstructions) based on planetary transits through the SBC grid
"""

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

try:
    import swisseph as swe
    import pytz
    SWISSEPH_AVAILABLE = True
except ImportError:
    SWISSEPH_AVAILABLE = False

# 28 Nakshatras with their starting degrees (sidereal)
NAKSHATRAS = [
    ('Ashwini', 0.0),
    ('Bharani', 13.333333),
    ('Krittika', 26.666667),
    ('Rohini', 40.0),
    ('Mrigashira', 53.333333),
    ('Ardra', 66.666667),
    ('Punarvasu', 80.0),
    ('Pushya', 93.333333),
    ('Ashlesha', 106.666667),
    ('Magha', 120.0),
    ('Purva Phalguni', 133.333333),
    ('Uttara Phalguni', 146.666667),
    ('Hasta', 160.0),
    ('Chitra', 173.333333),
    ('Swati', 186.666667),
    ('Vishakha', 200.0),
    ('Anuradha', 213.333333),
    ('Jyeshtha', 226.666667),
    ('Mula', 240.0),
    ('Purva Ashadha', 253.333333),
    ('Uttara Ashadha', 266.666667),
    ('Shravana', 280.0),
    ('Dhanishta', 293.333333),
    ('Shatabhisha', 306.666667),
    ('Purva Bhadrapada', 320.0),
    ('Uttara Bhadrapada', 333.333333),
    ('Revati', 346.666667),
    ('Abhijit', 276.666667),  # Abhijit is between Uttara Ashadha and Shravana (special nakshatra)
]

# Nakshatra to index mapping (0-27)
NAKSHATRA_NAMES = [n[0] for n in NAKSHATRAS[:27]]  # Exclude Abhijit for standard calculations

# SBC 9x9 Grid Layout - The chakra maps positions in a specific pattern
# Each cell contains: (type, name, index)
# Types: 'N' = Nakshatra, 'T' = Tithi, 'V' = Vara, 'A' = Akshar (vowel/consonant)
SBC_GRID = [
    # Row 0 (outer top)
    [('N', 'Krittika', 2), ('N', 'Rohini', 3), ('N', 'Mrigashira', 4), ('N', 'Ardra', 5),
     ('N', 'Punarvasu', 6), ('N', 'Pushya', 7), ('N', 'Ashlesha', 8), ('N', 'Magha', 9), ('N', 'Purva Phalguni', 10)],
    # Row 1
    [('N', 'Bharani', 1), ('T', 'Purnima', 15), ('V', 'Sunday', 0), ('T', 'Pratipada', 1),
     ('V', 'Monday', 1), ('T', 'Dvitiya', 2), ('V', 'Tuesday', 2), ('T', 'Tritiya', 3), ('N', 'Uttara Phalguni', 11)],
    # Row 2
    [('N', 'Ashwini', 0), ('T', 'Chaturdashi', 14), ('A', 'E', 4), ('A', 'U', 2), ('A', 'Ri', 6),
     ('A', 'O', 8), ('A', 'Au', 10), ('T', 'Chaturthi', 4), ('N', 'Hasta', 12)],
    # Row 3
    [('N', 'Revati', 26), ('V', 'Saturday', 6), ('A', 'A', 0), ('A', 'CENTER', -1), ('A', 'CENTER', -1),
     ('A', 'CENTER', -1), ('A', 'I', 1), ('V', 'Wednesday', 3), ('N', 'Chitra', 13)],
    # Row 4 (middle)
    [('N', 'Uttara Bhadrapada', 25), ('T', 'Trayodashi', 13), ('A', 'Li', 7), ('A', 'CENTER', -1), ('A', 'CENTER', -1),
     ('A', 'CENTER', -1), ('A', 'Lri', 5), ('T', 'Panchami', 5), ('N', 'Swati', 14)],
    # Row 5
    [('N', 'Purva Bhadrapada', 24), ('V', 'Friday', 5), ('A', 'Am', 11), ('A', 'CENTER', -1), ('A', 'CENTER', -1),
     ('A', 'CENTER', -1), ('A', 'Ah', 9), ('V', 'Thursday', 4), ('N', 'Vishakha', 15)],
    # Row 6
    [('N', 'Shatabhisha', 23), ('T', 'Dvadashi', 12), ('A', 'Ya', 28), ('A', 'La', 30), ('A', 'Va', 31),
     ('A', 'Sha', 32), ('A', 'Ra', 29), ('T', 'Shashthi', 6), ('N', 'Anuradha', 16)],
    # Row 7
    [('N', 'Dhanishta', 22), ('T', 'Ekadashi', 11), ('V', 'Saturday', 6), ('T', 'Dashami', 10),
     ('V', 'Friday', 5), ('T', 'Navami', 9), ('V', 'Thursday', 4), ('T', 'Saptami', 7), ('N', 'Jyeshtha', 17)],
    # Row 8 (outer bottom)
    [('N', 'Shravana', 21), ('N', 'Uttara Ashadha', 20), ('N', 'Purva Ashadha', 19), ('N', 'Mula', 18),
     ('N', 'Jyeshtha', 17), ('N', 'Anuradha', 16), ('N', 'Vishakha', 15), ('N', 'Swati', 14), ('N', 'Chitra', 13)],
]

# =====================================================
# PLANET SPEED (GATI) SYSTEM FOR SBC VEDHA
# =====================================================
# In traditional SBC, planet speed affects vedha strength and number of affected points
#
# Gati Types:
# 1. Ati-Chari (Very Fast) - Planet moving much faster than average
# 2. Sheeghra/Chari (Fast) - Planet moving faster than average
# 3. Sama (Normal) - Planet moving at average speed
# 4. Manda (Slow) - Planet moving slower than average
# 5. Ati-Manda (Very Slow) - Planet nearly stationary
# 6. Vakri (Retrograde) - Planet moving backward

# Average daily motion for each planet (degrees per day)
PLANET_AVERAGE_SPEED = {
    'Sun': 0.9856,      # ~1 degree/day
    'Moon': 13.176,     # ~13 degrees/day (fastest)
    'Mars': 0.524,      # Variable, can be retrograde
    'Mercury': 1.383,   # Highly variable
    'Jupiter': 0.083,   # ~5 degrees/month (slow)
    'Venus': 1.2,       # Variable
    'Saturn': 0.033,    # ~2 degrees/month (slowest)
    'Rahu': -0.053,     # Always retrograde (mean motion)
    'Ketu': -0.053,     # Always retrograde (mean motion)
}

# Speed thresholds as percentage of average speed
GATI_THRESHOLDS = {
    'ati_chari': 1.5,      # > 150% of average = very fast
    'sheeghra': 1.2,       # > 120% of average = fast
    'sama_high': 1.1,      # 90-110% = normal
    'sama_low': 0.9,
    'manda': 0.5,          # < 50% of average = slow
    'ati_manda': 0.1,      # < 10% of average = very slow/stationary
}

# Gati effects on vedha
# - vedha_multiplier: Affects strength of vedha
# - vedha_points: Number of cells affected (more for slow planets)
# - duration_factor: How long the vedha lasts
GATI_EFFECTS = {
    'ati_chari': {
        'name': 'Ati-Chari (Very Fast)',
        'vedha_multiplier': 0.5,    # Weak vedha due to quick transit
        'vedha_points': 1,          # Only direct vedha point
        'duration_factor': 0.5,     # Short duration
        'description': 'Planet moving very fast - weak, fleeting vedha'
    },
    'sheeghra': {
        'name': 'Sheeghra (Fast)',
        'vedha_multiplier': 0.75,
        'vedha_points': 1,
        'duration_factor': 0.75,
        'description': 'Planet moving fast - moderate vedha'
    },
    'sama': {
        'name': 'Sama (Normal)',
        'vedha_multiplier': 1.0,    # Standard vedha strength
        'vedha_points': 1,          # Standard affected points
        'duration_factor': 1.0,
        'description': 'Planet moving at normal speed - standard vedha'
    },
    'manda': {
        'name': 'Manda (Slow)',
        'vedha_multiplier': 1.5,    # Stronger vedha due to longer influence
        'vedha_points': 2,          # Affects additional adjacent cells
        'duration_factor': 1.5,
        'description': 'Planet moving slowly - strong, prolonged vedha'
    },
    'ati_manda': {
        'name': 'Ati-Manda (Very Slow/Stationary)',
        'vedha_multiplier': 2.0,    # Very strong vedha
        'vedha_points': 3,          # Affects multiple cells
        'duration_factor': 2.0,
        'description': 'Planet nearly stationary - very strong, extended vedha'
    },
    'vakri': {
        'name': 'Vakri (Retrograde)',
        'vedha_multiplier': 1.75,   # Strong vedha, karmic implications
        'vedha_points': 2,          # Multiple points affected
        'duration_factor': 1.5,
        'description': 'Planet retrograde - strong vedha with karmic effects'
    }
}

# Extended vedha - additional nakshatras affected based on gati
# When a planet is slow/retrograde, it affects adjacent nakshatras too
EXTENDED_VEDHA_NEIGHBORS = {
    # Each nakshatra's adjacent nakshatras in the SBC grid
    0: [1, 26],      # Ashwini neighbors
    1: [0, 2],       # Bharani neighbors
    2: [1, 3],       # Krittika neighbors
    3: [2, 4],       # Rohini neighbors
    4: [3, 5],       # Mrigashira neighbors
    5: [4, 6],       # Ardra neighbors
    6: [5, 7],       # Punarvasu neighbors
    7: [6, 8],       # Pushya neighbors
    8: [7, 9],       # Ashlesha neighbors
    9: [8, 10],      # Magha neighbors
    10: [9, 11],     # P.Phalguni neighbors
    11: [10, 12],    # U.Phalguni neighbors
    12: [11, 13],    # Hasta neighbors
    13: [12, 14],    # Chitra neighbors
    14: [13, 15],    # Swati neighbors
    15: [14, 16],    # Vishakha neighbors
    16: [15, 17],    # Anuradha neighbors
    17: [16, 18],    # Jyeshtha neighbors
    18: [17, 19],    # Mula neighbors
    19: [18, 20],    # P.Ashadha neighbors
    20: [19, 21],    # U.Ashadha neighbors
    21: [20, 22],    # Shravana neighbors
    22: [21, 23],    # Dhanishta neighbors
    23: [22, 24],    # Shatabhisha neighbors
    24: [23, 25],    # P.Bhadrapada neighbors
    25: [24, 26],    # U.Bhadrapada neighbors
    26: [25, 0],     # Revati neighbors
}


def calculate_planet_speed(planet_name: str, jd: float) -> Tuple[float, bool]:
    """
    Calculate the current speed of a planet.

    Returns:
        Tuple of (speed in degrees/day, is_retrograde)
    """
    if not SWISSEPH_AVAILABLE:
        return (PLANET_AVERAGE_SPEED.get(planet_name, 1.0), False)

    planet_ids = {
        'Sun': swe.SUN,
        'Moon': swe.MOON,
        'Mars': swe.MARS,
        'Mercury': swe.MERCURY,
        'Jupiter': swe.JUPITER,
        'Venus': swe.VENUS,
        'Saturn': swe.SATURN,
    }

    if planet_name in ['Rahu', 'Ketu']:
        # Rahu/Ketu always retrograde
        return (abs(PLANET_AVERAGE_SPEED.get(planet_name, 0.053)), True)

    if planet_name not in planet_ids:
        return (PLANET_AVERAGE_SPEED.get(planet_name, 1.0), False)

    try:
        # Get position with speed flag
        result = swe.calc_ut(jd, planet_ids[planet_name], swe.FLG_SPEED)
        speed = result[0][3]  # Speed in longitude (degrees/day)
        is_retrograde = speed < 0
        return (abs(speed), is_retrograde)
    except Exception:
        return (PLANET_AVERAGE_SPEED.get(planet_name, 1.0), False)


def get_planet_gati(planet_name: str, speed: float, is_retrograde: bool) -> str:
    """
    Determine the gati (speed category) of a planet based on its current speed.

    Args:
        planet_name: Name of the planet
        speed: Current speed in degrees/day (absolute value)
        is_retrograde: Whether planet is retrograde

    Returns:
        Gati category string
    """
    if is_retrograde:
        return 'vakri'

    avg_speed = PLANET_AVERAGE_SPEED.get(planet_name, 1.0)
    if avg_speed == 0:
        avg_speed = 0.001  # Prevent division by zero

    speed_ratio = speed / avg_speed

    if speed_ratio < GATI_THRESHOLDS['ati_manda']:
        return 'ati_manda'
    elif speed_ratio < GATI_THRESHOLDS['manda']:
        return 'manda'
    elif speed_ratio < GATI_THRESHOLDS['sama_low']:
        return 'manda'
    elif speed_ratio <= GATI_THRESHOLDS['sama_high']:
        return 'sama'
    elif speed_ratio <= GATI_THRESHOLDS['sheeghra']:
        return 'sheeghra'
    else:
        return 'ati_chari'


def get_extended_vedha_targets(nakshatra_idx: int, gati: str) -> List[int]:
    """
    Get additional vedha targets based on planet's gati.
    Slow/retrograde planets affect adjacent nakshatras as well.

    Args:
        nakshatra_idx: Primary nakshatra index
        gati: Planet's gati category

    Returns:
        List of additional nakshatra indices affected
    """
    gati_effects = GATI_EFFECTS.get(gati, GATI_EFFECTS['sama'])
    vedha_points = gati_effects['vedha_points']

    if vedha_points <= 1:
        return []

    # Get neighbors for extended vedha
    neighbors = EXTENDED_VEDHA_NEIGHBORS.get(nakshatra_idx, [])

    if vedha_points >= 3:
        # Very slow - return all neighbors
        return neighbors
    elif vedha_points >= 2:
        # Slow - return first neighbor only
        return neighbors[:1] if neighbors else []

    return []


# Vedha patterns - which nakshatras cause vedha to which
# Key: source nakshatra index, Value: list of target nakshatra indices that receive vedha
NAKSHATRA_VEDHA = {
    # Ashwini (0) causes vedha to Jyeshtha (17)
    0: [17],
    # Bharani (1) causes vedha to Anuradha (16)
    1: [16],
    # Krittika (2) causes vedha to Vishakha (15)
    2: [15],
    # Rohini (3) causes vedha to Swati (14)
    3: [14],
    # Mrigashira (4) causes vedha to Chitra (13)
    4: [13],
    # Ardra (5) causes vedha to Hasta (12)
    5: [12],
    # Punarvasu (6) causes vedha to Uttara Phalguni (11)
    6: [11],
    # Pushya (7) causes vedha to Purva Phalguni (10)
    7: [10],
    # Ashlesha (8) causes vedha to Magha (9)
    8: [9],
    # Magha (9) causes vedha to Ashlesha (8)
    9: [8],
    # P. Phalguni (10) causes vedha to Pushya (7)
    10: [7],
    # U. Phalguni (11) causes vedha to Punarvasu (6)
    11: [6],
    # Hasta (12) causes vedha to Ardra (5)
    12: [5],
    # Chitra (13) causes vedha to Mrigashira (4)
    13: [4],
    # Swati (14) causes vedha to Rohini (3)
    14: [3],
    # Vishakha (15) causes vedha to Krittika (2)
    15: [2],
    # Anuradha (16) causes vedha to Bharani (1)
    16: [1],
    # Jyeshtha (17) causes vedha to Ashwini (0)
    17: [0],
    # Mula (18) causes vedha to Revati (26)
    18: [26],
    # P. Ashadha (19) causes vedha to U. Bhadrapada (25)
    19: [25],
    # U. Ashadha (20) causes vedha to P. Bhadrapada (24)
    20: [24],
    # Shravana (21) causes vedha to Shatabhisha (23)
    21: [23],
    # Dhanishta (22) - no vedha (corner)
    22: [],
    # Shatabhisha (23) causes vedha to Shravana (21)
    23: [21],
    # P. Bhadrapada (24) causes vedha to U. Ashadha (20)
    24: [20],
    # U. Bhadrapada (25) causes vedha to P. Ashadha (19)
    25: [19],
    # Revati (26) causes vedha to Mula (18)
    26: [18],
}

# =====================================================
# BTC GENESIS BLOCK BIRTH DATA (January 3, 2009, 18:15:05 UTC)
# =====================================================
# Based on Swiss Ephemeris calculations with Lahiri ayanamsa

# 1. JANMA NAKSHATRA (Birth Nakshatra) - Moon position at genesis
#    Moon was at 340.57° sidereal = Uttara Bhadrapada nakshatra
BTC_BIRTH_NAKSHATRA = 'Uttara Bhadrapada'
BTC_BIRTH_NAKSHATRA_IDX = 25  # Corrected from Revati

# Sun's nakshatra at genesis (Sun was at 259.53° = Purva Ashadha)
BTC_SUN_NAKSHATRA = 'Purva Ashadha'
BTC_SUN_NAKSHATRA_IDX = 19

# 2. JANMA TITHI (Birth Lunar Day) - Based on Sun-Moon elongation
#    Elongation was 81.04°, Tithi = (81.04/12) + 1 = 7 (Saptami)
BTC_BIRTH_TITHI = 7  # Saptami (7th tithi, Shukla Paksha)
BTC_BIRTH_TITHI_NAME = 'Saptami'

# 3. JANMA RASHI (Birth Moon Sign) - Moon was in Pisces
BTC_BIRTH_RASHI = 'Pisces'
BTC_BIRTH_RASHI_IDX = 11  # Pisces = 11 (0-indexed)

# 4. JANMA AKSHARA (Birth Consonant) - First consonant of "Bitcoin" = 'B'
#    In Sanskrit/Devanagari, 'B' corresponds to the 'Ba' varga
BTC_BIRTH_AKSHARA = 'B'
BTC_BIRTH_AKSHARA_GROUP = 'Pa-varga'  # B is in Pa-Pha-Ba-Bha-Ma group

# 5. JANMA SWARA (Birth Vowel) - First vowel in "Bitcoin" = 'i'
BTC_BIRTH_SWARA = 'I'
BTC_BIRTH_SWARA_GROUP = 'I-varga'  # Short 'i' vowel

# =====================================================
# SBC VEDHA MAPPINGS FOR TITHI, RASHI, AKSHARA, SWARA
# =====================================================

# Tithi positions in SBC grid (which nakshatras cause vedha to which tithi)
# Tithis are placed in specific cells of the SBC grid
TITHI_VEDHA = {
    # Tithi index: list of nakshatra indices that cause vedha
    1: [6],    # Pratipada vedha from Punarvasu
    2: [7],    # Dvitiya vedha from Pushya
    3: [8],    # Tritiya vedha from Ashlesha
    4: [5],    # Chaturthi vedha from Ardra
    5: [14],   # Panchami vedha from Swati
    6: [16],   # Shashthi vedha from Anuradha
    7: [17],   # Saptami vedha from Jyeshtha (BTC's birth tithi)
    8: [18],   # Ashtami vedha from Mula
    9: [19],   # Navami vedha from Purva Ashadha
    10: [20],  # Dashami vedha from Uttara Ashadha
    11: [21],  # Ekadashi vedha from Shravana
    12: [23],  # Dvadashi vedha from Shatabhisha
    13: [24],  # Trayodashi vedha from Purva Bhadrapada
    14: [0],   # Chaturdashi vedha from Ashwini
    15: [1],   # Purnima/Amavasya vedha from Bharani
}

# Rashi (sign) vedha mapping - based on SBC grid positions
# Which nakshatras cause vedha to which rashi
RASHI_VEDHA = {
    # Rashi index: list of nakshatra indices that cause vedha
    0: [17],   # Aries vedha from Jyeshtha
    1: [16],   # Taurus vedha from Anuradha
    2: [15],   # Gemini vedha from Vishakha
    3: [14],   # Cancer vedha from Swati
    4: [13],   # Leo vedha from Chitra
    5: [12],   # Virgo vedha from Hasta
    6: [11],   # Libra vedha from Uttara Phalguni
    7: [10],   # Scorpio vedha from Purva Phalguni
    8: [9],    # Sagittarius vedha from Magha
    9: [8],    # Capricorn vedha from Ashlesha
    10: [22],  # Aquarius vedha from Dhanishta
    11: [18],  # Pisces vedha from Mula (BTC's birth rashi)
}

# Akshara (consonant) vedha mapping based on SBC grid
# Sanskrit consonant groups and their vedha relationships
AKSHARA_VEDHA = {
    # Consonant group: list of nakshatra indices that cause vedha
    'Ka-varga': [2, 3, 4],      # Ka, Kha, Ga, Gha, Nga
    'Cha-varga': [5, 6, 7],     # Cha, Chha, Ja, Jha, Nya
    'Ta-varga': [8, 9, 10],     # Ta, Tha, Da, Dha, Na (retroflex)
    'Ta-varga2': [11, 12, 13],  # Ta, Tha, Da, Dha, Na (dental)
    'Pa-varga': [14, 15, 16],   # Pa, Pha, Ba, Bha, Ma (BTC = B)
    'Ya-varga': [17, 18, 19],   # Ya, Ra, La, Va
    'Sha-varga': [20, 21, 22],  # Sha, Sha, Sa, Ha
}

# Swara (vowel) vedha mapping based on SBC grid
SWARA_VEDHA = {
    # Vowel: list of nakshatra indices that cause vedha
    'A': [0, 26],    # Short 'a'
    'Aa': [1, 25],   # Long 'aa'
    'I': [4, 13],    # Short 'i' (BTC's birth swara)
    'Ii': [5, 12],   # Long 'ii'
    'U': [3, 14],    # Short 'u'
    'Uu': [6, 11],   # Long 'uu'
    'Ri': [2, 15],   # Vocalic 'ri'
    'E': [7, 10],    # Short 'e'
    'Ai': [8, 9],    # Diphthong 'ai'
    'O': [23, 24],   # Short 'o'
    'Au': [21, 22],  # Diphthong 'au'
}

# Planets and their nature (benefic/malefic)
PLANET_NATURE = {
    'Sun': 'malefic',
    'Moon': 'benefic',  # Waxing moon is benefic
    'Mars': 'malefic',
    'Mercury': 'neutral',  # Depends on association
    'Jupiter': 'benefic',
    'Venus': 'benefic',
    'Saturn': 'malefic',
    'Rahu': 'malefic',
    'Ketu': 'malefic',
}


def get_nakshatra_from_longitude(longitude: float) -> Tuple[str, int, float]:
    """
    Get nakshatra name, index, and degree within nakshatra from sidereal longitude.
    Each nakshatra spans 13°20' (13.333... degrees)
    """
    nakshatra_span = 360.0 / 27.0  # 13.333... degrees
    nakshatra_idx = int(longitude / nakshatra_span) % 27
    degree_in_nakshatra = longitude % nakshatra_span
    return NAKSHATRA_NAMES[nakshatra_idx], nakshatra_idx, degree_in_nakshatra


def get_tithi(sun_longitude: float, moon_longitude: float) -> Tuple[str, int]:
    """
    Calculate tithi (lunar day) from Sun and Moon positions.
    Tithi is based on Moon's elongation from Sun.
    """
    elongation = (moon_longitude - sun_longitude) % 360
    tithi_idx = int(elongation / 12) + 1  # 1-30

    tithi_names = [
        'Pratipada', 'Dvitiya', 'Tritiya', 'Chaturthi', 'Panchami',
        'Shashthi', 'Saptami', 'Ashtami', 'Navami', 'Dashami',
        'Ekadashi', 'Dvadashi', 'Trayodashi', 'Chaturdashi', 'Purnima/Amavasya'
    ]

    # Adjust for Krishna/Shukla paksha
    if tithi_idx > 15:
        tithi_idx -= 15

    return tithi_names[tithi_idx - 1] if tithi_idx <= 15 else 'Purnima', tithi_idx


def get_vara(date: datetime) -> Tuple[str, int]:
    """Get weekday (Vara) from date."""
    vara_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    vara_idx = date.weekday()  # Monday = 0
    # Convert to Sunday = 0
    vara_idx = (vara_idx + 1) % 7
    return vara_names[vara_idx], vara_idx


def check_tithi_vedha(planet_nakshatra_idx: int, planet_name: str, tithi: int) -> Dict:
    """Check if planet causes vedha to a tithi."""
    vedha_sources = TITHI_VEDHA.get(tithi, [])
    if planet_nakshatra_idx in vedha_sources:
        planet_nature = PLANET_NATURE.get(planet_name, 'neutral')
        vedha_type = 'negative' if planet_nature == 'malefic' else 'positive'
        return {
            'planet': planet_name,
            'planet_nakshatra': NAKSHATRA_NAMES[planet_nakshatra_idx],
            'target_type': 'tithi',
            'target_name': f'Tithi {tithi} (Saptami)' if tithi == 7 else f'Tithi {tithi}',
            'vedha_type': vedha_type,
            'planet_nature': planet_nature,
            'significance': 'relationships, family dynamics',
            'description': f"{planet_name} in {NAKSHATRA_NAMES[planet_nakshatra_idx]} causes {vedha_type} vedha to Janma Tithi"
        }
    return None


def check_rashi_vedha(planet_nakshatra_idx: int, planet_name: str, rashi_idx: int, rashi_name: str) -> Dict:
    """Check if planet causes vedha to a rashi (sign)."""
    vedha_sources = RASHI_VEDHA.get(rashi_idx, [])
    if planet_nakshatra_idx in vedha_sources:
        planet_nature = PLANET_NATURE.get(planet_name, 'neutral')
        vedha_type = 'negative' if planet_nature == 'malefic' else 'positive'
        return {
            'planet': planet_name,
            'planet_nakshatra': NAKSHATRA_NAMES[planet_nakshatra_idx],
            'target_type': 'rashi',
            'target_name': f'Janma Rashi ({rashi_name})',
            'vedha_type': vedha_type,
            'planet_nature': planet_nature,
            'significance': 'events in life areas ruled by this sign',
            'description': f"{planet_name} in {NAKSHATRA_NAMES[planet_nakshatra_idx]} causes {vedha_type} vedha to Janma Rashi ({rashi_name})"
        }
    return None


def check_akshara_vedha(planet_nakshatra_idx: int, planet_name: str, akshara_group: str) -> Dict:
    """Check if planet causes vedha to birth consonant group."""
    vedha_sources = AKSHARA_VEDHA.get(akshara_group, [])
    if planet_nakshatra_idx in vedha_sources:
        planet_nature = PLANET_NATURE.get(planet_name, 'neutral')
        vedha_type = 'negative' if planet_nature == 'malefic' else 'positive'
        return {
            'planet': planet_name,
            'planet_nakshatra': NAKSHATRA_NAMES[planet_nakshatra_idx],
            'target_type': 'akshara',
            'target_name': f'Janma Akshara ({BTC_BIRTH_AKSHARA}, {akshara_group})',
            'vedha_type': vedha_type,
            'planet_nature': planet_nature,
            'significance': 'reputation, losses, physical body',
            'description': f"{planet_name} in {NAKSHATRA_NAMES[planet_nakshatra_idx]} causes {vedha_type} vedha to Janma Akshara"
        }
    return None


def check_swara_vedha(planet_nakshatra_idx: int, planet_name: str, swara: str) -> Dict:
    """Check if planet causes vedha to birth vowel."""
    vedha_sources = SWARA_VEDHA.get(swara, [])
    if planet_nakshatra_idx in vedha_sources:
        planet_nature = PLANET_NATURE.get(planet_name, 'neutral')
        vedha_type = 'negative' if planet_nature == 'malefic' else 'positive'
        return {
            'planet': planet_name,
            'planet_nakshatra': NAKSHATRA_NAMES[planet_nakshatra_idx],
            'target_type': 'swara',
            'target_name': f'Janma Swara ({swara})',
            'vedha_type': vedha_type,
            'planet_nature': planet_nature,
            'significance': 'life force (prana), health, vitality',
            'description': f"{planet_name} in {NAKSHATRA_NAMES[planet_nakshatra_idx]} causes {vedha_type} vedha to Janma Swara"
        }
    return None


def calculate_vedhas_for_position(planet_nakshatra_idx: int, planet_name: str,
                                   target_nakshatra_idx: int = BTC_BIRTH_NAKSHATRA_IDX,
                                   target_name: str = "BTC Birth") -> Dict:
    """
    Calculate if a planet's current nakshatra causes vedha to a target nakshatra.

    Args:
        planet_nakshatra_idx: Index of the planet's current nakshatra
        planet_name: Name of the planet
        target_nakshatra_idx: Index of the target nakshatra to check vedha on
        target_name: Description of the target (e.g., "BTC Birth", "Lagna", "Transit Moon")

    Returns dict with vedha details or None if no vedha.
    """
    vedha_targets = NAKSHATRA_VEDHA.get(planet_nakshatra_idx, [])

    if target_nakshatra_idx in vedha_targets:
        planet_nature = PLANET_NATURE.get(planet_name, 'neutral')
        vedha_type = 'negative' if planet_nature == 'malefic' else 'positive'

        return {
            'planet': planet_name,
            'planet_nakshatra': NAKSHATRA_NAMES[planet_nakshatra_idx],
            'target_nakshatra': NAKSHATRA_NAMES[target_nakshatra_idx],
            'target_name': target_name,
            'vedha_type': vedha_type,
            'planet_nature': planet_nature,
            'description': f"{planet_name} in {NAKSHATRA_NAMES[planet_nakshatra_idx]} causes {vedha_type} vedha to {target_name} ({NAKSHATRA_NAMES[target_nakshatra_idx]})"
        }

    return None


def get_lagna_nakshatra(jd: float, lat: float = 28.6139, lon: float = 77.2090) -> Tuple[str, int, float]:
    """
    Calculate Lagna (Ascendant) nakshatra for a given Julian Day.
    Default location is Delhi, India.
    """
    if not SWISSEPH_AVAILABLE:
        return None, -1, 0

    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Calculate houses (cusps[1] is the Ascendant)
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')  # Placidus

    # Get sidereal ascendant
    ayanamsa = swe.get_ayanamsa(jd)
    sidereal_asc = (cusps[0] - ayanamsa) % 360

    nakshatra_name, nakshatra_idx, degree = get_nakshatra_from_longitude(sidereal_asc)
    return nakshatra_name, nakshatra_idx, degree


def calculate_sbc_analysis(jd: float, lat: float = 28.6139, lon: float = 77.2090) -> Dict:
    """
    Calculate complete SBC analysis for a given Julian Day.
    Returns all planetary nakshatras, vedhas on all 5 SBC targets, and analysis.

    Checks vedhas on all 5 Janma factors:
    1. Janma Nakshatra (Birth Nakshatra) - mental state, judgment, worries
    2. Janma Tithi (Birth Lunar Day) - relationships, family dynamics
    3. Janma Rashi (Birth Moon Sign) - events in related life areas
    4. Janma Akshara (Birth Consonant) - reputation, losses, physical body
    5. Janma Swara (Birth Vowel) - life force (prana), health, vitality
    """
    if not SWISSEPH_AVAILABLE:
        return {'error': 'Swiss Ephemeris not available'}

    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Planet IDs
    planet_ids = {
        'Sun': swe.SUN,
        'Moon': swe.MOON,
        'Mars': swe.MARS,
        'Mercury': swe.MERCURY,
        'Jupiter': swe.JUPITER,
        'Venus': swe.VENUS,
        'Saturn': swe.SATURN,
        'Rahu': swe.MEAN_NODE,
    }

    planetary_positions = {}

    # First pass: calculate all planetary positions with speed/gati
    for planet_name, planet_id in planet_ids.items():
        # Get position with speed
        result = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL | swe.FLG_SPEED)
        longitude = result[0][0]
        speed = result[0][3]  # Speed in degrees/day
        is_retrograde = speed < 0

        nakshatra_name, nakshatra_idx, degree = get_nakshatra_from_longitude(longitude)

        # Calculate gati (speed category)
        gati = get_planet_gati(planet_name, abs(speed), is_retrograde)
        gati_info = GATI_EFFECTS.get(gati, GATI_EFFECTS['sama'])

        planetary_positions[planet_name] = {
            'longitude': round(longitude, 2),
            'nakshatra': nakshatra_name,
            'nakshatra_idx': nakshatra_idx,
            'degree_in_nakshatra': round(degree, 2),
            'pada': int(degree / 3.333333) + 1,  # 4 padas per nakshatra
            'speed': round(abs(speed), 4),
            'is_retrograde': is_retrograde,
            'gati': gati,
            'gati_name': gati_info['name'],
            'vedha_multiplier': gati_info['vedha_multiplier']
        }

    # Calculate Ketu (opposite to Rahu) - always retrograde like Rahu
    rahu_long = planetary_positions['Rahu']['longitude']
    rahu_speed = planetary_positions['Rahu']['speed']
    ketu_long = (rahu_long + 180) % 360
    ketu_nakshatra, ketu_idx, ketu_degree = get_nakshatra_from_longitude(ketu_long)
    ketu_gati = get_planet_gati('Ketu', rahu_speed, True)
    ketu_gati_info = GATI_EFFECTS.get(ketu_gati, GATI_EFFECTS['sama'])

    planetary_positions['Ketu'] = {
        'longitude': round(ketu_long, 2),
        'nakshatra': ketu_nakshatra,
        'nakshatra_idx': ketu_idx,
        'degree_in_nakshatra': round(ketu_degree, 2),
        'pada': int(ketu_degree / 3.333333) + 1,
        'speed': round(rahu_speed, 4),
        'is_retrograde': True,  # Ketu is always retrograde
        'gati': ketu_gati,
        'gati_name': ketu_gati_info['name'],
        'vedha_multiplier': ketu_gati_info['vedha_multiplier']
    }

    # Get current Lagna nakshatra
    lagna_nakshatra_name, lagna_nakshatra_idx, lagna_degree = get_lagna_nakshatra(jd, lat, lon)

    # Calculate current tithi
    sun_long = planetary_positions['Sun']['longitude']
    moon_long = planetary_positions['Moon']['longitude']
    current_tithi_name, current_tithi_idx = get_tithi(sun_long, moon_long)

    # Initialize vedha tracking for all 5 Janma targets
    vedha_results = {
        'janma_nakshatra': {
            'target': f'Janma Nakshatra ({BTC_BIRTH_NAKSHATRA})',
            'significance': 'mental state, judgment, worries, potential harm/gains',
            'vedhas': [],
            'positive': [],
            'negative': []
        },
        'janma_tithi': {
            'target': f'Janma Tithi ({BTC_BIRTH_TITHI_NAME})',
            'significance': 'relationships, family dynamics',
            'vedhas': [],
            'positive': [],
            'negative': []
        },
        'janma_rashi': {
            'target': f'Janma Rashi ({BTC_BIRTH_RASHI})',
            'significance': 'events in life areas ruled by this sign',
            'vedhas': [],
            'positive': [],
            'negative': []
        },
        'janma_akshara': {
            'target': f'Janma Akshara ({BTC_BIRTH_AKSHARA}, {BTC_BIRTH_AKSHARA_GROUP})',
            'significance': 'reputation, losses, physical body',
            'vedhas': [],
            'positive': [],
            'negative': []
        },
        'janma_swara': {
            'target': f'Janma Swara ({BTC_BIRTH_SWARA})',
            'significance': 'life force (prana), health, vitality',
            'vedhas': [],
            'positive': [],
            'negative': []
        }
    }

    # Check vedhas from each planet to each of the 5 targets
    all_planets = list(planet_ids.keys()) + ['Ketu']
    for planet_name in all_planets:
        planet_nakshatra_idx = planetary_positions[planet_name]['nakshatra_idx']

        # 1. Check Janma Nakshatra vedha
        nakshatra_vedha = calculate_vedhas_for_position(
            planet_nakshatra_idx,
            planet_name,
            BTC_BIRTH_NAKSHATRA_IDX,
            f'Janma Nakshatra ({BTC_BIRTH_NAKSHATRA})'
        )
        if nakshatra_vedha:
            nakshatra_vedha['significance'] = 'mental state, judgment'
            vedha_results['janma_nakshatra']['vedhas'].append(nakshatra_vedha)
            if nakshatra_vedha['vedha_type'] == 'positive':
                vedha_results['janma_nakshatra']['positive'].append(nakshatra_vedha)
            else:
                vedha_results['janma_nakshatra']['negative'].append(nakshatra_vedha)

        # 2. Check Janma Tithi vedha
        tithi_vedha = check_tithi_vedha(planet_nakshatra_idx, planet_name, BTC_BIRTH_TITHI)
        if tithi_vedha:
            vedha_results['janma_tithi']['vedhas'].append(tithi_vedha)
            if tithi_vedha['vedha_type'] == 'positive':
                vedha_results['janma_tithi']['positive'].append(tithi_vedha)
            else:
                vedha_results['janma_tithi']['negative'].append(tithi_vedha)

        # 3. Check Janma Rashi vedha
        rashi_vedha = check_rashi_vedha(planet_nakshatra_idx, planet_name, BTC_BIRTH_RASHI_IDX, BTC_BIRTH_RASHI)
        if rashi_vedha:
            vedha_results['janma_rashi']['vedhas'].append(rashi_vedha)
            if rashi_vedha['vedha_type'] == 'positive':
                vedha_results['janma_rashi']['positive'].append(rashi_vedha)
            else:
                vedha_results['janma_rashi']['negative'].append(rashi_vedha)

        # 4. Check Janma Akshara vedha
        akshara_vedha = check_akshara_vedha(planet_nakshatra_idx, planet_name, BTC_BIRTH_AKSHARA_GROUP)
        if akshara_vedha:
            vedha_results['janma_akshara']['vedhas'].append(akshara_vedha)
            if akshara_vedha['vedha_type'] == 'positive':
                vedha_results['janma_akshara']['positive'].append(akshara_vedha)
            else:
                vedha_results['janma_akshara']['negative'].append(akshara_vedha)

        # 5. Check Janma Swara vedha
        swara_vedha = check_swara_vedha(planet_nakshatra_idx, planet_name, BTC_BIRTH_SWARA)
        if swara_vedha:
            vedha_results['janma_swara']['vedhas'].append(swara_vedha)
            if swara_vedha['vedha_type'] == 'positive':
                vedha_results['janma_swara']['positive'].append(swara_vedha)
            else:
                vedha_results['janma_swara']['negative'].append(swara_vedha)

    # Calculate scores for each target
    for target_key, target_info in vedha_results.items():
        target_info['positive_count'] = len(target_info['positive'])
        target_info['negative_count'] = len(target_info['negative'])
        target_info['net_score'] = target_info['positive_count'] - target_info['negative_count']

    # Calculate weighted combined score
    # Weights based on importance in SBC tradition
    weights = {
        'janma_nakshatra': 0.30,  # Most important - mental state
        'janma_tithi': 0.15,      # Relationships
        'janma_rashi': 0.25,      # Life events
        'janma_akshara': 0.15,    # Reputation/body
        'janma_swara': 0.15       # Health/vitality
    }

    combined_score = sum(
        vedha_results[k]['net_score'] * weights[k]
        for k in weights.keys()
    )

    # Total counts across all targets
    total_positive = sum(t['positive_count'] for t in vedha_results.values())
    total_negative = sum(t['negative_count'] for t in vedha_results.values())
    total_net = total_positive - total_negative

    # Determine overall signal based on combined score
    if combined_score >= 1.0:
        vedha_signal = 'STRONG_POSITIVE'
        signal_description = 'Strong benefic vedhas across all 5 Janma factors - very favorable for BTC'
    elif combined_score >= 0.3:
        vedha_signal = 'MILD_POSITIVE'
        signal_description = 'Net benefic influence across Janma factors - cautiously bullish'
    elif combined_score > -0.3:
        vedha_signal = 'NEUTRAL'
        signal_description = 'Balanced vedhas on Janma factors - no clear directional bias'
    elif combined_score > -1.0:
        vedha_signal = 'MILD_NEGATIVE'
        signal_description = 'Net malefic influence on Janma factors - cautiously bearish'
    else:
        vedha_signal = 'STRONG_NEGATIVE'
        signal_description = 'Strong malefic vedhas across Janma factors - unfavorable for BTC'

    # Build all vedhas list (combined from all targets)
    all_vedhas = []
    for target_info in vedha_results.values():
        all_vedhas.extend(target_info['vedhas'])

    return {
        'planetary_positions': planetary_positions,
        'lagna_nakshatra': {
            'name': lagna_nakshatra_name,
            'index': lagna_nakshatra_idx,
            'degree': round(lagna_degree, 2) if lagna_degree else 0
        },
        'btc_birth_data': {
            'nakshatra': BTC_BIRTH_NAKSHATRA,
            'nakshatra_idx': BTC_BIRTH_NAKSHATRA_IDX,
            'tithi': BTC_BIRTH_TITHI,
            'tithi_name': BTC_BIRTH_TITHI_NAME,
            'rashi': BTC_BIRTH_RASHI,
            'rashi_idx': BTC_BIRTH_RASHI_IDX,
            'akshara': BTC_BIRTH_AKSHARA,
            'akshara_group': BTC_BIRTH_AKSHARA_GROUP,
            'swara': BTC_BIRTH_SWARA
        },
        'vedhas_by_janma': {
            'janma_nakshatra': {
                'target': vedha_results['janma_nakshatra']['target'],
                'significance': vedha_results['janma_nakshatra']['significance'],
                'vedhas': vedha_results['janma_nakshatra']['vedhas'],
                'positive_count': vedha_results['janma_nakshatra']['positive_count'],
                'negative_count': vedha_results['janma_nakshatra']['negative_count'],
                'net_score': vedha_results['janma_nakshatra']['net_score'],
                'weight': weights['janma_nakshatra']
            },
            'janma_tithi': {
                'target': vedha_results['janma_tithi']['target'],
                'significance': vedha_results['janma_tithi']['significance'],
                'vedhas': vedha_results['janma_tithi']['vedhas'],
                'positive_count': vedha_results['janma_tithi']['positive_count'],
                'negative_count': vedha_results['janma_tithi']['negative_count'],
                'net_score': vedha_results['janma_tithi']['net_score'],
                'weight': weights['janma_tithi']
            },
            'janma_rashi': {
                'target': vedha_results['janma_rashi']['target'],
                'significance': vedha_results['janma_rashi']['significance'],
                'vedhas': vedha_results['janma_rashi']['vedhas'],
                'positive_count': vedha_results['janma_rashi']['positive_count'],
                'negative_count': vedha_results['janma_rashi']['negative_count'],
                'net_score': vedha_results['janma_rashi']['net_score'],
                'weight': weights['janma_rashi']
            },
            'janma_akshara': {
                'target': vedha_results['janma_akshara']['target'],
                'significance': vedha_results['janma_akshara']['significance'],
                'vedhas': vedha_results['janma_akshara']['vedhas'],
                'positive_count': vedha_results['janma_akshara']['positive_count'],
                'negative_count': vedha_results['janma_akshara']['negative_count'],
                'net_score': vedha_results['janma_akshara']['net_score'],
                'weight': weights['janma_akshara']
            },
            'janma_swara': {
                'target': vedha_results['janma_swara']['target'],
                'significance': vedha_results['janma_swara']['significance'],
                'vedhas': vedha_results['janma_swara']['vedhas'],
                'positive_count': vedha_results['janma_swara']['positive_count'],
                'negative_count': vedha_results['janma_swara']['negative_count'],
                'net_score': vedha_results['janma_swara']['net_score'],
                'weight': weights['janma_swara']
            }
        },
        'vedhas_on_btc': vedha_results['janma_nakshatra']['vedhas'],  # Backward compatibility
        'all_vedhas': all_vedhas,
        'vedhas_summary': {
            'positive_count': total_positive,
            'negative_count': total_negative,
            'net_score': total_net,
            'combined_weighted_score': round(combined_score, 2),
            'signal': vedha_signal,
            'description': signal_description,
            'by_janma_factor': {
                'nakshatra_score': vedha_results['janma_nakshatra']['net_score'],
                'tithi_score': vedha_results['janma_tithi']['net_score'],
                'rashi_score': vedha_results['janma_rashi']['net_score'],
                'akshara_score': vedha_results['janma_akshara']['net_score'],
                'swara_score': vedha_results['janma_swara']['net_score']
            }
        },
        'tithi': {
            'name': current_tithi_name,
            'index': current_tithi_idx
        },
        'btc_birth_nakshatra': BTC_BIRTH_NAKSHATRA,
        'btc_sun_nakshatra': BTC_SUN_NAKSHATRA
    }


def get_current_sbc_analysis() -> Dict:
    """Get SBC analysis for current time."""
    if not SWISSEPH_AVAILABLE:
        return {'error': 'Swiss Ephemeris not available'}

    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    utc_now = now_ny.astimezone(pytz.UTC)

    jd = swe.julday(utc_now.year, utc_now.month, utc_now.day,
                    utc_now.hour + utc_now.minute/60.0)

    analysis = calculate_sbc_analysis(jd)

    # Add time info
    vara_name, vara_idx = get_vara(now_ny)
    analysis['time'] = now_ny.strftime('%Y-%m-%d %H:%M %Z')
    analysis['vara'] = {
        'name': vara_name,
        'index': vara_idx
    }
    analysis['julian_day'] = round(jd, 4)

    return analysis


def analyze_historical_vedhas() -> Dict:
    """
    Analyze historical correlation between all 5 Janma factor vedhas and BTC price movements.
    Uses the FULL 5-year dataset (3,652 sessions).
    Tracks each factor separately: Nakshatra, Tithi, Rashi, Akshara, Swara.
    """
    if not SWISSEPH_AVAILABLE:
        return {'error': 'Swiss Ephemeris not available'}

    data_file = Path(__file__).parent.parent / 'btc_vedic_planetary_5years.csv'
    if not data_file.exists():
        return {'error': 'Historical data file not found'}

    # Load historical data - FULL DATASET
    sessions = []
    with open(data_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('PositiveOrNegative') in ['Positive', 'Negative']:
                sessions.append(row)

    # Track stats for EACH of the 5 Janma factors separately
    factor_stats = {
        'nakshatra': defaultdict(lambda: {'total': 0, 'btc_positive': 0}),
        'tithi': defaultdict(lambda: {'total': 0, 'btc_positive': 0}),
        'rashi': defaultdict(lambda: {'total': 0, 'btc_positive': 0}),
        'akshara': defaultdict(lambda: {'total': 0, 'btc_positive': 0}),
        'swara': defaultdict(lambda: {'total': 0, 'btc_positive': 0}),
    }

    # Overall signal tracking
    overall_results = {
        'strong_positive': {'total': 0, 'btc_positive': 0},
        'mild_positive': {'total': 0, 'btc_positive': 0},
        'neutral': {'total': 0, 'btc_positive': 0},
        'mild_negative': {'total': 0, 'btc_positive': 0},
        'strong_negative': {'total': 0, 'btc_positive': 0},
        'by_weighted_score': defaultdict(lambda: {'total': 0, 'btc_positive': 0})
    }

    ny_tz = pytz.timezone('America/New_York')

    for session in sessions:
        try:
            date_str = session.get('Date', '')
            session_name = session.get('SessionName', '')

            if not date_str:
                continue

            dt = datetime.strptime(date_str, '%Y-%m-%d')

            if session_name == 'ODR':
                dt = dt.replace(hour=0, minute=0)
            else:  # RDR
                dt = dt.replace(hour=9, minute=30)

            dt = ny_tz.localize(dt)
            utc_dt = dt.astimezone(pytz.UTC)

            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                           utc_dt.hour + utc_dt.minute/60.0)

            # Get full SBC analysis with all 5 factors
            sbc = calculate_sbc_analysis(jd)

            vedha_summary = sbc.get('vedhas_summary', {})
            signal = vedha_summary.get('signal', 'NEUTRAL')
            weighted_score = round(vedha_summary.get('combined_weighted_score', 0), 1)

            btc_positive = session.get('PositiveOrNegative') == 'Positive'

            # Track each factor's net score from vedhas_by_janma
            vedhas_by_janma = sbc.get('vedhas_by_janma', {})
            # Map to short names
            factor_key_map = {
                'nakshatra': 'janma_nakshatra',
                'tithi': 'janma_tithi',
                'rashi': 'janma_rashi',
                'akshara': 'janma_akshara',
                'swara': 'janma_swara'
            }
            for factor, janma_key in factor_key_map.items():
                factor_data = vedhas_by_janma.get(janma_key, {})
                net = factor_data.get('net_score', 0)
                # Bucket: positive (+1 or more), neutral (0), negative (-1 or less)
                if net > 0:
                    bucket = 'positive'
                elif net < 0:
                    bucket = 'negative'
                else:
                    bucket = 'neutral'
                factor_stats[factor][bucket]['total'] += 1
                if btc_positive:
                    factor_stats[factor][bucket]['btc_positive'] += 1

            # Track overall signal
            if 'STRONG_POSITIVE' in signal:
                overall_results['strong_positive']['total'] += 1
                if btc_positive:
                    overall_results['strong_positive']['btc_positive'] += 1
            elif 'MILD_POSITIVE' in signal:
                overall_results['mild_positive']['total'] += 1
                if btc_positive:
                    overall_results['mild_positive']['btc_positive'] += 1
            elif 'MILD_NEGATIVE' in signal:
                overall_results['mild_negative']['total'] += 1
                if btc_positive:
                    overall_results['mild_negative']['btc_positive'] += 1
            elif 'STRONG_NEGATIVE' in signal:
                overall_results['strong_negative']['total'] += 1
                if btc_positive:
                    overall_results['strong_negative']['btc_positive'] += 1
            else:
                overall_results['neutral']['total'] += 1
                if btc_positive:
                    overall_results['neutral']['btc_positive'] += 1

            # Track by weighted score buckets
            score_bucket = int(weighted_score * 10) / 10  # Round to 0.1
            overall_results['by_weighted_score'][score_bucket]['total'] += 1
            if btc_positive:
                overall_results['by_weighted_score'][score_bucket]['btc_positive'] += 1

        except Exception as e:
            continue

    # Calculate win rates for each factor
    factor_summary = {}
    for factor, buckets in factor_stats.items():
        factor_summary[factor] = {}
        for bucket, values in buckets.items():
            if values['total'] > 0:
                factor_summary[factor][bucket] = {
                    'total': values['total'],
                    'btc_positive': values['btc_positive'],
                    'win_rate': round(values['btc_positive'] / values['total'] * 100, 2)
                }
            else:
                factor_summary[factor][bucket] = {'total': 0, 'btc_positive': 0, 'win_rate': 50.0}

    # Calculate overall signal win rates
    overall_summary = {}
    for signal_type, values in overall_results.items():
        if signal_type == 'by_weighted_score':
            overall_summary['by_weighted_score'] = {}
            for score, data in values.items():
                if data['total'] > 0:
                    overall_summary['by_weighted_score'][score] = {
                        'total': data['total'],
                        'btc_positive': data['btc_positive'],
                        'win_rate': round(data['btc_positive'] / data['total'] * 100, 2)
                    }
        else:
            if values['total'] > 0:
                overall_summary[signal_type] = {
                    'total': values['total'],
                    'btc_positive': values['btc_positive'],
                    'win_rate': round(values['btc_positive'] / values['total'] * 100, 2)
                }
            else:
                overall_summary[signal_type] = {'total': 0, 'btc_positive': 0, 'win_rate': 50.0}

    return {
        'by_factor': factor_summary,
        'overall': overall_summary,
        'total_sessions': len(sessions),
        'methodology': f'BTC Genesis Block (Jan 3, 2009): Nakshatra={BTC_BIRTH_NAKSHATRA}, Tithi={BTC_BIRTH_TITHI_NAME}, Rashi={BTC_BIRTH_RASHI}, Akshara={BTC_BIRTH_AKSHARA}, Swara={BTC_BIRTH_SWARA}',
        'weights': 'Nakshatra 30%, Rashi 25%, Tithi 15%, Akshara 15%, Swara 15%'
    }


def generate_sbc_csv(days: int = 365) -> str:
    """
    Generate a CSV file with SBC vedha analysis for each day.
    """
    if not SWISSEPH_AVAILABLE:
        return 'Error: Swiss Ephemeris not available'

    output_file = Path(__file__).parent.parent / 'btc_sbc_vedha_analysis.csv'
    ny_tz = pytz.timezone('America/New_York')

    rows = []
    end_date = datetime.now(ny_tz)
    start_date = end_date - timedelta(days=days)

    current = start_date
    while current <= end_date:
        for session_name, hour, minute in [('ODR', 0, 0), ('RDR', 9, 30)]:
            dt = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
            utc_dt = dt.astimezone(pytz.UTC)

            jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                           utc_dt.hour + utc_dt.minute/60.0)

            sbc = calculate_sbc_analysis(jd)
            vara_name, _ = get_vara(dt)

            vedha_summary = sbc.get('vedhas_summary', {})

            row = {
                'Date': current.strftime('%Y-%m-%d'),
                'SessionName': session_name,
                'Vara': vara_name,
                'Tithi': sbc.get('tithi', {}).get('name', ''),
                'PositiveVedhas': vedha_summary.get('positive_count', 0),
                'NegativeVedhas': vedha_summary.get('negative_count', 0),
                'NetVedhaScore': vedha_summary.get('net_score', 0),
                'VedhaSignal': vedha_summary.get('signal', ''),
            }

            # Add planetary nakshatras
            for planet in ['Sun', 'Moon', 'Mars', 'Mercury', 'Jupiter', 'Venus', 'Saturn', 'Rahu', 'Ketu']:
                pos = sbc.get('planetary_positions', {}).get(planet, {})
                row[f'{planet}Nakshatra'] = pos.get('nakshatra', '')
                row[f'{planet}Pada'] = pos.get('pada', '')

            rows.append(row)

        current += timedelta(days=1)

    # Write CSV
    if rows:
        fieldnames = list(rows[0].keys())
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return str(output_file)

    return 'No data generated'


def get_full_sbc_data() -> Dict:
    """Get all SBC data for dashboard."""
    current = get_current_sbc_analysis()

    # Run historical analysis (this can be slow, so we might want to cache it)
    # For now, we'll provide a simplified version

    return {
        'current_analysis': current,
        'btc_birth_info': {
            'genesis_date': '2009-01-03 18:15:05 UTC',
            'moon_nakshatra': BTC_BIRTH_NAKSHATRA,
            'sun_nakshatra': BTC_SUN_NAKSHATRA,
            'explanation': 'BTC genesis block was mined when Moon was in Uttara Bhadrapada nakshatra (340.57°). This is used as BTC\'s "birth" nakshatra for vedha calculations.'
        },
        'vedha_explanation': {
            'what_is_vedha': 'Vedha is an obstruction or piercing influence in the Sarvato Bhadra Chakra. When a planet transits a nakshatra that has a vedha relationship with BTC\'s birth nakshatra, it creates an influence on BTC.',
            'positive_vedha': 'Benefic planets (Jupiter, Venus, Moon) causing vedha create positive influences.',
            'negative_vedha': 'Malefic planets (Saturn, Mars, Rahu, Ketu, Sun) causing vedha create negative influences.',
            'interpretation': 'Net positive vedhas suggest favorable conditions for BTC. Net negative vedhas suggest caution.'
        },
        'sbc_grid_info': {
            'description': 'The Sarvato Bhadra Chakra is a 9x9 grid containing 28 nakshatras arranged in a specific pattern. Vedhas are determined by line-of-sight relationships across the grid.',
            'nakshatras': NAKSHATRA_NAMES
        }
    }


# SBC 9x9 Grid Layout for visualization - Based on Traditional Sarvato Bhadra Chakra
# Each cell: (type, name, short_name)
# Types: 'N'=Nakshatra, 'T'=Tithi, 'V'=Vara (Day), 'S'=Swara/Akshara, 'R'=Rashi, 'C'=Center
# Reference: Traditional SBC with NW at top-left, rows A-I, columns 1-9
# This matches the correct traditional layout with Swaras in corners
SBC_VISUAL_GRID = [
    # Row A (Row 0) - Top row: Swaras and Nakshatras
    # A1=ī, A2=Dhan, A3=Shata, A4=P.Bha, A5=U.Bha, A6=Reva, A7=Asvi, A8=Bhar, A9=a
    [('S', 'ī', 'ī'), ('N', 'Dhanishta', 'Dhan'), ('N', 'Shatabhisha', 'Shata'), ('N', 'P.Bhadrapada', 'P.Bha'),
     ('N', 'U.Bhadrapada', 'U.Bha'), ('N', 'Revati', 'Reva'), ('N', 'Ashwini', 'Asvi'), ('N', 'Bharani', 'Bhar'), ('S', 'a', 'a')],
    # Row B (Row 1) - Srav, Swaras, Krit
    # B1=Srav, B2=ṛ, B3=ga, B4=sa, B5=Aksh(da,tha,jha,ña), B6=ca, B7=la, B8=u, B9=Krit
    [('N', 'Shravana', 'Srav'), ('S', 'ṛ', 'ṛ'), ('S', 'ga', 'ga'), ('S', 'sa', 'sa'),
     ('S', 'Aksh', 'Aksh'), ('S', 'ca', 'ca'), ('S', 'la', 'la'), ('S', 'u', 'u'), ('N', 'Krittika', 'Krit')],
    # Row C (Row 2) - Abhi*, Aksh, Rashis, Aksh, Roh
    # C1=Abhi*, C2=kha, C3=ai, C4=Aq, C5=Pi, C6=Ar, C7=ḷ, C8=a, C9=Roh
    [('N', 'Abhijit', 'Abhi*'), ('S', 'kha', 'kha'), ('S', 'ai', 'ai'), ('R', 'Aquarius', 'Aq'),
     ('R', 'Pisces', 'Pi'), ('R', 'Aries', 'Ar'), ('S', 'ḷ', 'ḷ'), ('S', 'a', 'a'), ('N', 'Rohini', 'Roh')],
    # Row D (Row 3) - U.Asha, Aksh, Rashis with Rikta center, Aksh, Mrig
    # D1=U.Asha, D2=ja, D3=Cp, D4=aḥ, D5=Rikta (Fri), D6=o, D7=Ta, D8=va, D9=Mrig
    [('N', 'U.Ashadha', 'U.Asha'), ('S', 'ja', 'ja'), ('R', 'Capricorn', 'Cp'), ('S', 'aḥ', 'aḥ'),
     ('V', 'Rikta', 'Rikta'), ('S', 'o', 'o'), ('R', 'Taurus', 'Ta'), ('S', 'va', 'va'), ('N', 'Mrigashira', 'Mrig')],
    # Row E (Row 4) - P.Asha, Aksh group, Sg, Jaya, Purna, Nanda, Ge, Aksh group, Ardr
    # E1=P.Asha, E2=Aksh, E3=Sg, E4=Jaya (Thu), E5=Purna (Sat), E6=Nanda (Sun/Tue), E7=Ge, E8=Aksh, E9=Ardr
    [('N', 'P.Ashadha', 'P.Asha'), ('S', 'Aksh', 'Aksh'), ('R', 'Sagittarius', 'Sg'), ('V', 'Jaya', 'Jaya'),
     ('V', 'Purna', 'Purna'), ('V', 'Nanda', 'Nanda'), ('R', 'Gemini', 'Ge'), ('S', 'Aksh', 'Aksh'), ('N', 'Ardra', 'Ardr')],
    # Row F (Row 5) - Mula, Aksh, Rashis with Bhadra center, Aksh, Puna
    # F1=Mula, F2=ya, F3=Sc, F4=aṃ, F5=Bhadra (Mon/Wed), F6=au, F7=Ca, F8=ha, F9=Puna
    [('N', 'Mula', 'Mula'), ('S', 'ya', 'ya'), ('R', 'Scorpio', 'Sc'), ('S', 'aṃ', 'aṃ'),
     ('V', 'Bhadra', 'Bhadra'), ('S', 'au', 'au'), ('R', 'Cancer', 'Ca'), ('S', 'ha', 'ha'), ('N', 'Punarvasu', 'Puna')],
    # Row G (Row 6) - Jyes, Aksh, Rashis, Aksh, Push
    # G1=Jyes, G2=na, G3=e, G4=Li, G5=Vi, G6=Le, G7=lṝ, G8=ḍa, G9=Push
    [('N', 'Jyeshtha', 'Jyes'), ('S', 'na', 'na'), ('S', 'e', 'e'), ('R', 'Libra', 'Li'),
     ('R', 'Virgo', 'Vi'), ('R', 'Leo', 'Le'), ('S', 'lṝ', 'lṝ'), ('S', 'ḍa', 'ḍa'), ('N', 'Pushya', 'Push')],
    # Row H (Row 7) - Anu, Aksh, Swaras, Aksh, Ashl
    # H1=Anu, H2=ṛ, H3=ta, H4=ra, H5=Aksh(pa,ṣa,ṇa,ṭha), H6=ṭa, H7=ma, H8=ū, H9=Ashl
    [('N', 'Anuradha', 'Anu'), ('S', 'ṛ', 'ṛ'), ('S', 'ta', 'ta'), ('S', 'ra', 'ra'),
     ('S', 'Aksh', 'Aksh'), ('S', 'ṭa', 'ṭa'), ('S', 'ma', 'ma'), ('S', 'ū', 'ū'), ('N', 'Ashlesha', 'Ashl')],
    # Row I (Row 8) - Bottom row: Swaras and Nakshatras
    # I1=i, I2=Vish, I3=Swat, I4=Chit, I5=Hast, I6=U.Pha, I7=P.Pha, I8=Magh, I9=ā
    [('S', 'i', 'i'), ('N', 'Vishakha', 'Vish'), ('N', 'Swati', 'Swat'), ('N', 'Chitra', 'Chit'),
     ('N', 'Hasta', 'Hast'), ('N', 'U.Phalguni', 'U.Pha'), ('N', 'P.Phalguni', 'P.Pha'), ('N', 'Magha', 'Magh'), ('S', 'ā', 'ā')],
]

# Nakshatra to grid position mapping (row, col) - Based on Traditional SBC layout
# Row A=0, B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8
# Col 1=0, 2=1, 3=2, 4=3, 5=4, 6=5, 7=6, 8=7, 9=8
NAKSHATRA_POSITIONS = {
    # Row A (top): Dhan, Shata, P.Bha, U.Bha, Reva, Asvi, Bhar
    'Dhanishta': (0, 1), 'Shatabhisha': (0, 2), 'Purva Bhadrapada': (0, 3),
    'Uttara Bhadrapada': (0, 4), 'Revati': (0, 5), 'Ashwini': (0, 6), 'Bharani': (0, 7),
    # Row B: Srav, Krit
    'Shravana': (1, 0), 'Krittika': (1, 8),
    # Row C: Abhi*, Roh
    'Abhijit': (2, 0), 'Rohini': (2, 8),
    # Row D: U.Asha, Mrig
    'Uttara Ashadha': (3, 0), 'Mrigashira': (3, 8),
    # Row E: P.Asha, Ardr
    'Purva Ashadha': (4, 0), 'Ardra': (4, 8),
    # Row F: Mula, Puna
    'Mula': (5, 0), 'Punarvasu': (5, 8),
    # Row G: Jyes, Push
    'Jyeshtha': (6, 0), 'Pushya': (6, 8),
    # Row H: Anu, Ashl
    'Anuradha': (7, 0), 'Ashlesha': (7, 8),
    # Row I (bottom): Vish, Swat, Chit, Hast, U.Pha, P.Pha, Magh
    'Vishakha': (8, 1), 'Swati': (8, 2), 'Chitra': (8, 3),
    'Hasta': (8, 4), 'Uttara Phalguni': (8, 5), 'Purva Phalguni': (8, 6), 'Magha': (8, 7),
}

# Rashi (Sign) names
RASHI_NAMES = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
               'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']


def get_akshara_from_name(name: str) -> Tuple[str, str]:
    """Get the first consonant (Akshara) and vowel (Swara) from a name."""
    if not name:
        return ('', '')

    name = name.upper().strip()

    # Extract first consonant
    consonants = 'BCDFGHJKLMNPQRSTVWXYZ'
    vowels = 'AEIOU'

    first_consonant = ''
    first_vowel = ''

    for char in name:
        if char in consonants and not first_consonant:
            first_consonant = char
        if char in vowels and not first_vowel:
            first_vowel = char

    # Map consonant to varga group
    akshara_group = ''
    if first_consonant in 'KG':
        akshara_group = 'Ka-varga'
    elif first_consonant in 'CJ':
        akshara_group = 'Cha-varga'
    elif first_consonant in 'TD':
        akshara_group = 'Ta-varga'
    elif first_consonant in 'TDN':
        akshara_group = 'Ta-varga2'
    elif first_consonant in 'PBM':
        akshara_group = 'Pa-varga'
    elif first_consonant in 'YRLV':
        akshara_group = 'Ya-varga'
    elif first_consonant in 'SH':
        akshara_group = 'Sha-varga'

    return (first_consonant, first_vowel, akshara_group)


def calculate_birth_chart(
    name: str,
    birth_date: str,  # YYYY-MM-DD
    birth_time: str,  # HH:MM
    latitude: float,
    longitude: float,
    timezone: str = 'UTC'
) -> Dict:
    """
    Calculate birth chart details including all 5 Janma factors.
    """
    if not SWISSEPH_AVAILABLE:
        return {'error': 'Swiss Ephemeris not available'}

    try:
        # Parse birth date and time
        birth_dt = datetime.strptime(f"{birth_date} {birth_time}", "%Y-%m-%d %H:%M")

        # Handle timezone
        tz = pytz.timezone(timezone) if timezone else pytz.UTC
        birth_dt = tz.localize(birth_dt)
        utc_dt = birth_dt.astimezone(pytz.UTC)

        # Calculate Julian Day
        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                       utc_dt.hour + utc_dt.minute/60.0 + utc_dt.second/3600.0)

        swe.set_sid_mode(swe.SIDM_LAHIRI)

        # Calculate planetary positions
        planet_ids = {
            'Sun': swe.SUN,
            'Moon': swe.MOON,
            'Mars': swe.MARS,
            'Mercury': swe.MERCURY,
            'Jupiter': swe.JUPITER,
            'Venus': swe.VENUS,
            'Saturn': swe.SATURN,
            'Rahu': swe.MEAN_NODE,
        }

        positions = {}
        for planet_name, planet_id in planet_ids.items():
            result = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL)
            lon = result[0][0]
            nakshatra_name, nakshatra_idx, degree = get_nakshatra_from_longitude(lon)
            rashi_idx = int(lon / 30)
            rashi_name = RASHI_NAMES[rashi_idx]

            positions[planet_name] = {
                'longitude': round(lon, 2),
                'nakshatra': nakshatra_name,
                'nakshatra_idx': nakshatra_idx,
                'pada': int(degree / 3.333333) + 1,
                'rashi': rashi_name,
                'rashi_idx': rashi_idx
            }

        # Add Ketu
        rahu_lon = positions['Rahu']['longitude']
        ketu_lon = (rahu_lon + 180) % 360
        ketu_nak, ketu_idx, ketu_deg = get_nakshatra_from_longitude(ketu_lon)
        ketu_rashi_idx = int(ketu_lon / 30)
        positions['Ketu'] = {
            'longitude': round(ketu_lon, 2),
            'nakshatra': ketu_nak,
            'nakshatra_idx': ketu_idx,
            'pada': int(ketu_deg / 3.333333) + 1,
            'rashi': RASHI_NAMES[ketu_rashi_idx],
            'rashi_idx': ketu_rashi_idx
        }

        # Calculate Lagna (Ascendant)
        lagna_deg = swe.houses_ex(jd, latitude, longitude, b'P', swe.FLG_SIDEREAL)[0][0]
        lagna_nak, lagna_idx, lagna_deg_in_nak = get_nakshatra_from_longitude(lagna_deg)
        lagna_rashi_idx = int(lagna_deg / 30)

        # Get Moon position for birth nakshatra
        moon = positions['Moon']
        birth_nakshatra = moon['nakshatra']
        birth_nakshatra_idx = moon['nakshatra_idx']

        # Calculate birth tithi
        sun_lon = positions['Sun']['longitude']
        moon_lon = positions['Moon']['longitude']
        tithi_name, tithi_idx = get_tithi(sun_lon, moon_lon)

        # Get birth rashi from Moon
        birth_rashi = moon['rashi']
        birth_rashi_idx = moon['rashi_idx']

        # Get akshara and swara from name
        akshara, swara, akshara_group = get_akshara_from_name(name)

        birth_data = {
            'name': name,
            'birth_datetime': birth_dt.strftime('%Y-%m-%d %H:%M %Z'),
            'location': {'latitude': latitude, 'longitude': longitude, 'timezone': timezone},
            'julian_day': round(jd, 4),
            'lagna': {
                'longitude': round(lagna_deg, 2),
                'nakshatra': lagna_nak,
                'nakshatra_idx': lagna_idx,
                'rashi': RASHI_NAMES[lagna_rashi_idx],
                'rashi_idx': lagna_rashi_idx
            },
            'planetary_positions': positions,
            'janma_factors': {
                'nakshatra': {
                    'name': birth_nakshatra,
                    'index': birth_nakshatra_idx,
                    'significance': 'Mental state, judgment, worries, potential harm/gains'
                },
                'tithi': {
                    'name': tithi_name,
                    'index': tithi_idx,
                    'significance': 'Relationships, family dynamics'
                },
                'rashi': {
                    'name': birth_rashi,
                    'index': birth_rashi_idx,
                    'significance': 'Events in life areas ruled by this sign'
                },
                'akshara': {
                    'letter': akshara,
                    'group': akshara_group,
                    'significance': 'Reputation, losses, physical body'
                },
                'swara': {
                    'vowel': swara,
                    'significance': 'Life force (prana), health, vitality'
                }
            }
        }

        return birth_data

    except Exception as e:
        return {'error': str(e)}


def calculate_custom_sbc_analysis(
    name: str,
    birth_date: str,  # YYYY-MM-DD
    birth_time: str,  # HH:MM
    latitude: float,
    longitude: float,
    analysis_date: str,  # YYYY-MM-DD
    analysis_time: str = '12:00',  # HH:MM
    timezone: str = 'UTC'
) -> Dict:
    """
    Calculate custom SBC analysis for a person/entity on a specific date.
    Returns the SBC grid with color-coded vedhas (red=negative, green=positive).
    """
    if not SWISSEPH_AVAILABLE:
        return {'error': 'Swiss Ephemeris not available'}

    try:
        # First, calculate birth chart to get the 5 Janma factors
        birth_data = calculate_birth_chart(name, birth_date, birth_time, latitude, longitude, timezone)
        if 'error' in birth_data:
            return birth_data

        janma = birth_data['janma_factors']

        # Parse analysis date/time
        tz = pytz.timezone(timezone) if timezone else pytz.UTC
        analysis_dt = datetime.strptime(f"{analysis_date} {analysis_time}", "%Y-%m-%d %H:%M")
        analysis_dt = tz.localize(analysis_dt)
        utc_dt = analysis_dt.astimezone(pytz.UTC)

        jd = swe.julday(utc_dt.year, utc_dt.month, utc_dt.day,
                       utc_dt.hour + utc_dt.minute/60.0)

        swe.set_sid_mode(swe.SIDM_LAHIRI)

        # Get transit planetary positions
        planet_ids = {
            'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
            'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER, 'Venus': swe.VENUS,
            'Saturn': swe.SATURN, 'Rahu': swe.MEAN_NODE,
        }

        transit_positions = {}
        for planet_name, planet_id in planet_ids.items():
            # Get position with speed for gati calculation
            result = swe.calc_ut(jd, planet_id, swe.FLG_SIDEREAL | swe.FLG_SPEED)
            lon = result[0][0]
            speed = result[0][3]  # Speed in degrees/day
            is_retrograde = speed < 0
            nak_name, nak_idx, degree = get_nakshatra_from_longitude(lon)
            rashi_idx = int(lon / 30)

            # Calculate gati (speed category)
            gati = get_planet_gati(planet_name, abs(speed), is_retrograde)
            gati_info = GATI_EFFECTS.get(gati, GATI_EFFECTS['sama'])

            transit_positions[planet_name] = {
                'longitude': round(lon, 2),
                'nakshatra': nak_name,
                'nakshatra_idx': nak_idx,
                'pada': int(degree / 3.333333) + 1,
                'rashi': RASHI_NAMES[rashi_idx],
                'speed': round(abs(speed), 4),
                'is_retrograde': is_retrograde,
                'gati': gati,
                'gati_name': gati_info['name'],
                'vedha_multiplier': gati_info['vedha_multiplier']
            }

        # Add Ketu (always retrograde)
        ketu_lon = (transit_positions['Rahu']['longitude'] + 180) % 360
        rahu_speed = transit_positions['Rahu']['speed']
        ketu_nak, ketu_idx, ketu_deg = get_nakshatra_from_longitude(ketu_lon)
        ketu_gati = get_planet_gati('Ketu', rahu_speed, True)
        ketu_gati_info = GATI_EFFECTS.get(ketu_gati, GATI_EFFECTS['sama'])
        transit_positions['Ketu'] = {
            'longitude': round(ketu_lon, 2),
            'nakshatra': ketu_nak,
            'nakshatra_idx': ketu_idx,
            'pada': int(ketu_deg / 3.333333) + 1,
            'rashi': RASHI_NAMES[int(ketu_lon / 30)],
            'speed': round(rahu_speed, 4),
            'is_retrograde': True,
            'gati': ketu_gati,
            'gati_name': ketu_gati_info['name'],
            'vedha_multiplier': ketu_gati_info['vedha_multiplier']
        }

        # Calculate vedhas for all 5 Janma factors
        vedhas = {
            'nakshatra': {'positive': [], 'negative': [], 'net': 0},
            'tithi': {'positive': [], 'negative': [], 'net': 0},
            'rashi': {'positive': [], 'negative': [], 'net': 0},
            'akshara': {'positive': [], 'negative': [], 'net': 0},
            'swara': {'positive': [], 'negative': [], 'net': 0}
        }

        # Build grid highlighting map
        grid_highlights = {}  # (row, col) -> {'planets': [], 'vedha_type': 'positive'/'negative'/'neutral'}

        # Check each planet
        for planet_name, pos in transit_positions.items():
            nak_idx = pos['nakshatra_idx']
            planet_nature = PLANET_NATURE.get(planet_name, 'neutral')
            # Match BTC SBC behavior: treat neutral planets as positive (only malefic is negative)
            vedha_type = 'negative' if planet_nature == 'malefic' else 'positive'

            # Mark planet position on grid
            nak_name = pos['nakshatra']
            if nak_name in NAKSHATRA_POSITIONS:
                grid_pos = NAKSHATRA_POSITIONS[nak_name]
                if grid_pos not in grid_highlights:
                    grid_highlights[grid_pos] = {'planets': [], 'vedha_type': 'neutral', 'is_planet': True}
                grid_highlights[grid_pos]['planets'].append(planet_name)

            # 1. Check Nakshatra vedha
            vedha_targets = NAKSHATRA_VEDHA.get(nak_idx, [])
            if janma['nakshatra']['index'] in vedha_targets:
                vedha_info = {
                    'planet': planet_name,
                    'from_nakshatra': pos['nakshatra'],
                    'to_target': janma['nakshatra']['name']
                }
                if vedha_type == 'negative':
                    vedhas['nakshatra']['negative'].append(vedha_info)
                elif vedha_type == 'positive':
                    vedhas['nakshatra']['positive'].append(vedha_info)

            # 2. Check Tithi vedha
            tithi_sources = TITHI_VEDHA.get(janma['tithi']['index'], [])
            if nak_idx in tithi_sources:
                vedha_info = {
                    'planet': planet_name,
                    'from_nakshatra': pos['nakshatra'],
                    'to_target': janma['tithi']['name']
                }
                if vedha_type == 'negative':
                    vedhas['tithi']['negative'].append(vedha_info)
                elif vedha_type == 'positive':
                    vedhas['tithi']['positive'].append(vedha_info)

            # 3. Check Rashi vedha
            rashi_sources = RASHI_VEDHA.get(janma['rashi']['index'], [])
            if nak_idx in rashi_sources:
                vedha_info = {
                    'planet': planet_name,
                    'from_nakshatra': pos['nakshatra'],
                    'to_target': janma['rashi']['name']
                }
                if vedha_type == 'negative':
                    vedhas['rashi']['negative'].append(vedha_info)
                elif vedha_type == 'positive':
                    vedhas['rashi']['positive'].append(vedha_info)

            # 4. Check Akshara vedha
            if janma['akshara']['group']:
                akshara_sources = AKSHARA_VEDHA.get(janma['akshara']['group'], [])
                if nak_idx in akshara_sources:
                    vedha_info = {
                        'planet': planet_name,
                        'from_nakshatra': pos['nakshatra'],
                        'to_target': f"{janma['akshara']['letter']} ({janma['akshara']['group']})"
                    }
                    if vedha_type == 'negative':
                        vedhas['akshara']['negative'].append(vedha_info)
                    elif vedha_type == 'positive':
                        vedhas['akshara']['positive'].append(vedha_info)

            # 5. Check Swara vedha
            if janma['swara']['vowel']:
                swara_sources = SWARA_VEDHA.get(janma['swara']['vowel'], [])
                if nak_idx in swara_sources:
                    vedha_info = {
                        'planet': planet_name,
                        'from_nakshatra': pos['nakshatra'],
                        'to_target': janma['swara']['vowel']
                    }
                    if vedha_type == 'negative':
                        vedhas['swara']['negative'].append(vedha_info)
                    elif vedha_type == 'positive':
                        vedhas['swara']['positive'].append(vedha_info)

        # Calculate net scores
        for factor in vedhas:
            vedhas[factor]['net'] = len(vedhas[factor]['positive']) - len(vedhas[factor]['negative'])

        # Calculate weighted combined score
        weights = {'nakshatra': 0.30, 'tithi': 0.15, 'rashi': 0.25, 'akshara': 0.15, 'swara': 0.15}
        combined_score = sum(vedhas[k]['net'] * weights[k] for k in weights)

        total_positive = sum(len(vedhas[k]['positive']) for k in vedhas)
        total_negative = sum(len(vedhas[k]['negative']) for k in vedhas)

        # Determine signal
        if combined_score >= 1.0:
            signal = 'STRONG_POSITIVE'
            description = 'Strong benefic influences - very favorable period'
        elif combined_score >= 0.3:
            signal = 'MILD_POSITIVE'
            description = 'Net benefic influence - generally favorable'
        elif combined_score > -0.3:
            signal = 'NEUTRAL'
            description = 'Balanced influences - no strong directional bias'
        elif combined_score > -1.0:
            signal = 'MILD_NEGATIVE'
            description = 'Net malefic influence - exercise caution'
        else:
            signal = 'STRONG_NEGATIVE'
            description = 'Strong malefic influences - challenging period'

        # Build SBC grid with colors for visualization
        sbc_grid = []
        for row_idx, row in enumerate(SBC_VISUAL_GRID):
            grid_row = []
            for col_idx, cell in enumerate(row):
                cell_type, cell_name, cell_short = cell

                cell_data = {
                    'type': cell_type,
                    'name': cell_name,
                    'short': cell_short,
                    'row': row_idx,
                    'col': col_idx,
                    'color': 'default',
                    'planets': [],
                    'is_birth_nakshatra': False,
                    'has_vedha': False
                }

                # Check if this is the birth nakshatra
                if cell_type == 'N' and cell_name == janma['nakshatra']['name']:
                    cell_data['is_birth_nakshatra'] = True
                    cell_data['color'] = 'gold'

                # Check if any planet is here
                if (row_idx, col_idx) in grid_highlights:
                    highlight = grid_highlights[(row_idx, col_idx)]
                    cell_data['planets'] = highlight['planets']

                    # Check if this planet is causing vedha
                    for planet in highlight['planets']:
                        planet_nature = PLANET_NATURE.get(planet, 'neutral')
                        if planet_nature == 'malefic':
                            cell_data['color'] = 'red'
                            cell_data['has_vedha'] = True
                        elif planet_nature == 'benefic' and cell_data['color'] != 'red':
                            cell_data['color'] = 'green'
                            cell_data['has_vedha'] = True

                grid_row.append(cell_data)
            sbc_grid.append(grid_row)

        # Mark birth nakshatra target with special highlight
        if janma['nakshatra']['name'] in NAKSHATRA_POSITIONS:
            birth_pos = NAKSHATRA_POSITIONS[janma['nakshatra']['name']]
            sbc_grid[birth_pos[0]][birth_pos[1]]['is_birth_nakshatra'] = True
            if sbc_grid[birth_pos[0]][birth_pos[1]]['color'] == 'default':
                sbc_grid[birth_pos[0]][birth_pos[1]]['color'] = 'gold'

        vara_name, vara_idx = get_vara(analysis_dt)
        tithi_name_now, tithi_idx_now = get_tithi(
            transit_positions['Sun']['longitude'],
            transit_positions['Moon']['longitude']
        )

        return {
            'name': name,
            'birth_data': birth_data,
            'analysis_datetime': analysis_dt.strftime('%Y-%m-%d %H:%M %Z'),
            'transit_positions': transit_positions,
            'current_vara': vara_name,
            'current_tithi': tithi_name_now,
            'vedhas_by_factor': vedhas,
            'vedhas_summary': {
                'positive_count': total_positive,
                'negative_count': total_negative,
                'net_score': total_positive - total_negative,
                'combined_weighted_score': round(combined_score, 2),
                'signal': signal,
                'description': description,
                'by_janma_factor': {
                    'nakshatra_score': vedhas['nakshatra']['net'],
                    'tithi_score': vedhas['tithi']['net'],
                    'rashi_score': vedhas['rashi']['net'],
                    'akshara_score': vedhas['akshara']['net'],
                    'swara_score': vedhas['swara']['net']
                }
            },
            'sbc_grid': sbc_grid,
            'grid_legend': {
                'red': 'Malefic planet causing negative vedha',
                'green': 'Benefic planet causing positive vedha',
                'gold': 'Birth Nakshatra (target)',
                'default': 'No active vedha'
            },
            'interpretation': generate_interpretation(name, vedhas, signal)
        }

    except Exception as e:
        return {'error': str(e)}


def generate_interpretation(name: str, vedhas: Dict, signal: str) -> str:
    """Generate a human-readable interpretation of the SBC analysis."""
    interpretations = []

    interpretations.append(f"=== SBC Analysis for {name} ===\n")

    # Nakshatra interpretation
    nak = vedhas['nakshatra']
    if nak['net'] > 0:
        interpretations.append(f"NAKSHATRA (Mental State): Positive influence. Clear thinking and good judgment are favored.")
    elif nak['net'] < 0:
        interpretations.append(f"NAKSHATRA (Mental State): Negative influence. Be careful of hasty decisions and worry.")
    else:
        interpretations.append(f"NAKSHATRA (Mental State): Neutral. No strong mental influences.")

    # Tithi interpretation
    tithi = vedhas['tithi']
    if tithi['net'] > 0:
        interpretations.append(f"TITHI (Relationships): Positive. Good for family and social connections.")
    elif tithi['net'] < 0:
        interpretations.append(f"TITHI (Relationships): Challenging. Possible tensions in relationships.")
    else:
        interpretations.append(f"TITHI (Relationships): Neutral. No strong relationship influences.")

    # Rashi interpretation
    rashi = vedhas['rashi']
    if rashi['net'] > 0:
        interpretations.append(f"RASHI (Life Events): Favorable. Positive events likely in life areas.")
    elif rashi['net'] < 0:
        interpretations.append(f"RASHI (Life Events): Challenging. Be prepared for obstacles.")
    else:
        interpretations.append(f"RASHI (Life Events): Neutral. Status quo maintained.")

    # Akshara interpretation
    aksh = vedhas['akshara']
    if aksh['net'] > 0:
        interpretations.append(f"AKSHARA (Reputation/Body): Positive. Good for public image and health.")
    elif aksh['net'] < 0:
        interpretations.append(f"AKSHARA (Reputation/Body): Challenging. Watch reputation and health.")
    else:
        interpretations.append(f"AKSHARA (Reputation/Body): Neutral.")

    # Swara interpretation
    swara = vedhas['swara']
    if swara['net'] > 0:
        interpretations.append(f"SWARA (Life Force): Strong vitality and energy.")
    elif swara['net'] < 0:
        interpretations.append(f"SWARA (Life Force): Low energy possible. Rest and self-care advised.")
    else:
        interpretations.append(f"SWARA (Life Force): Normal energy levels.")

    # Overall
    interpretations.append(f"\nOVERALL: {signal}")

    return "\n".join(interpretations)
