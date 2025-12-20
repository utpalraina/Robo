"""
SBC Market Prediction Rules Module

Based on:
1. "Vedic Astrology in Money Matters" by P.K. Vasudev (Pages 464-490)
2. "Mystics of Sarvatobhadra Chakra" by M.K. Agarwal (Chapters 15, 20)
3. Varaha Mihira's Sarvatobhadra Chakra

This module implements:
1. Nakshatra-Commodity Rulership (28 nakshatras from MK Agarwal)
2. Planet-in-Rasi Commodity Price Rules (all 12 rasis)
3. Retrograde/Combustion Strength Modifiers
4. Teji/Mandi Market Yogas (bullish/bearish combinations)
5. Mutual Vedha Detection
6. Western Aspect Calculations
7. Combined Market Prediction Engine
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import math
from datetime import datetime

# =====================================================
# NAKSHATRA-COMMODITY RULERSHIP
# From MK Agarwal "Mystics of SBC" Chapter 15 (pp. 55-58)
# =====================================================

# Nakshatra indices (0-27, including Abhijit)
NAKSHATRA_NAMES = [
    'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
    'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
    'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
    'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Abhijit', 'Shravana', 'Dhanishta',
    'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
]

# Create reverse mapping
NAKSHATRA_TO_IDX = {name: idx for idx, name in enumerate(NAKSHATRA_NAMES)}
# Also support names without Abhijit (standard 27)
NAKSHATRA_TO_IDX_27 = {
    'Ashwini': 0, 'Bharani': 1, 'Krittika': 2, 'Rohini': 3, 'Mrigashira': 4, 'Ardra': 5,
    'Punarvasu': 6, 'Pushya': 7, 'Ashlesha': 8, 'Magha': 9, 'Purva Phalguni': 10,
    'Uttara Phalguni': 11, 'Hasta': 12, 'Chitra': 13, 'Swati': 14, 'Vishakha': 15,
    'Anuradha': 16, 'Jyeshtha': 17, 'Mula': 18, 'Purva Ashadha': 19, 'Uttara Ashadha': 20,
    'Shravana': 21, 'Dhanishta': 22, 'Shatabhisha': 23, 'Purva Bhadrapada': 24,
    'Uttara Bhadrapada': 25, 'Revati': 26
}

# Complete Nakshatra-Commodity Rulership from MK Agarwal (pp. 55-58)
# Malefic vedha = Teji (price rise), Benefic vedha = Mandi (price fall)
NAKSHATRA_COMMODITY_RULES = {
    'Ashwini': {
        'commodities': ['ghee', 'rice', 'clothes', 'animals'],
        'direction': 'North',
        'duration_days': 60
    },
    'Bharani': {
        'commodities': ['wheat', 'rice', 'kali_mirch', 'sonth'],
        'direction': 'South',
        'duration_months': 8
    },
    'Krittika': {
        'commodities': ['rice', 'gram', 'grains', 'til', 'oil', 'diamond', 'gems', 'gold', 'silver'],
        'direction': 'South',
        'duration_months': 8
    },
    'Rohini': {
        'commodities': ['grains', 'liquids', 'oils', 'metals'],
        'direction': 'East',
        'duration_days': 7
    },
    'Mrigashira': {
        'commodities': ['animals', 'liquids'],
        'direction': 'North',
        'delay_days': 3
    },
    'Ardra': {
        'commodities': ['oil', 'salt', 'liquids', 'sandal', 'scented_items'],
        'direction': 'West',
        'duration_days': 15
    },
    'Punarvasu': {
        'commodities': ['cotton', 'thread', 'jute', 'til'],
        'direction': 'North-East',
        'duration_days': 30
    },
    'Pushya': {
        'commodities': ['gold', 'silver', 'ghee', 'rice', 'salt', 'heeng', 'oils'],
        'direction': 'North-South',
        'duration_days': 15
    },
    'Ashlesha': {
        'commodities': ['gur', 'sugar', 'masoor', 'wheat'],
        'direction': 'West',
        'duration_days': 15
    },
    'Magha': {
        'commodities': ['ghee', 'oil', 'til', 'gram', 'gur'],
        'direction': 'South',
        'duration_days': 15
    },
    'Purva Phalguni': {
        'commodities': ['woolen_clothes', 'wool', 'oils', 'silver'],
        'direction': 'South',
        'duration_days': 15
    },
    'Uttara Phalguni': {
        'commodities': ['urad', 'moong', 'rice'],
        'direction': 'North',
        'duration_days': 15
    },
    'Hasta': {
        'commodities': ['sandal', 'camphor'],
        'direction': 'North',
        'duration_days': 15
    },
    'Chitra': {
        'commodities': ['gold', 'gems', 'gur', 'urad', 'moong', 'animals'],
        'direction': 'North',
        'duration_days': 15
    },
    'Swati': {
        'commodities': ['chilies', 'oil', 'heeng'],
        'direction': 'North',
        'duration_days': 15
    },
    'Vishakha': {
        'commodities': ['rice', 'wheat', 'moong', 'masoor', 'moth'],
        'direction': 'South',
        'duration_days': 15
    },
    'Anuradha': {
        'commodities': ['arhar', 'grains', 'rice', 'gram'],
        'direction': 'East',
        'duration_days': 15
    },
    'Jyeshtha': {
        'commodities': ['gur', 'camphor', 'mercury', 'heeng'],
        'direction': 'East',
        'duration_days': 15
    },
    'Mula': {
        'commodities': ['white_commodities', 'cotton', 'grains'],
        'direction': 'West',
        'duration_days': 15
    },
    'Purva Ashadha': {
        'commodities': ['ghee', 'grains'],
        'direction': 'West',
        'duration_days': 15
    },
    'Uttara Ashadha': {
        'commodities': ['animals', 'iron', 'brass', 'copper'],
        'direction': 'East',
        'duration_days': 15
    },
    'Abhijit': {
        'commodities': ['moong', 'sonth'],
        'direction': 'East',
        'duration_days': 15
    },
    'Shravana': {
        'commodities': ['sugar', 'grains', 'sweet_commodities'],
        'direction': 'East',
        'duration_days': 15
    },
    'Dhanishta': {
        'commodities': ['gold', 'silver', 'pearls', 'gems'],
        'direction': 'East',
        'duration_days': 15
    },
    'Shatabhisha': {
        'commodities': ['oils', 'wines'],
        'direction': 'West',
        'duration_days': 15
    },
    'Purva Bhadrapada': {
        'commodities': ['metals', 'grains', 'medicines'],
        'direction': 'South',
        'duration_days': 15
    },
    'Uttara Bhadrapada': {
        'commodities': ['gur', 'sugar', 'til', 'oils'],
        'direction': 'West',
        'duration_days': 15
    },
    'Revati': {
        'commodities': ['pearl', 'gems', 'betelenuts'],
        'direction': 'North',
        'duration_days': 15
    }
}

# Gold-ruling nakshatras (combined from both books)
GOLD_NAKSHATRAS = {
    2: 'Krittika',        # Gold, gems, diamond
    7: 'Pushya',          # Gold, silver
    13: 'Chitra',         # Gold, gems
    22: 'Dhanishta',      # Gold, silver, pearls
    6: 'Punarvasu',       # From Vasudev
    10: 'Purva Phalguni', # From Vasudev
    15: 'Vishakha',       # From Vasudev
    18: 'Mula',           # From Vasudev
    24: 'Purva Bhadrapada' # From Vasudev
}

# Silver-ruling nakshatras (combined)
SILVER_NAKSHATRAS = {
    2: 'Krittika',        # Gold, silver
    7: 'Pushya',          # Gold, silver
    10: 'Purva Phalguni', # Silver, wool
    22: 'Dhanishta',      # Gold, silver
    6: 'Punarvasu',       # From Vasudev
    12: 'Hasta',          # From Vasudev
    17: 'Jyeshtha',       # From Vasudev
    21: 'Shravana',       # From Vasudev
    23: 'Shatabhisha',    # From Vasudev
    24: 'Purva Bhadrapada' # From Vasudev
}

# Stock market nakshatras
STOCK_NAKSHATRAS = {
    3: 'Rohini',          # Taurus - stock markets
    14: 'Swati',          # Libra - trade, commerce
    19: 'Purva Ashadha',  # Sagittarius - speculation
    20: 'Uttara Ashadha', # Capricorn - business
    23: 'Shatabhisha',    # Stock exchanges
    24: 'Purva Bhadrapada', # Stock markets, risky investments
    26: 'Revati'          # Share brokers, stock exchanges
}

# Bitcoin/Crypto rulership (modern interpretation based on traditional rules)
CRYPTO_NAKSHATRAS = {
    22: 'Dhanishta',      # Mars-ruled, wealth accumulation
    23: 'Shatabhisha',    # Rahu-ruled, technology, innovation
    24: 'Purva Bhadrapada', # Jupiter-ruled, speculation
    25: 'Uttara Bhadrapada', # Saturn-ruled, long-term value (BTC birth nakshatra!)
    18: 'Mula',           # Ketu-ruled, hidden wealth, transformation
}

# =====================================================
# SIGN CLASSIFICATIONS (from book)
# =====================================================

# Bullish signs - transit here causes rising trends
BULLISH_SIGNS = {
    0: 'Aries',      # Fire, Mars - gold, wheat, copper
    1: 'Taurus',     # Earth, Venus - stock markets
    4: 'Leo',        # Fire, Sun - gold, bullion
    7: 'Scorpio',    # Water, Mars - iron, transformation
    8: 'Sagittarius', # Fire, Jupiter - stock shares
    9: 'Capricorn'   # Earth, Saturn - gold, stocks, copper
}

# Bearish signs - transit here causes falling/dull trends
BEARISH_SIGNS = {
    2: 'Gemini',     # Air, Mercury - cotton
    3: 'Cancer',     # Water, Moon - silver
    5: 'Virgo',      # Earth, Mercury - service industries
    6: 'Libra',      # Air, Venus - silver, gold, cotton
    10: 'Aquarius',  # Air, Saturn - shares
    11: 'Pisces'     # Water, Jupiter - precious stones
}

# Sign commodity rulership
SIGN_COMMODITIES = {
    0: ['gold', 'wheat', 'copper'],           # Aries
    1: ['stock_markets', 'stock_exchanges'],  # Taurus
    2: ['cotton'],                             # Gemini
    3: ['silver'],                             # Cancer
    4: ['gold', 'bullion'],                    # Leo
    5: ['service', 'agriculture'],             # Virgo
    6: ['silver', 'gold', 'cotton'],          # Libra
    7: ['iron', 'metals'],                     # Scorpio
    8: ['stock_shares'],                       # Sagittarius
    9: ['gold', 'stock_shares', 'copper'],    # Capricorn
    10: ['shares', 'technology'],              # Aquarius
    11: ['precious_stones', 'crypto']          # Pisces
}

# =====================================================
# PLANET-IN-RASI COMMODITY PRICE RULES
# From MK Agarwal Chapter 15 (pp. 57-61)
# Rise = Teji, Fall = Mandi
# =====================================================

PLANET_RASI_COMMODITY_RULES = {
    # SUN (Sy) in each Rasi
    'Sun': {
        0: {'rise': ['cotton', 'ghee', 'oil', 'til', 'sarso', 'almond', 'gur', 'sugar', 'gold', 'silver'],
            'fall': ['wheat', 'rice', 'urad', 'moong', 'arhar', 'gram', 'peas']},  # Aries
        1: {'rise': ['silver', 'gold', 'gur', 'sugar', 'cotton', 'oil'],
            'fall': ['wheat', 'gram', 'arhar', 'moong', 'rice']},  # Taurus
        2: {'rise': ['silk', 'cotton', 'steel', 'oil', 'gur', 'sugar', 'ghee', 'moong', 'urad', 'wheat', 'gram', 'rice', 'gold', 'silver']},  # Gemini
        3: {'rise': ['gur', 'sugar', 'silver', 'gold', 'oil', 'cotton', 'sarso'],
            'fall': ['wheat', 'gram', 'matar', 'arhar', 'urad', 'moong', 'rice']},  # Cancer
        4: {'rise': ['silver', 'gold', 'gur', 'cotton', 'sugar', 'oil'],
            'fall': ['grains', 'shares']},  # Leo
        5: {'rise': ['oil', 'cotton', 'red_items'],
            'fall': ['silver', 'shares']},  # Virgo
        6: {'rise': ['wheat', 'gram', 'gold', 'copper'],
            'fall': ['silver', 'cotton']},  # Libra
        7: {'rise': ['cotton', 'copper', 'gold', 'silver', 'woolen_items'],
            'fall': ['red_items']},  # Scorpio
        8: {'rise': ['cotton', 'til', 'oil', 'gold', 'silver'],
            'fall': ['grains']},  # Sagittarius
        9: {'rise': ['ghee', 'oil', 'gur', 'sugar', 'cotton'],
            'fall': ['wheat', 'grains']},  # Capricorn
        10: {'rise': ['ghee', 'oil', 'salt', 'groundnut'],
             'fall': ['cotton', 'wheat', 'grains', 'gur', 'sugar']},  # Aquarius
        11: {'rise': ['oil', 'gur', 'sugar', 'cotton', 'gold'],
             'fall': ['silver']},  # Pisces
    },
    # MOON (Ch) in each Rasi
    'Moon': {
        0: {'rise': ['wheat', 'gram', 'alsi', 'opium'],
            'fall': ['gold', 'silver']},  # Aries
        1: {'rise': ['wheat', 'gram', 'urad', 'til', 'groundnut', 'silver', 'cotton'],
            'fall': ['animals']},  # Taurus
        2: {'rise': ['cotton', 'wheat', 'gram']},  # Gemini
        3: {'fall': ['silver', 'gold', 'cotton']},  # Cancer (aspected by Jupiter)
        4: {'rise': ['camphor', 'cotton', 'silver', 'gold']},  # Leo
        5: {'rise': ['gold', 'silver', 'steel'],
            'fall': ['cotton']},  # Virgo
        6: {'fall': ['rice', 'ghee', 'groundnut', 'silver', 'gold']},  # Libra
        7: {'fall': ['gold', 'silver', 'pearls']},  # Scorpio
        8: {'fall': ['til', 'oil', 'cotton', 'cotton_clothes']},  # Sagittarius
        9: {'rise': ['metals']},  # Capricorn (all types)
        10: {'rise': ['oil', 'til', 'groundnut'],
             'fall': ['cotton', 'gold', 'silver']},  # Aquarius
        11: {'fall': ['gold', 'silver']},  # Pisces
    },
    # MARS (Ma) in each Rasi
    'Mars': {
        0: {'rise': ['gur', 'gold', 'silver', 'metals', 'red_coral', 'pearl', 'wool', 'cotton'],
            'fall': ['wheat', 'grains']},  # Aries
        1: {'rise': ['red_items', 'grains', 'cotton', 'oil', 'gold', 'silver', 'copper', 'shares']},  # Taurus
        2: {'rise': ['gur', 'sugar', 'copper', 'red_items']},  # Gemini
        3: {'rise': ['grains', 'gur', 'sugar', 'animals'],
            'fall': ['oils', 'silver']},  # Cancer (benefic relation)
        4: {'rise': ['silver', 'gold', 'copper', 'steel', 'gur', 'sugar', 'wheat', 'red_chillies', 'red_items']},  # Leo
        5: {'rise': ['cotton', 'gold', 'silver', 'wool', 'wheat', 'red_items']},  # Virgo
        6: {'rise': ['gur', 'sugar', 'wheat', 'urad', 'moong', 'grains'],
            'fall': []},  # Libra (fall if associated with Jupiter)
        7: {'rise': ['gur', 'gold', 'silver', 'cotton']},  # Scorpio
        8: {'rise': ['cotton', 'silver', 'metals', 'ghee', 'grains', 'animals']},  # Sagittarius
        9: {'rise': ['gold', 'silver', 'copper', 'gur', 'ghee', 'oil', 'wool'],
            'fall': ['grains']},  # Capricorn (benefic aspect)
        10: {'rise': ['wheat', 'grains', 'gur', 'gold'],
             'fall': ['silver', 'cotton']},  # Aquarius
        11: {'rise': ['gold', 'cotton', 'woolen_items'],
             'fall': ['silver']},  # Pisces
    },
    # MERCURY (Bu) in each Rasi
    'Mercury': {
        0: {'rise': ['animals'],
            'fall': ['gold', 'silver', 'metals', 'wheat', 'gram', 'til', 'mustard_oil', 'cotton', 'ghee', 'gur', 'sugar']},  # Aries
        1: {'rise': ['wheat', 'gram', 'rice', 'cotton', 'oil']},  # Taurus
        2: {'rise': ['animals'],
            'fall': ['gold', 'silver', 'sarso']},  # Gemini
        3: {'rise': ['silver', 'gur', 'oil', 'groundnut'],
            'fall': ['cotton', 'gold', 'grains', 'white_cloth']},  # Cancer (short period)
        4: {'rise': ['silver', 'gold', 'cotton', 'woolen_items'],
            'fall': ['gur', 'sugar', 'camphor']},  # Leo
        5: {'rise': ['wheat', 'gram', 'gur', 'sugar', 'haldi'],
            'fall': ['cotton', 'silver']},  # Virgo
        6: {'rise': ['cotton', 'gur', 'sugar', 'gold'],
            'fall': ['silver', 'groundnut', 'oils']},  # Libra
        7: {'rise': ['ghee', 'oil', 'silver', 'gold'],
            'fall': ['grains']},  # Scorpio
        8: {'rise': ['cotton', 'silver'],
            'fall': []},  # Sagittarius (if malefic relation, otherwise fall)
        9: {'rise': ['cotton', 'gold', 'silver'],
            'fall': ['grains']},  # Capricorn
        10: {'rise': ['ghee', 'oil', 'gur', 'sugar'],
             'fall': ['silver', 'cotton']},  # Aquarius
        11: {'rise': ['gold', 'silver'],
             'fall': ['gur', 'cotton', 'sugar']},  # Pisces (short period)
    },
    # JUPITER (Gu) in each Rasi
    'Jupiter': {
        0: {'rise': ['cotton'],
            'fall': ['gold', 'silver', 'copper', 'gur', 'silk']},  # Aries
        1: {'rise': ['cotton', 'silver', 'grains'],
            'fall': ['salt', 'red_items']},  # Taurus
        2: {'rise': ['copper', 'steel', 'ghee'],
            'fall': ['cotton', 'gold', 'silver', 'cloth', 'groundnut']},  # Gemini
        3: {'rise': ['cotton', 'gur', 'sugar', 'ghee', 'wheat', 'grains']},  # Cancer
        4: {'rise': ['ghee', 'wheat', 'cotton'],
            'fall': ['silver', 'gold', 'copper', 'steel']},  # Leo (alone)
        5: {'rise': ['rice', 'wheat', 'moong', 'urad', 'gram', 'oil', 'ghee', 'gur', 'sugar'],
            'fall': ['cotton', 'silver', 'grains']},  # Virgo
        6: {'rise': ['gold', 'cotton'],
            'fall': ['ghee', 'oil', 'sarso']},  # Libra
        7: {'rise': ['cotton', 'gold', 'silver', 'copper', 'ghee', 'oil', 'gur', 'urad', 'dal', 'grains']},  # Scorpio (short period)
        8: {'rise': ['gur'],
            'fall': ['sugar', 'gur', 'wheat', 'salt', 'oil', 'ghee', 'gold', 'silver', 'brass', 'steel', 'copper', 'coins']},  # Sagittarius (with Saturn)
        9: {'rise': ['wheat', 'gram', 'cotton', 'copper', 'gold', 'silver'],
            'fall': []},  # Capricorn (benefic relations = fall)
        10: {'rise': ['gold', 'copper', 'brass', 'steel', 'cotton']},  # Aquarius (after 3 months, cotton up to 6 months)
        11: {'rise': ['cotton', 'wheat', 'gur', 'urad', 'sugar', 'salt']},  # Pisces (cotton for 6 months)
    },
    # VENUS (Sk) in each Rasi
    'Venus': {
        0: {'rise': ['gram', 'wheat', 'grains', 'ghee', 'gold', 'silver', 'gur'],
            'fall': ['wool', 'til', 'oil']},  # Aries
        1: {'rise': ['gold', 'silver'],
            'fall': ['grains', 'cotton']},  # Taurus
        2: {'rise': ['wheat', 'gram', 'rice'],
            'fall': ['cotton', 'cloth', 'oil', 'arhar', 'gur', 'ghee']},  # Gemini
        3: {'rise': ['cotton', 'oils', 'ghee', 'gur', 'sugar'],
            'fall': ['silver', 'wheat', 'gram', 'arhar']},  # Cancer
        4: {'rise': ['gold', 'copper', 'gram', 'wheat', 'ghee', 'animals'],
            'fall': ['silver']},  # Leo
        5: {'rise': ['silver', 'wheat', 'grains', 'gur', 'woolen_clothes', 'rice']},  # Virgo
        6: {'rise': ['gold', 'gur', 'sugar'],
            'fall': ['cotton', 'silver']},  # Libra
        7: {'rise': ['wheat', 'urad', 'moong', 'moth', 'bajra', 'silver', 'gur']},  # Scorpio
        8: {'rise': ['wheat', 'gram', 'grains', 'silver', 'gold', 'copper'],
            'fall': ['cotton']},  # Sagittarius
        9: {'rise': ['shares', 'gur', 'ghee', 'wheat', 'gram', 'grains']},  # Capricorn
        10: {'rise': ['cotton'],
             'fall': ['silver', 'gur', 'wheat', 'gram', 'moong', 'white_items']},  # Aquarius (cotton at 24°)
        11: {'rise': ['silver'],
             'fall': ['grains', 'oil', 'gur', 'sugar']},  # Pisces (benefic relation)
    },
    # SATURN (Sa) in each Rasi
    'Saturn': {
        0: {'rise': ['gold', 'silver', 'copper', 'metals', 'til', 'oil', 'ghee', 'cotton'],
            'fall': ['gur', 'sugar', 'oil']},  # Aries
        1: {'rise': ['gur', 'sugar', 'cotton', 'gold', 'silver', 'copper', 'oils', 'wheat', 'grains', 'rice'],
            'fall': []},  # Taurus (fall in last 6 months of transit)
        2: {'rise': ['salt', 'oils', 'gur', 'steel'],
            'fall': ['gold', 'animals']},  # Gemini
        3: {'rise': ['cotton']},  # Cancer
        4: {'rise': ['gur', 'oil', 'steel', 'urad', 'grains', 'cotton']},  # Leo (when 6-7°)
        5: {'rise': ['cotton', 'gur', 'sugar', 'grains'],
            'fall': ['gold', 'silver']},  # Virgo (for some time)
        6: {'rise': ['gur', 'cotton', 'sugar', 'grains'],
            'fall': ['cotton']},  # Libra (cotton fall at 15°)
        7: {'rise': ['wheat', 'gram', 'masoor', 'cotton', 'silver'],
            'fall': []},  # Scorpio (benefic aspect = fall)
        8: {'rise': ['wheat', 'gram', 'grains', 'gur', 'sugar', 'coal']},  # Sagittarius
        9: {'rise': ['cotton', 'silver', 'gold', 'copper', 'wheat', 'oil', 'grains']},  # Capricorn
        10: {'rise': ['oils', 'silver', 'grains', 'shares']},  # Aquarius
        11: {'rise': ['gur', 'sugar', 'ghee', 'grains', 'gold', 'silver'],
             'fall': []},  # Pisces (first 6 months rise, then fall)
    },
    # RAHU in each Rasi
    'Rahu': {
        0: {'rise': ['wheat', 'gram', 'grains']},  # Aries
        1: {'rise': ['oils', 'gur', 'sugar', 'cotton']},  # Taurus
        2: {'rise': ['cotton', 'ghee', 'grains', 'yarn'],
            'fall': ['silver', 'gold']},  # Gemini
        3: {'rise': ['steel', 'copper', 'brass', 'gold', 'silver', 'wheat', 'rice']},  # Cancer
        4: {'rise': ['oil', 'kiryana_items'],
            'fall': ['wheat', 'grains']},  # Leo
        5: {'rise': ['cotton'],
            'fall': ['oil', 'sarso', 'til']},  # Virgo
        6: {'rise': ['grains']},  # Libra
        7: {'rise': ['cotton', 'gold', 'silver']},  # Scorpio (short period)
        8: {'rise': ['cotton', 'animals']},  # Sagittarius (after a month)
        9: {'rise': ['gram', 'wheat'],
            'fall': ['gur', 'sarso']},  # Capricorn
        10: {'rise': ['oils'],
             'fall': []},  # Aquarius (malefic relation = rise, benefic = fall)
        11: {'rise': ['grains', 'cotton'],
             'fall': ['gold', 'silver']},  # Pisces
    },
    # URANUS (Herschel) - From MK Agarwal pp. 61, 86-87
    # General effect: Mandi (bearish). With benefic = Mandi. With malefic = Teji.
    'Uranus': {
        0: {'rise': ['shares', 'factories', 'machines'], 'fall': ['grains']},  # Aries - sudden changes
        1: {'rise': ['technology', 'machines'], 'fall': ['cotton']},  # Taurus
        2: {'rise': ['technology', 'electronics'], 'fall': ['grains']},  # Gemini
        3: {'fall': ['silver', 'gold', 'shares']},  # Cancer - bearish for metals
        4: {'rise': ['gold', 'shares'], 'fall': ['technology']},  # Leo - with malefic = Teji
        5: {'fall': ['shares', 'cotton', 'technology']},  # Virgo - bearish
        6: {'fall': ['shares', 'gold', 'silver']},  # Libra - bearish
        7: {'rise': ['technology', 'crypto', 'metals']},  # Scorpio - sudden gains
        8: {'rise': ['shares', 'speculation']},  # Sagittarius - with malefic
        9: {'fall': ['shares', 'gold']},  # Capricorn - bearish
        10: {'rise': ['technology', 'crypto', 'innovation'], 'fall': ['traditional']},  # Aquarius - own sign
        11: {'fall': ['shares', 'gold', 'silver']},  # Pisces - bearish
    },
    # NEPTUNE - From MK Agarwal pp. 61, 86-87
    # General effect: Teji (bullish). With malefic = Teji. With benefic = Mandi.
    'Neptune': {
        0: {'rise': ['oil', 'chemicals', 'medicines']},  # Aries
        1: {'rise': ['oil', 'liquids', 'chemicals']},  # Taurus
        2: {'rise': ['chemicals', 'pharmaceuticals']},  # Gemini
        3: {'rise': ['silver', 'liquids', 'oil']},  # Cancer - water sign
        4: {'rise': ['gold', 'shares', 'speculation']},  # Leo
        5: {'rise': ['medicines', 'healthcare', 'chemicals']},  # Virgo
        6: {'rise': ['oil', 'perfumes', 'chemicals']},  # Libra
        7: {'rise': ['oil', 'hidden_wealth', 'crypto']},  # Scorpio
        8: {'rise': ['oil', 'speculation', 'foreign_trade']},  # Sagittarius
        9: {'rise': ['oil', 'shares', 'gold']},  # Capricorn
        10: {'rise': ['technology', 'innovation', 'crypto']},  # Aquarius
        11: {'rise': ['oil', 'liquids', 'crypto', 'gold']},  # Pisces - own sign, strong
    },
    # PLUTO - From MK Agarwal pp. 61, 86-87
    # Significations: Medicines, weapons, mines, transformation, hidden wealth
    'Pluto': {
        0: {'rise': ['metals', 'weapons', 'iron', 'crypto']},  # Aries - Mars sign
        1: {'rise': ['gold', 'banking', 'hidden_wealth']},  # Taurus
        2: {'rise': ['technology', 'communication']},  # Gemini
        3: {'rise': ['silver', 'real_estate', 'hidden_wealth']},  # Cancer
        4: {'rise': ['gold', 'power', 'authority']},  # Leo
        5: {'rise': ['medicines', 'healthcare', 'mining']},  # Virgo
        6: {'rise': ['shares', 'partnerships', 'transformation']},  # Libra
        7: {'rise': ['crypto', 'hidden_wealth', 'transformation', 'gold']},  # Scorpio - own sign
        8: {'rise': ['foreign_investment', 'speculation']},  # Sagittarius
        9: {'rise': ['gold', 'shares', 'institutions', 'crypto']},  # Capricorn
        10: {'rise': ['technology', 'crypto', 'innovation', 'revolution']},  # Aquarius
        11: {'rise': ['oil', 'hidden_wealth', 'crypto']},  # Pisces
    },
}

# =====================================================
# COMBUSTION RULES (from MK Agarwal p. 31)
# Combust planets have strength = 0
# =====================================================

COMBUSTION_ORBS = {
    'Moon': 12,      # Within 12° of Sun
    'Mars': 17,      # Within 17° of Sun
    'Mercury': 13,   # Within 13° of Sun
    'Jupiter': 11,   # Within 11° of Sun
    'Venus': 9,      # Within 09° of Sun
    'Saturn': 15,    # Within 15° of Sun
    'Rahu': 15,      # Within 15° of Sun
    'Ketu': 15,      # Within 15° of Sun
}

def is_planet_combust(planet: str, planet_lon: float, sun_lon: float) -> bool:
    """Check if planet is combust (too close to Sun)."""
    if planet == 'Sun':
        return False  # Sun cannot be combust
    orb = COMBUSTION_ORBS.get(planet, 10)
    diff = abs(planet_lon - sun_lon)
    if diff > 180:
        diff = 360 - diff
    return diff <= orb


# =====================================================
# RETROGRADE STRENGTH MULTIPLIER
# From MK Agarwal: Retrograde planets have 200% strength
# Malefic retrograde = 200% malefic
# Benefic retrograde = 200% benefic
# =====================================================

RETROGRADE_MULTIPLIER = 2.0  # 200% strength

# =====================================================
# TEJI/MANDI MARKET YOGAS
# From MK Agarwal Chapter 20 (pp. 85-91)
# Bullish (Teji) and Bearish (Mandi) combinations
# =====================================================

BULLISH_YOGAS = [
    # Mercury combinations
    {'condition': 'Mercury behind Saturn/Jupiter/Mars/Venus in same nakshatra',
     'description': 'Bu behind slow graha = Teji continues till Bu crosses'},
    {'condition': 'Mercury behind Pluto/Neptune/Uranus/Rahu/Ketu, aspected by Saturn and Mars',
     'description': 'Bu behind outer planets with malefic aspects'},
    {'condition': 'Mercury opposite Pluto/Neptune/Uranus at 180°',
     'description': 'Maximum Teji when Bu 180° from outer planets'},
    {'condition': 'Mercury combust by Sun',
     'description': 'Teji continues while Bu is combust'},
    {'condition': 'Mercury retrograde ahead of Sun in same rasi',
     'description': 'Teji continues while Bu is retrograde'},
    {'condition': 'Mercury and Saturn both retrograde in same rasi',
     'description': 'Both retrograde = strong Teji'},
    # Jupiter combinations
    {'condition': 'Jupiter going retrograde or direct',
     'description': 'Teji on date Jupiter changes direction'},
    {'condition': 'Jupiter and Saturn both retrograde in Aries/Leo/Libra/Scorpio/Capricorn',
     'description': 'Both retrograde in these signs'},
    {'condition': 'Jupiter retrograde in 5th bhava with malefic aspect',
     'description': 'Retrograde Gu in 5th with malefic'},
    {'condition': 'Jupiter and Venus opposite each other at same degree',
     'description': 'Gu-Sk opposition at exact degree'},
    {'condition': 'Jupiter combust by Sun',
     'description': 'Teji continues while Gu is combust'},
    # Saturn combinations
    {'condition': 'Saturn retrograde in Libra',
     'description': 'Sa(R) in Libra = Teji'},
    {'condition': 'Saturn and Mars opposite or exchange',
     'description': 'Sa-Ma opposition or exchange'},
    {'condition': 'Saturn retrograde in Aries/Leo with Mars',
     'description': 'Sa(R) with Ma in fire signs'},
    # General combinations
    {'condition': 'Fast planet behind slow planet in same nakshatra',
     'description': 'Rising continues till fast crosses slow'},
    {'condition': 'Mars enters Pushya/Anuradha/U.Bhadra owned by Saturn',
     'description': 'Ma in Sa-owned nakshatras with Sa present'},
]

BEARISH_YOGAS = [
    {'condition': 'Slow planet behind fast planet in same nakshatra',
     'description': 'Reversal of normal order'},
    {'condition': 'Jupiter behind Sun/Moon/Mars/Mercury/Venus in same nakshatra',
     'description': 'Gu behind faster planets'},
    {'condition': 'Jupiter ahead of Saturn/Rahu/Ketu/outer planets',
     'description': 'Gu ahead of slower planets'},
    {'condition': 'Rahu/Ketu behind Venus(R)',
     'description': 'Nodes behind retrograde Venus'},
    {'condition': 'Saturn(R) ahead of Rahu/Ketu',
     'description': 'Retrograde Sa ahead of nodes'},
    {'condition': 'Two benefic planets in trine with same degree',
     'description': 'Bearish trend starts when fast enters sign'},
    {'condition': 'Jupiter/Saturn retrograde in 5th bhava or Neptune(R) in 2nd',
     'description': 'Retrograde planets in wealth houses'},
]

# Special market timing rules
SPECIAL_MARKET_RULES = {
    'Sun': 'Market trend reverses if Sun is with a combust graha',
    'Moon': 'Indicator of daily fluctuations only',
    'Mars': 'With fast moving graha, market picks up. With Sa/Neptune/Pluto = Teji',
    'Mercury': {
        'stays_25_days': 'Lot of fluctuation if Bu in rasi > 25 days',
        'ahead_of_sun': 'Causes Mandi if ahead of Sun',
        'with_sun': 'Lot of fluctuations if joined by Sun',
        'exalted_with_sun': 'Exalted with Sun = Teji',
        'debilitated_with_sun': 'Debilitated with Sun = Mandi',
        'retrograde': 'Same trend for 7 days',
    },
    'Jupiter': {
        'movable_sign': 'Causes Mandi when in movable rasi',
        'with_malefic': 'Causes Teji if joined by malefic graha',
        'with_uranus': 'Causes sudden Teji if joined by Uranus',
    },
    'Venus': 'Causes both Mandi & Teji. With Bu = Mandi. With Pluto = Teji',
    'Saturn': 'Causes Teji. With Rahu/Neptune = Teji due to shortage',
    'Uranus': 'Mandi. With benefic = Mandi. With malefic = Teji',
    'Neptune': 'Teji. With malefic = Teji. With benefic = Mandi',
}

# =====================================================
# WESTERN ASPECTS (for "gross effects")
# =====================================================

class AspectType(Enum):
    CONJUNCTION = 0      # 0° - Strong, nature depends on planets
    SEXTILE = 60         # 60° - Mildly benefic
    SQUARE = 90          # 90° - Malefic/Bearish
    TRINE = 120          # 120° - Strongly benefic
    OPPOSITION = 180     # 180° - Malefic/Bearish

# Aspect orbs (tolerance in degrees)
ASPECT_ORBS = {
    AspectType.CONJUNCTION: 8,
    AspectType.SEXTILE: 6,
    AspectType.SQUARE: 8,
    AspectType.TRINE: 8,
    AspectType.OPPOSITION: 8
}

# Aspect market effects
ASPECT_EFFECTS = {
    AspectType.CONJUNCTION: 'neutral',  # Depends on planets involved
    AspectType.SEXTILE: 'bearish',      # Per book: Sextile causes falls
    AspectType.SQUARE: 'bearish',       # Strongly bearish
    AspectType.TRINE: 'bullish',        # Strongly bullish
    AspectType.OPPOSITION: 'bearish'    # Bearish
}


def calculate_aspect(lon1: float, lon2: float) -> Optional[Tuple[AspectType, float]]:
    """
    Calculate if two planetary longitudes form an aspect.

    Returns:
        Tuple of (AspectType, exactness) or None if no aspect
        exactness is 0 for exact, higher values = less exact
    """
    diff = abs(lon1 - lon2)
    if diff > 180:
        diff = 360 - diff

    for aspect_type in AspectType:
        orb = ASPECT_ORBS[aspect_type]
        if abs(diff - aspect_type.value) <= orb:
            exactness = abs(diff - aspect_type.value)
            return (aspect_type, exactness)

    return None


def get_aspect_strength(exactness: float, orb: float) -> float:
    """Calculate aspect strength (1.0 = exact, 0.0 = at orb edge)."""
    return max(0, 1 - (exactness / orb))


# =====================================================
# PLANET-WISE VEDHA MARKET RULES (from book pp. 467-472)
# =====================================================

@dataclass
class VedhaMarketRule:
    """Represents a vedha market prediction rule from the book."""
    planet: str
    condition: str  # Description of the condition
    target_type: str  # 'nakshatra', 'sign', 'planet', 'mutual'
    target: str  # Specific nakshatra/sign/planet
    additional_condition: Optional[str]  # Additional planet requirement
    market: str  # 'gold', 'silver', 'cotton', 'stock', 'all', 'crypto'
    effect: str  # 'bullish', 'bearish', 'volatile'
    strength: float  # 0.0 to 1.0


# Comprehensive vedha market rules from the book
VEDHA_MARKET_RULES: List[VedhaMarketRule] = [
    # === SUN RULES ===
    VedhaMarketRule('Sun', 'Vedha on Swati/P.Bhadra/Revati', 'nakshatra', 'Swati,Purva Bhadrapada,Revati',
                    None, 'silver', 'bullish', 0.8),
    VedhaMarketRule('Sun', 'Vedha on Anuradha', 'nakshatra', 'Anuradha',
                    None, 'gold', 'bearish', 0.7),
    VedhaMarketRule('Sun', 'Vedha on Pushya/Dhanishta with Mars on Ashlesha', 'nakshatra', 'Pushya,Dhanishta',
                    'Mars in Ashlesha', 'gold', 'volatile', 0.9),
    VedhaMarketRule('Sun', 'Vedha on Aries/Gemini/Leo/Libra/Capricorn/Aquarius', 'sign', 'Aries,Gemini,Leo,Libra,Capricorn,Aquarius',
                    None, 'silver', 'bullish', 0.6),
    VedhaMarketRule('Sun', 'Same vedha on these signs', 'sign', 'Aries,Gemini,Leo,Libra,Capricorn,Aquarius',
                    None, 'stock', 'bearish', 0.6),
    VedhaMarketRule('Sun', 'Mutual vedha with Rahu', 'mutual', 'Rahu',
                    None, 'stock', 'bullish', 0.7),
    VedhaMarketRule('Sun', 'Mutual vedha with Rahu', 'mutual', 'Rahu',
                    None, 'gold', 'bearish', 0.7),
    VedhaMarketRule('Sun', 'Vedha on Taurus', 'sign', 'Taurus',
                    None, 'silver', 'bearish', 0.6),
    VedhaMarketRule('Sun', 'Combined vedha with Mercury (not Aquarius)', 'mutual', 'Mercury',
                    'Not in Aquarius', 'silver', 'bullish', 0.7),
    VedhaMarketRule('Sun', 'Combined vedha with Mars on Libra', 'mutual', 'Mars',
                    'On Libra', 'cotton', 'bullish', 0.7),
    VedhaMarketRule('Sun', 'Vedha on Leo + Saturn vedha on Capricorn', 'sign', 'Leo',
                    'Saturn vedha on Capricorn', 'gold', 'bullish', 0.9),

    # === MOON RULES ===
    VedhaMarketRule('Moon', 'With Mercury, vedha on Taurus/Cancer', 'sign', 'Taurus,Cancer',
                    'With Mercury', 'cotton', 'bearish', 0.7),
    VedhaMarketRule('Moon', 'With Mercury, vedha on Gemini', 'sign', 'Gemini',
                    'With Mercury', 'silver', 'bearish', 0.8),
    VedhaMarketRule('Moon', 'Vedha on Leo', 'sign', 'Leo',
                    None, 'gold', 'bullish', 0.8),
    VedhaMarketRule('Moon', 'Vedha on Leo', 'sign', 'Leo',
                    None, 'cotton', 'bullish', 0.7),
    VedhaMarketRule('Moon', 'Vedha on Scorpio/Pisces', 'sign', 'Scorpio,Pisces',
                    None, 'all', 'bearish', 0.6),
    VedhaMarketRule('Moon', 'Vedha on Sagittarius', 'sign', 'Sagittarius',
                    None, 'all', 'bullish', 0.6),
    VedhaMarketRule('Moon', 'Vedha on Aquarius', 'sign', 'Aquarius',
                    None, 'cotton', 'bullish', 0.7),
    VedhaMarketRule('Moon', 'Vedha on Aquarius', 'sign', 'Aquarius',
                    None, 'stock', 'bullish', 0.7),
    VedhaMarketRule('Moon', 'Vedha on Rahu/Ketu', 'mutual', 'Rahu,Ketu',
                    None, 'silver', 'bullish', 0.7),

    # === MARS RULES ===
    VedhaMarketRule('Mars', 'Vedha while accelerating on Venus', 'mutual', 'Venus',
                    'Mars accelerating', 'cotton', 'bearish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Cancer', 'sign', 'Cancer',
                    None, 'silver', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Cancer', 'sign', 'Cancer',
                    None, 'stock', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Capricorn/Aquarius with Moon transit', 'sign', 'Capricorn,Aquarius',
                    'Moon in same sign', 'all', 'bullish', 0.8),
    VedhaMarketRule('Mars', 'Vedha on Leo', 'sign', 'Leo',
                    None, 'gold', 'bullish', 0.9),
    VedhaMarketRule('Mars', 'Vedha on Venus', 'mutual', 'Venus',
                    None, 'silver', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Saturn', 'mutual', 'Saturn',
                    None, 'cotton', 'bullish', 0.6),
    VedhaMarketRule('Mars', 'Vedha on Saturn', 'mutual', 'Saturn',
                    None, 'stock', 'bearish', 0.8),
    VedhaMarketRule('Mars', 'Mutual vedha with Rahu/Ketu', 'mutual', 'Rahu,Ketu',
                    None, 'stock', 'bearish', 0.7),
    VedhaMarketRule('Mars', 'Mutual vedha with Rahu/Ketu', 'mutual', 'Rahu,Ketu',
                    None, 'silver', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Aries/Libra', 'sign', 'Aries,Libra',
                    None, 'cotton', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Aries/Libra', 'sign', 'Aries,Libra',
                    None, 'stock', 'bullish', 0.6),
    VedhaMarketRule('Mars', 'Vedha on Virgo/Sagittarius', 'sign', 'Virgo,Sagittarius',
                    None, 'silver', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Vedha on Taurus/Leo/Libra/Capricorn', 'sign', 'Taurus,Leo,Libra,Capricorn',
                    None, 'gold', 'bullish', 0.8),
    VedhaMarketRule('Mars', 'Combined vedha with Rahu on Leo', 'mutual', 'Rahu',
                    'On Leo', 'all', 'bullish', 0.8),
    VedhaMarketRule('Mars', 'Mutual vedha with Rahu/Jupiter', 'mutual', 'Rahu,Jupiter',
                    None, 'silver', 'bullish', 0.8),
    VedhaMarketRule('Mars', 'Mutual vedha with Saturn on Gemini/Virgo/Sagittarius', 'mutual', 'Saturn',
                    'On Gemini/Virgo/Sagittarius', 'stock', 'bullish', 0.8),
    VedhaMarketRule('Mars', 'Vedha on Mercury', 'mutual', 'Mercury',
                    None, 'gold', 'bearish', 0.7),
    VedhaMarketRule('Mars', 'Mutual vedha with Venus', 'mutual', 'Venus',
                    None, 'stock', 'bullish', 0.7),
    VedhaMarketRule('Mars', 'Mutual vedha with Jupiter', 'mutual', 'Jupiter',
                    None, 'stock', 'bullish', 0.8),
    VedhaMarketRule('Mars', 'Mutual vedha with Jupiter', 'mutual', 'Jupiter',
                    None, 'cotton', 'bullish', 0.7),

    # === SATURN (representing Jupiter's vedha rules from book) ===
    VedhaMarketRule('Jupiter', 'Vedha on Pushya', 'nakshatra', 'Pushya',
                    None, 'gold', 'bearish', 0.7),
    VedhaMarketRule('Jupiter', 'Vedha on Pushya with Mars in Pushya', 'nakshatra', 'Pushya',
                    'Mars in Pushya', 'gold', 'bearish', 0.9),
    VedhaMarketRule('Jupiter', 'Vedha on Leo with Mars in Leo', 'sign', 'Leo',
                    'Mars in Leo', 'gold', 'bullish', 0.9),
    VedhaMarketRule('Jupiter', 'Vedha on Leo with Mars in Leo', 'sign', 'Leo',
                    'Mars in Leo', 'stock', 'bearish', 0.7),
    VedhaMarketRule('Jupiter', 'Vedha on Virgo + Mars on Ashlesha', 'sign', 'Virgo',
                    'Mars vedha on Ashlesha', 'gold', 'bearish', 0.9),
    VedhaMarketRule('Jupiter', 'Mutual vedha with Venus', 'mutual', 'Venus',
                    None, 'silver', 'bearish', 0.7),
    VedhaMarketRule('Jupiter', 'Mutual vedha with Venus', 'mutual', 'Venus',
                    None, 'cotton', 'bearish', 0.6),
    VedhaMarketRule('Jupiter', 'Vedha on Punarvasu/Chitra/Hasta/Shatabhisha', 'nakshatra', 'Punarvasu,Chitra,Hasta,Shatabhisha',
                    None, 'gold', 'bearish', 0.7),
    VedhaMarketRule('Jupiter', 'Vedha with Rahu on any nakshatra', 'mutual', 'Rahu',
                    None, 'gold', 'bearish', 0.8),
    VedhaMarketRule('Jupiter', 'Mutual vedha with Venus', 'mutual', 'Venus',
                    None, 'silver', 'bullish', 0.8),
    VedhaMarketRule('Jupiter', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'silver', 'bearish', 0.7),
    VedhaMarketRule('Jupiter', 'Mutual vedha with Rahu/Ketu', 'mutual', 'Rahu,Ketu',
                    None, 'all', 'volatile', 0.8),

    # === MERCURY RULES ===
    VedhaMarketRule('Mercury', 'Vedha on Shatabhisha + Mars on Chitra', 'nakshatra', 'Shatabhisha',
                    'Mars vedha on Chitra', 'gold', 'bullish', 0.8),
    VedhaMarketRule('Mercury', 'Vedha on Shatabhisha + Mars on Chitra', 'nakshatra', 'Shatabhisha',
                    'Mars vedha on Chitra', 'wheat', 'bullish', 0.7),
    VedhaMarketRule('Mercury', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'silver', 'bearish', 0.6),
    VedhaMarketRule('Mercury', 'Vedha on Krittika/Punarvasu/Ardra/Hasta/Vishakha/Purva Ashadha', 'nakshatra',
                    'Krittika,Punarvasu,Ardra,Hasta,Vishakha,Purva Ashadha',
                    None, 'gold', 'bearish', 0.7),

    # === VENUS RULES ===
    VedhaMarketRule('Venus', 'Mutual vedha on Rahu', 'mutual', 'Rahu',
                    None, 'stock', 'bearish', 0.8),
    VedhaMarketRule('Venus', 'Mutual vedha on Rahu', 'mutual', 'Rahu',
                    None, 'silver', 'bearish', 0.7),
    VedhaMarketRule('Venus', 'Mutual vedha on Jupiter', 'mutual', 'Jupiter',
                    None, 'silver', 'bullish', 0.8),
    VedhaMarketRule('Venus', 'Vedha on Cancer/Sagittarius', 'sign', 'Cancer,Sagittarius',
                    None, 'stock', 'bullish', 0.7),
    VedhaMarketRule('Venus', 'Vedha on Leo', 'sign', 'Leo',
                    None, 'gold', 'bullish', 0.7),
    VedhaMarketRule('Venus', 'Vedha on Leo', 'sign', 'Leo',
                    None, 'stock', 'bearish', 0.6),
    VedhaMarketRule('Venus', 'Vedha on Libra', 'sign', 'Libra',
                    None, 'silver', 'bullish', 0.7),
    VedhaMarketRule('Venus', 'Vedha from Rahu/Ketu', 'mutual', 'Rahu,Ketu',
                    None, 'silver', 'bullish', 0.7),

    # === SATURN RULES ===
    VedhaMarketRule('Saturn', 'Vedha on Capricorn', 'sign', 'Capricorn',
                    None, 'silver', 'bullish', 0.8),
    VedhaMarketRule('Saturn', 'Mutual vedha with Mars', 'mutual', 'Mars',
                    None, 'stock', 'bearish', 0.9),
    VedhaMarketRule('Saturn', 'Vedha on Mula/Uttara Ashadha/Shatabhisha', 'nakshatra', 'Mula,Uttara Ashadha,Shatabhisha',
                    None, 'all', 'bullish', 0.8),  # Crop failure causes rise
    VedhaMarketRule('Saturn', 'With Rahu/Ketu vedha on Aries/Capricorn', 'sign', 'Aries,Capricorn',
                    'Rahu/Ketu vedha', 'silver', 'bullish', 0.8),
    VedhaMarketRule('Saturn', 'With Rahu/Ketu vedha on Aries/Capricorn', 'sign', 'Aries,Capricorn',
                    'Rahu/Ketu vedha', 'cotton', 'bullish', 0.7),
    VedhaMarketRule('Saturn', 'Vedha on Aquarius', 'sign', 'Aquarius',
                    None, 'silver', 'bullish', 0.7),
    VedhaMarketRule('Saturn', 'Vedha on Aquarius', 'sign', 'Aquarius',
                    None, 'stock', 'bullish', 0.7),

    # === RAHU/KETU RULES ===
    VedhaMarketRule('Rahu', 'Vedha on Punarvasu/Uttara Phalguni/Chitra/Uttara Bhadrapada', 'nakshatra',
                    'Punarvasu,Uttara Phalguni,Chitra,Uttara Bhadrapada',
                    None, 'all', 'bullish', 0.8),  # Inflationary
    VedhaMarketRule('Rahu', 'Vedha on Gemini/Virgo/Scorpio/Capricorn', 'sign', 'Gemini,Virgo,Scorpio,Capricorn',
                    None, 'stock', 'bullish', 0.8),
    VedhaMarketRule('Rahu', 'Vedha on Gemini/Cancer', 'sign', 'Gemini,Cancer',
                    None, 'silver', 'bearish', 0.7),
    VedhaMarketRule('Rahu', 'Vedha on Gemini/Cancer', 'sign', 'Gemini,Cancer',
                    None, 'cotton', 'bearish', 0.7),
    VedhaMarketRule('Rahu', 'Vedha on Aquarius/Pisces', 'sign', 'Aquarius,Pisces',
                    None, 'cotton', 'bearish', 0.6),
    VedhaMarketRule('Rahu', 'Mutual vedha with Jupiter/Mercury', 'mutual', 'Jupiter,Mercury',
                    None, 'silver', 'bearish', 0.7),
    VedhaMarketRule('Rahu', 'Vedha on Libra/Scorpio/Sagittarius', 'sign', 'Libra,Scorpio,Sagittarius',
                    None, 'all', 'bullish', 0.7),  # Scarcity, panic buying
    VedhaMarketRule('Rahu', 'Mutual vedha with Jupiter/Saturn/Mars', 'mutual', 'Jupiter,Saturn,Mars',
                    None, 'all', 'volatile', 0.8),

    # Ketu follows similar rules as Rahu
    VedhaMarketRule('Ketu', 'Vedha on Punarvasu/Uttara Phalguni/Chitra/Uttara Bhadrapada', 'nakshatra',
                    'Punarvasu,Uttara Phalguni,Chitra,Uttara Bhadrapada',
                    None, 'all', 'bullish', 0.8),
    VedhaMarketRule('Ketu', 'Vedha on Gemini/Virgo/Scorpio/Capricorn', 'sign', 'Gemini,Virgo,Scorpio,Capricorn',
                    None, 'stock', 'bullish', 0.8),

    # === URANUS (Herschel) RULES - From MK Agarwal p. 61 ===
    # General: Mandi (bearish). With benefic = Mandi. With malefic = Teji.
    VedhaMarketRule('Uranus', 'Transit in Aquarius (own sign)', 'sign', 'Aquarius',
                    None, 'crypto', 'bullish', 0.9),  # Technology, innovation
    VedhaMarketRule('Uranus', 'Transit in Aquarius', 'sign', 'Aquarius',
                    None, 'stock', 'volatile', 0.7),
    VedhaMarketRule('Uranus', 'Transit in Scorpio', 'sign', 'Scorpio',
                    None, 'crypto', 'bullish', 0.8),  # Hidden wealth, transformation
    VedhaMarketRule('Uranus', 'Mutual vedha with Jupiter', 'mutual', 'Jupiter',
                    None, 'stock', 'bullish', 0.8),  # Sudden Teji from MK Agarwal
    VedhaMarketRule('Uranus', 'Mutual vedha with Saturn', 'mutual', 'Saturn',
                    None, 'all', 'volatile', 0.8),
    VedhaMarketRule('Uranus', 'Transit in Cancer/Libra/Pisces', 'sign', 'Cancer,Libra,Pisces',
                    None, 'gold', 'bearish', 0.6),  # Bearish for traditional
    VedhaMarketRule('Uranus', 'Transit in Cancer/Libra/Pisces', 'sign', 'Cancer,Libra,Pisces',
                    None, 'silver', 'bearish', 0.6),

    # === NEPTUNE RULES - From MK Agarwal p. 61 ===
    # General: Teji (bullish). With malefic = Teji. With benefic = Mandi.
    VedhaMarketRule('Neptune', 'Transit in Pisces (own sign)', 'sign', 'Pisces',
                    None, 'all', 'bullish', 0.8),  # Strong in own sign
    VedhaMarketRule('Neptune', 'Transit in Pisces', 'sign', 'Pisces',
                    None, 'crypto', 'bullish', 0.9),
    VedhaMarketRule('Neptune', 'Transit in water signs', 'sign', 'Cancer,Scorpio,Pisces',
                    None, 'silver', 'bullish', 0.7),  # Liquids, silver
    VedhaMarketRule('Neptune', 'Mutual vedha with Saturn', 'mutual', 'Saturn',
                    None, 'all', 'bullish', 0.8),  # Teji due to shortage
    VedhaMarketRule('Neptune', 'Mutual vedha with Mars', 'mutual', 'Mars',
                    None, 'all', 'bullish', 0.7),
    VedhaMarketRule('Neptune', 'Mutual vedha with Venus', 'mutual', 'Venus',
                    None, 'all', 'bearish', 0.6),  # With benefic = Mandi

    # === PLUTO RULES - From MK Agarwal p. 61, 87 ===
    # Significations: Medicines, weapons, mines, transformation, hidden wealth
    VedhaMarketRule('Pluto', 'Transit in Capricorn', 'sign', 'Capricorn',
                    None, 'stock', 'bullish', 0.8),  # Institutions, power
    VedhaMarketRule('Pluto', 'Transit in Capricorn', 'sign', 'Capricorn',
                    None, 'gold', 'bullish', 0.8),
    VedhaMarketRule('Pluto', 'Transit in Aquarius', 'sign', 'Aquarius',
                    None, 'crypto', 'bullish', 0.9),  # Revolution, innovation
    VedhaMarketRule('Pluto', 'Transit in Scorpio (own sign)', 'sign', 'Scorpio',
                    None, 'crypto', 'bullish', 0.9),  # Hidden wealth, transformation
    VedhaMarketRule('Pluto', 'Mutual vedha with Venus', 'mutual', 'Venus',
                    None, 'all', 'bullish', 0.8),  # Sk + Pluto = Teji
    VedhaMarketRule('Pluto', 'Mutual vedha with Mars', 'mutual', 'Mars',
                    None, 'all', 'volatile', 0.8),
    VedhaMarketRule('Pluto', 'Transit in earth signs', 'sign', 'Taurus,Virgo,Capricorn',
                    None, 'gold', 'bullish', 0.7),  # Hidden wealth, mining
]

# =====================================================
# CRYPTO/BTC SPECIFIC RULES (Modern interpretation)
# =====================================================

# BTC birth data (Jan 3, 2009, 18:15 UTC)
BTC_BIRTH_NAKSHATRA = 'Uttara Bhadrapada'
BTC_BIRTH_NAKSHATRA_IDX = 25
BTC_BIRTH_RASHI = 'Pisces'
BTC_BIRTH_RASHI_IDX = 11

# Planets that strongly influence crypto (modern interpretation)
CRYPTO_RULING_PLANETS = ['Rahu', 'Uranus', 'Saturn', 'Jupiter']

# BTC/Crypto specific vedha rules
CRYPTO_VEDHA_RULES: List[VedhaMarketRule] = [
    # Rahu rules innovation, technology, sudden gains
    VedhaMarketRule('Rahu', 'Vedha on Uttara Bhadrapada (BTC birth)', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'crypto', 'volatile', 0.9),
    VedhaMarketRule('Rahu', 'Vedha on Aquarius (tech)', 'sign', 'Aquarius',
                    None, 'crypto', 'bullish', 0.8),
    VedhaMarketRule('Rahu', 'Vedha on Pisces (BTC rashi)', 'sign', 'Pisces',
                    None, 'crypto', 'bullish', 0.8),

    # Saturn for long-term value, institutional adoption
    VedhaMarketRule('Saturn', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'crypto', 'bearish', 0.8),  # Restrictions, regulations
    VedhaMarketRule('Saturn', 'Vedha on Aquarius', 'sign', 'Aquarius',
                    None, 'crypto', 'volatile', 0.7),

    # Jupiter for expansion, mainstream adoption
    VedhaMarketRule('Jupiter', 'Vedha on Pisces', 'sign', 'Pisces',
                    None, 'crypto', 'bullish', 0.9),
    VedhaMarketRule('Jupiter', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'crypto', 'bullish', 0.8),
    VedhaMarketRule('Jupiter', 'Mutual vedha with Rahu', 'mutual', 'Rahu',
                    None, 'crypto', 'volatile', 0.9),

    # Mars for volatility, trading volume
    VedhaMarketRule('Mars', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'crypto', 'volatile', 0.8),
    VedhaMarketRule('Mars', 'Vedha on Scorpio', 'sign', 'Scorpio',
                    None, 'crypto', 'bullish', 0.7),

    # Sun for visibility, mainstream attention
    VedhaMarketRule('Sun', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'crypto', 'bullish', 0.7),

    # Mercury for trading, exchanges
    VedhaMarketRule('Mercury', 'Vedha on Uttara Bhadrapada', 'nakshatra', 'Uttara Bhadrapada',
                    None, 'crypto', 'volatile', 0.6),
    VedhaMarketRule('Mercury', 'Retrograde with vedha on crypto nakshatras', 'nakshatra',
                    'Shatabhisha,Purva Bhadrapada,Uttara Bhadrapada',
                    'Mercury retrograde', 'crypto', 'bearish', 0.7),
]


# =====================================================
# MUTUAL VEDHA DETECTION
# =====================================================

def check_mutual_vedha(planet1_nak_idx: int, planet2_nak_idx: int,
                       vedha_mapping: Dict[int, List[int]]) -> bool:
    """
    Check if two planets are in mutual vedha (each causing vedha to the other).

    Args:
        planet1_nak_idx: Nakshatra index of planet 1
        planet2_nak_idx: Nakshatra index of planet 2
        vedha_mapping: NAKSHATRA_VEDHA from sbc_analysis

    Returns:
        True if mutual vedha exists
    """
    # Check if planet1 causes vedha to planet2's nakshatra
    p1_vedha_targets = vedha_mapping.get(planet1_nak_idx, [])
    p1_vedhas_p2 = planet2_nak_idx in p1_vedha_targets

    # Check if planet2 causes vedha to planet1's nakshatra
    p2_vedha_targets = vedha_mapping.get(planet2_nak_idx, [])
    p2_vedhas_p1 = planet1_nak_idx in p2_vedha_targets

    return p1_vedhas_p2 and p2_vedhas_p1


def find_all_mutual_vedhas(planetary_positions: Dict,
                           vedha_mapping: Dict[int, List[int]]) -> List[Dict]:
    """
    Find all mutual vedhas between planets.

    Args:
        planetary_positions: Dict of planet -> position data
        vedha_mapping: NAKSHATRA_VEDHA from sbc_analysis

    Returns:
        List of mutual vedha info dicts
    """
    mutual_vedhas = []
    planets = list(planetary_positions.keys())

    for i, p1 in enumerate(planets):
        for p2 in planets[i+1:]:
            p1_nak_idx = planetary_positions[p1].get('nakshatra_idx')
            p2_nak_idx = planetary_positions[p2].get('nakshatra_idx')

            if p1_nak_idx is not None and p2_nak_idx is not None:
                if check_mutual_vedha(p1_nak_idx, p2_nak_idx, vedha_mapping):
                    mutual_vedhas.append({
                        'planet1': p1,
                        'planet2': p2,
                        'planet1_nakshatra': planetary_positions[p1].get('nakshatra'),
                        'planet2_nakshatra': planetary_positions[p2].get('nakshatra'),
                        'description': f"{p1} and {p2} in mutual vedha"
                    })

    return mutual_vedhas


# =====================================================
# MARKET PREDICTION ENGINE
# =====================================================

@dataclass
class MarketPrediction:
    """Represents a market prediction."""
    market: str  # 'gold', 'silver', 'stock', 'crypto', 'all'
    direction: str  # 'bullish', 'bearish', 'volatile', 'neutral'
    strength: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    factors: List[str]  # List of contributing factors
    details: Dict  # Additional details


def get_sign_from_longitude(longitude: float) -> Tuple[int, str]:
    """Get sign index and name from longitude."""
    sign_idx = int(longitude / 30) % 12
    sign_names = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    return sign_idx, sign_names[sign_idx]


def get_planet_strength_modifier(planet: str, planet_pos: Dict,
                                  sun_lon: float) -> Tuple[float, List[str]]:
    """
    Calculate planet strength modifier based on retrograde/combustion.

    Returns:
        Tuple of (multiplier, list of conditions)
    """
    multiplier = 1.0
    conditions = []

    planet_lon = planet_pos.get('longitude', 0)

    # Check combustion (strength = 0)
    if is_planet_combust(planet, planet_lon, sun_lon):
        conditions.append(f'{planet} combust (strength reduced)')
        # Combustion doesn't eliminate effect but reduces it
        # Per MK Agarwal, combust planet = 0 numerical strength
        # But for market predictions, combust Mercury/Jupiter = Teji
        if planet in ['Mercury', 'Jupiter']:
            multiplier = 1.5  # Teji continues while combust
            conditions[-1] = f'{planet} combust (Teji continues)'
        else:
            multiplier = 0.3  # Reduced effect

    # Check retrograde (200% strength)
    if planet_pos.get('retrograde', False):
        multiplier *= RETROGRADE_MULTIPLIER
        conditions.append(f'{planet} retrograde (200% strength)')

    return multiplier, conditions


def evaluate_planet_rasi_commodity_effects(planetary_positions: Dict,
                                            market_type: str) -> Tuple[float, float, List[str]]:
    """
    Evaluate planet-in-rasi commodity price effects from MK Agarwal.

    Returns:
        Tuple of (bullish_score, bearish_score, factors)
    """
    bullish_score = 0.0
    bearish_score = 0.0
    factors = []

    # Map market types to commodity keywords
    market_commodities = {
        'gold': ['gold', 'metals', 'copper', 'brass', 'steel', 'gems', 'diamond', 'pearl'],
        'silver': ['silver', 'metals'],
        'stock': ['shares', 'stock', 'animals'],  # Animals = livestock/commodities trading
        'crypto': ['gold', 'silver', 'technology', 'metals'],  # Crypto correlates with gold/tech
    }

    target_commodities = market_commodities.get(market_type, [])

    for planet, pos in planetary_positions.items():
        if planet not in PLANET_RASI_COMMODITY_RULES:
            continue

        sign_idx, sign_name = get_sign_from_longitude(pos.get('longitude', 0))
        rasi_rules = PLANET_RASI_COMMODITY_RULES[planet].get(sign_idx, {})

        rise_commodities = rasi_rules.get('rise', [])
        fall_commodities = rasi_rules.get('fall', [])

        # Check if any target commodities are in rise/fall lists
        for comm in target_commodities:
            if any(comm.lower() in rc.lower() for rc in rise_commodities):
                bullish_score += 0.4
                factors.append(f'RASI: {planet} in {sign_name} → rise in {comm}')
                break
            if any(comm.lower() in fc.lower() for fc in fall_commodities):
                bearish_score += 0.4
                factors.append(f'RASI: {planet} in {sign_name} → fall in {comm}')
                break

    return bullish_score, bearish_score, factors


def evaluate_nakshatra_commodity_vedha(planetary_positions: Dict,
                                        vedha_mapping: Dict[int, List[int]],
                                        market_type: str) -> Tuple[float, float, List[str]]:
    """
    Evaluate nakshatra-commodity vedha effects.
    Malefic vedha = Teji (price rise)
    Benefic vedha = Mandi (price fall)

    Returns:
        Tuple of (bullish_score, bearish_score, factors)
    """
    bullish_score = 0.0
    bearish_score = 0.0
    factors = []

    # Malefic planets
    malefic_planets = ['Sun', 'Saturn', 'Mars', 'Rahu', 'Ketu']
    # Benefic planets
    benefic_planets = ['Moon', 'Mercury', 'Jupiter', 'Venus']

    # Market-relevant commodities
    market_commodities = {
        'gold': ['gold', 'gems', 'diamond', 'metals'],
        'silver': ['silver', 'metals', 'pearls'],
        'stock': ['shares', 'animals', 'grains'],
        'crypto': ['gold', 'silver', 'metals', 'gems'],  # Crypto correlates
    }

    target_commodities = set(market_commodities.get(market_type, []))

    for planet, pos in planetary_positions.items():
        planet_nak_idx = pos.get('nakshatra_idx')
        planet_nak = pos.get('nakshatra')
        if planet_nak_idx is None:
            continue

        # Get vedha targets for this planet's nakshatra
        vedha_targets = vedha_mapping.get(planet_nak_idx, [])

        for target_idx in vedha_targets:
            # Find target nakshatra name
            target_nak = NAKSHATRA_NAMES[target_idx] if target_idx < len(NAKSHATRA_NAMES) else None
            if not target_nak:
                continue

            # Get commodities ruled by target nakshatra
            nak_rules = NAKSHATRA_COMMODITY_RULES.get(target_nak, {})
            nak_commodities = set(nak_rules.get('commodities', []))

            # Check if any overlap with market commodities
            overlap = target_commodities & nak_commodities
            if overlap:
                is_malefic = planet in malefic_planets
                if is_malefic:
                    # Malefic vedha = price RISE
                    bullish_score += 0.3
                    factors.append(f'VEDHA: {planet}(malefic) → {target_nak} → rise in {list(overlap)[0]}')
                else:
                    # Benefic vedha = price FALL
                    bearish_score += 0.3
                    factors.append(f'VEDHA: {planet}(benefic) → {target_nak} → fall in {list(overlap)[0]}')

    return bullish_score, bearish_score, factors


def evaluate_market_rules(planetary_positions: Dict,
                          vedha_mapping: Dict[int, List[int]],
                          active_vedhas: List[Dict],
                          market_type: str = 'crypto') -> MarketPrediction:
    """
    Evaluate all market rules and generate prediction.
    Enhanced with MK Agarwal rules for planet-rasi effects, retrograde/combustion.

    Args:
        planetary_positions: Dict of planet -> position data
        vedha_mapping: NAKSHATRA_VEDHA from sbc_analysis
        active_vedhas: List of active vedhas from SBC analysis
        market_type: 'gold', 'silver', 'stock', 'crypto', 'all'

    Returns:
        MarketPrediction with combined analysis
    """
    bullish_score = 0.0
    bearish_score = 0.0
    volatile_score = 0.0
    factors = []
    strength_conditions = []

    # Get Sun longitude for combustion checks
    sun_pos = planetary_positions.get('Sun', {})
    sun_lon = sun_pos.get('longitude', 0)

    # === NEW: Evaluate planet-in-rasi commodity effects (MK Agarwal) ===
    rasi_bull, rasi_bear, rasi_factors = evaluate_planet_rasi_commodity_effects(
        planetary_positions, market_type
    )
    bullish_score += rasi_bull
    bearish_score += rasi_bear
    factors.extend(rasi_factors[:3])  # Limit to top 3

    # === NEW: Evaluate nakshatra-commodity vedha effects ===
    nak_bull, nak_bear, nak_factors = evaluate_nakshatra_commodity_vedha(
        planetary_positions, vedha_mapping, market_type
    )
    bullish_score += nak_bull
    bearish_score += nak_bear
    factors.extend(nak_factors[:3])  # Limit to top 3

    # Select appropriate rules
    rules = VEDHA_MARKET_RULES.copy()
    if market_type == 'crypto':
        rules.extend(CRYPTO_VEDHA_RULES)

    # Check each rule
    for rule in rules:
        if rule.market != market_type and rule.market != 'all':
            continue

        rule_triggered = False

        # Get planet position
        planet_pos = planetary_positions.get(rule.planet)
        if not planet_pos:
            continue

        planet_nak = planet_pos.get('nakshatra')
        planet_nak_idx = planet_pos.get('nakshatra_idx')
        planet_sign_idx, planet_sign = get_sign_from_longitude(planet_pos.get('longitude', 0))

        # === NEW: Get strength modifier for retrograde/combustion ===
        strength_mult, conds = get_planet_strength_modifier(rule.planet, planet_pos, sun_lon)
        strength_conditions.extend(conds)

        if rule.target_type == 'nakshatra':
            # Check if planet's vedha targets include the specified nakshatra(s)
            target_nakshatras = [n.strip() for n in rule.target.split(',')]
            vedha_targets = vedha_mapping.get(planet_nak_idx, [])

            for target_nak in target_nakshatras:
                target_idx = NAKSHATRA_TO_IDX.get(target_nak)
                # Also check alternate index mapping
                if target_idx is None:
                    target_idx = NAKSHATRA_TO_IDX_27.get(target_nak)
                if target_idx is not None and target_idx in vedha_targets:
                    rule_triggered = True
                    break

        elif rule.target_type == 'sign':
            # Check if planet causes vedha to cells in the specified sign(s)
            target_signs = [s.strip() for s in rule.target.split(',')]
            if planet_sign in target_signs:
                rule_triggered = True

        elif rule.target_type == 'mutual':
            # Check for mutual vedha with specified planet(s)
            target_planets = [p.strip() for p in rule.target.split(',')]
            for target_planet in target_planets:
                target_pos = planetary_positions.get(target_planet)
                if target_pos:
                    target_nak_idx = target_pos.get('nakshatra_idx')
                    if target_nak_idx and planet_nak_idx:
                        if check_mutual_vedha(planet_nak_idx, target_nak_idx, vedha_mapping):
                            rule_triggered = True
                            break

        if rule_triggered:
            # Apply rule effect with strength modifier
            effect_score = rule.strength * strength_mult

            if rule.effect == 'bullish':
                bullish_score += effect_score
                factors.append(f"BULLISH: {rule.planet} - {rule.condition}")
            elif rule.effect == 'bearish':
                bearish_score += effect_score
                factors.append(f"BEARISH: {rule.planet} - {rule.condition}")
            elif rule.effect == 'volatile':
                volatile_score += effect_score
                factors.append(f"VOLATILE: {rule.planet} - {rule.condition}")

    # Check western aspects for additional signals
    aspect_factors = []
    planets = list(planetary_positions.keys())
    for i, p1 in enumerate(planets):
        for p2 in planets[i+1:]:
            lon1 = planetary_positions[p1].get('longitude', 0)
            lon2 = planetary_positions[p2].get('longitude', 0)

            aspect = calculate_aspect(lon1, lon2)
            if aspect:
                aspect_type, exactness = aspect
                strength = get_aspect_strength(exactness, ASPECT_ORBS[aspect_type])

                if strength > 0.5:  # Only consider strong aspects
                    effect = ASPECT_EFFECTS[aspect_type]
                    if effect == 'bullish':
                        bullish_score += strength * 0.3
                        aspect_factors.append(f"{p1}-{p2} {aspect_type.name} (bullish)")
                    elif effect == 'bearish':
                        bearish_score += strength * 0.3
                        aspect_factors.append(f"{p1}-{p2} {aspect_type.name} (bearish)")

    if aspect_factors:
        factors.append(f"ASPECTS: {', '.join(aspect_factors[:3])}")

    # Check sign classifications
    planets_in_bullish = 0
    planets_in_bearish = 0
    for planet, pos in planetary_positions.items():
        sign_idx, _ = get_sign_from_longitude(pos.get('longitude', 0))
        if sign_idx in BULLISH_SIGNS:
            planets_in_bullish += 1
        elif sign_idx in BEARISH_SIGNS:
            planets_in_bearish += 1

    if planets_in_bullish > planets_in_bearish + 2:
        bullish_score += 0.5
        factors.append(f"SIGN BALANCE: {planets_in_bullish} planets in bullish signs")
    elif planets_in_bearish > planets_in_bullish + 2:
        bearish_score += 0.5
        factors.append(f"SIGN BALANCE: {planets_in_bearish} planets in bearish signs")

    # Calculate final direction
    total_score = bullish_score + bearish_score + volatile_score
    if total_score == 0:
        direction = 'neutral'
        strength = 0.0
        confidence = 0.0
    else:
        if volatile_score > bullish_score and volatile_score > bearish_score:
            direction = 'volatile'
            strength = volatile_score / total_score
        elif bullish_score > bearish_score:
            direction = 'bullish'
            strength = (bullish_score - bearish_score) / total_score
        elif bearish_score > bullish_score:
            direction = 'bearish'
            strength = (bearish_score - bullish_score) / total_score
        else:
            direction = 'neutral'
            strength = 0.0

        confidence = min(1.0, total_score / 5.0)  # Normalize confidence

    # Add strength conditions if any
    if strength_conditions:
        unique_conditions = list(set(strength_conditions))
        factors.append(f"MODIFIERS: {', '.join(unique_conditions[:3])}")

    return MarketPrediction(
        market=market_type,
        direction=direction,
        strength=round(strength, 2),
        confidence=round(confidence, 2),
        factors=factors,
        details={
            'bullish_score': round(bullish_score, 2),
            'bearish_score': round(bearish_score, 2),
            'volatile_score': round(volatile_score, 2),
            'planets_in_bullish_signs': planets_in_bullish,
            'planets_in_bearish_signs': planets_in_bearish,
            'strength_modifiers': list(set(strength_conditions))
        }
    )


def get_comprehensive_market_analysis(planetary_positions: Dict,
                                       vedha_mapping: Dict[int, List[int]],
                                       active_vedhas: List[Dict]) -> Dict:
    """
    Get comprehensive market analysis for all market types.

    Args:
        planetary_positions: Dict of planet -> position data
        vedha_mapping: NAKSHATRA_VEDHA from sbc_analysis
        active_vedhas: List of active vedhas

    Returns:
        Dict with predictions for each market type
    """
    # Find mutual vedhas
    mutual_vedhas = find_all_mutual_vedhas(planetary_positions, vedha_mapping)

    # Get predictions for each market
    predictions = {}
    for market in ['crypto', 'gold', 'silver', 'stock']:
        pred = evaluate_market_rules(
            planetary_positions, vedha_mapping, active_vedhas, market
        )
        predictions[market] = {
            'direction': pred.direction,
            'strength': pred.strength,
            'confidence': pred.confidence,
            'factors': pred.factors,
            'details': pred.details
        }

    # Calculate overall market sentiment
    bullish_count = sum(1 for p in predictions.values() if p['direction'] == 'bullish')
    bearish_count = sum(1 for p in predictions.values() if p['direction'] == 'bearish')

    if bullish_count > bearish_count:
        overall = 'bullish'
    elif bearish_count > bullish_count:
        overall = 'bearish'
    else:
        overall = 'mixed'

    return {
        'predictions': predictions,
        'mutual_vedhas': mutual_vedhas,
        'overall_sentiment': overall,
        'summary': generate_market_summary(predictions, mutual_vedhas)
    }


def generate_market_summary(predictions: Dict, mutual_vedhas: List[Dict]) -> str:
    """Generate human-readable market summary."""
    lines = ["=== SBC Market Analysis ===\n"]

    for market, pred in predictions.items():
        emoji = {'bullish': '📈', 'bearish': '📉', 'volatile': '⚡', 'neutral': '➖'}
        lines.append(f"{market.upper()}: {emoji.get(pred['direction'], '❓')} {pred['direction'].upper()}")
        lines.append(f"  Strength: {pred['strength']:.0%}, Confidence: {pred['confidence']:.0%}")
        if pred['factors']:
            lines.append(f"  Key factors: {pred['factors'][0]}")
        lines.append("")

    if mutual_vedhas:
        lines.append("MUTUAL VEDHAS (amplified effects):")
        for mv in mutual_vedhas[:3]:
            lines.append(f"  • {mv['planet1']} ↔ {mv['planet2']}")

    return "\n".join(lines)


# =====================================================
# VEDHA WEIGHT CALCULATION SYSTEM
# Based on P.K. Vasudev & MK Agarwal rules
# =====================================================

# Base planet weights (influence strength)
PLANET_BASE_WEIGHT = {
    'Sun': 1.0,      # Moderate influence
    'Moon': 0.8,     # Daily fluctuations
    'Mars': 1.2,     # Strong volatile influence
    'Mercury': 0.9,  # Trade/commerce regulator
    'Jupiter': 1.5,  # Major expansion/contraction
    'Venus': 1.1,    # Precious metals, sudden moves
    'Saturn': 1.4,   # Long-term trends, fear factor
    'Rahu': 1.3,     # Speculation, manipulation
    'Ketu': 1.0,     # Sudden events
    'Uranus': 1.2,   # Innovation, volatility
    'Neptune': 1.0,  # Speculation, illusion
    'Pluto': 1.1     # Transformation
}

# Strength modifiers
EXALTED_MULTIPLIER = 1.5         # 150% in exaltation
DEBILITATED_MULTIPLIER = 0.5     # 50% in debilitation
OWN_SIGN_MULTIPLIER = 1.25       # 125% in own sign
COMBUST_MULTIPLIER = 0.25        # 25% when combust (near Sun)
ACCELERATED_MULTIPLIER = 1.3     # 130% when moving fast

# Exaltation signs
EXALTATION = {
    'Sun': 'Aries', 'Moon': 'Taurus', 'Mars': 'Capricorn',
    'Mercury': 'Virgo', 'Jupiter': 'Cancer', 'Venus': 'Pisces',
    'Saturn': 'Libra', 'Rahu': 'Taurus', 'Ketu': 'Scorpio'
}

# Debilitation signs
DEBILITATION = {
    'Sun': 'Libra', 'Moon': 'Scorpio', 'Mars': 'Cancer',
    'Mercury': 'Pisces', 'Jupiter': 'Capricorn', 'Venus': 'Virgo',
    'Saturn': 'Aries', 'Rahu': 'Scorpio', 'Ketu': 'Taurus'
}

# Own signs
OWN_SIGNS = {
    'Sun': ['Leo'], 'Moon': ['Cancer'], 'Mars': ['Aries', 'Scorpio'],
    'Mercury': ['Gemini', 'Virgo'], 'Jupiter': ['Sagittarius', 'Pisces'],
    'Venus': ['Taurus', 'Libra'], 'Saturn': ['Capricorn', 'Aquarius'],
    'Rahu': ['Aquarius'], 'Ketu': ['Scorpio']
}

# Average daily motions (for accelerated motion detection)
AVERAGE_DAILY_MOTION = {
    'Moon': 13.0, 'Sun': 1.0, 'Mercury': 1.2, 'Venus': 1.0,
    'Mars': 0.5, 'Jupiter': 0.08, 'Saturn': 0.03
}

# Vedha type weights
VEDHA_TYPE_WEIGHT = {
    'front': 1.0,    # Direct/front vedha - full strength
    'left': 0.8,     # Left vedha (retrograde) - 80%
    'right': 0.8,    # Right vedha (direct fast) - 80%
}

# Malefic and Benefic classifications
MALEFIC_PLANETS = ['Sun', 'Mars', 'Saturn', 'Rahu', 'Ketu']
BENEFIC_PLANETS = ['Moon', 'Mercury', 'Jupiter', 'Venus']


def calculate_planet_strength(planet: str, rasi: str, is_retrograde: bool,
                              speed: float, sun_longitude: float,
                              planet_longitude: float) -> tuple:
    """
    Calculate total strength multiplier for a planet based on various factors.

    Returns:
        tuple: (strength_multiplier, list_of_modifiers)
    """
    strength = PLANET_BASE_WEIGHT.get(planet, 1.0)
    modifiers = []

    # Retrograde - 200% strength
    if is_retrograde:
        strength *= RETROGRADE_MULTIPLIER
        modifiers.append(f'Retrograde ({RETROGRADE_MULTIPLIER}x)')

    # Exaltation/Debilitation/Own Sign
    if EXALTATION.get(planet) == rasi:
        strength *= EXALTED_MULTIPLIER
        modifiers.append(f'Exalted ({EXALTED_MULTIPLIER}x)')
    elif DEBILITATION.get(planet) == rasi:
        strength *= DEBILITATED_MULTIPLIER
        modifiers.append(f'Debilitated ({DEBILITATED_MULTIPLIER}x)')
    elif rasi in OWN_SIGNS.get(planet, []):
        strength *= OWN_SIGN_MULTIPLIER
        modifiers.append(f'Own Sign ({OWN_SIGN_MULTIPLIER}x)')

    # Combustion check
    if planet in COMBUSTION_ORBS and planet != 'Sun':
        orb = COMBUSTION_ORBS[planet]
        diff = abs(planet_longitude - sun_longitude)
        if diff > 180:
            diff = 360 - diff
        if diff <= orb:
            strength *= COMBUST_MULTIPLIER
            modifiers.append(f'Combust ({diff:.1f}° from Sun, {COMBUST_MULTIPLIER}x)')

    # Accelerated motion check
    if planet in AVERAGE_DAILY_MOTION:
        avg_speed = AVERAGE_DAILY_MOTION[planet]
        if abs(speed) > avg_speed * 1.2:
            strength *= ACCELERATED_MULTIPLIER
            modifiers.append(f'Accelerated ({ACCELERATED_MULTIPLIER}x)')

    return strength, modifiers


def get_vedha_target_nakshatra(source_nak_idx: int, vedha_type: str = 'front') -> int:
    """
    Get the target nakshatra index for a vedha.
    Front vedha = 16th nakshatra from source (index + 15 in 27-nak system)
    """
    if vedha_type == 'front':
        return (source_nak_idx + 15) % 27
    elif vedha_type == 'left':
        return (source_nak_idx - 1) % 27
    elif vedha_type == 'right':
        return (source_nak_idx + 1) % 27
    return source_nak_idx


def calculate_vedha_weights(planetary_positions: Dict, asset_type: str = 'crypto') -> Dict:
    """
    Calculate positive (TEJI) and negative (MANDI) vedha weights.

    Args:
        planetary_positions: Dict with planet data including:
            - longitude, nakshatra, nakshatra_idx, rasi, is_retrograde, speed
        asset_type: 'crypto' or 'commodity' - determines interpretation
            - For commodities (traditional SBC): malefic=TEJI=bullish, benefic=MANDI=bearish
            - For crypto (sentiment-driven): malefic=bearish, benefic=bullish

    Returns:
        Dict with:
            - positive_weight: Total malefic vedha weight
            - negative_weight: Total benefic vedha weight
            - net_score: positive - negative
            - sentiment: Overall market sentiment (interpretation depends on asset_type)
            - vedha_details: List of individual vedha calculations
    """
    # Standard 27 nakshatra names (without Abhijit for vedha calculation)
    nak_names_27 = [
        'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
        'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
        'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
        'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
        'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
    ]

    # Get Sun longitude for combustion check
    sun_lon = planetary_positions.get('Sun', {}).get('longitude', 0)

    positive_weight = 0.0  # Malefic = TEJI
    negative_weight = 0.0  # Benefic = MANDI
    vedha_details = []

    for planet, data in planetary_positions.items():
        if planet in ['Lagna', 'Ascendant'] or not isinstance(data, dict):
            continue

        # Get nakshatra index
        nakshatra = data.get('nakshatra', '')

        # Try to find nakshatra index
        try:
            if 'nakshatra_idx' in data:
                nak_idx = data['nakshatra_idx']
            else:
                # Calculate from nakshatra name
                nak_idx = nak_names_27.index(nakshatra) if nakshatra in nak_names_27 else -1
        except (ValueError, IndexError):
            # Calculate from longitude
            lon = data.get('longitude', 0)
            nak_idx = int(lon / 13.333333) % 27

        if nak_idx < 0 or nak_idx >= 27:
            continue

        # Get vedha target
        target_idx = get_vedha_target_nakshatra(nak_idx, 'front')
        target_nak = nak_names_27[target_idx]
        source_nak = nak_names_27[nak_idx]

        # Calculate strength
        rasi = data.get('rasi', data.get('sign', ''))
        is_retro = data.get('is_retrograde', False)
        speed = data.get('speed', 0)
        planet_lon = data.get('longitude', 0)

        strength, modifiers = calculate_planet_strength(
            planet, rasi, is_retro, speed, sun_lon, planet_lon
        )

        vedha_weight = strength * VEDHA_TYPE_WEIGHT['front']

        # Determine nature and accumulate weight
        is_malefic = planet in MALEFIC_PLANETS
        nature = 'MALEFIC' if is_malefic else 'BENEFIC'
        effect = 'TEJI' if is_malefic else 'MANDI'

        if is_malefic:
            positive_weight += vedha_weight
        else:
            negative_weight += vedha_weight

        vedha_details.append({
            'planet': planet,
            'from_nakshatra': source_nak,
            'to_nakshatra': target_nak,
            'vedha_type': 'front',
            'nature': nature,
            'effect': effect,
            'base_weight': PLANET_BASE_WEIGHT.get(planet, 1.0),
            'modifiers': modifiers,
            'final_weight': vedha_weight,
            'rasi': rasi,
            'is_retrograde': is_retro
        })

    # Calculate net score and sentiment
    net_score = positive_weight - negative_weight

    # For crypto: INVERT the traditional interpretation
    # Traditional SBC (commodities): malefic=TEJI=bullish, benefic=MANDI=bearish
    # Crypto interpretation: malefic=bearish (negative sentiment), benefic=bullish (positive sentiment)
    if asset_type == 'crypto':
        # Invert: net_score > 0 means more malefic, which is BEARISH for crypto
        if net_score > 2.0:
            sentiment = 'STRONGLY_BEARISH'
        elif net_score > 0.5:
            sentiment = 'MODERATELY_BEARISH'
        elif net_score > -0.5:
            sentiment = 'NEUTRAL'
        elif net_score > -2.0:
            sentiment = 'MODERATELY_BULLISH'
        else:
            sentiment = 'STRONGLY_BULLISH'
    else:
        # Traditional commodity interpretation
        if net_score > 2.0:
            sentiment = 'STRONGLY_BULLISH'
        elif net_score > 0.5:
            sentiment = 'MODERATELY_BULLISH'
        elif net_score > -0.5:
            sentiment = 'NEUTRAL'
        elif net_score > -2.0:
            sentiment = 'MODERATELY_BEARISH'
        else:
            sentiment = 'STRONGLY_BEARISH'

    return {
        'positive_weight': round(positive_weight, 2),
        'negative_weight': round(negative_weight, 2),
        'net_score': round(net_score, 2),
        'sentiment': sentiment,
        'asset_type': asset_type,
        'interpretation': 'crypto (benefic=bullish)' if asset_type == 'crypto' else 'commodity (malefic=TEJI=bullish)',
        'vedha_details': vedha_details,
        'malefic_breakdown': [v for v in vedha_details if v['nature'] == 'MALEFIC'],
        'benefic_breakdown': [v for v in vedha_details if v['nature'] == 'BENEFIC']
    }


def calculate_personalized_vedha_weights(planetary_positions: Dict, natal_nakshatra: str, natal_nakshatra_idx: int = None, asset_type: str = 'crypto') -> Dict:
    """
    Calculate vedha weights personalized for a specific entity's natal nakshatra.

    This is the KEY function that makes each market's analysis unique.
    It checks which transiting planets are creating vedha TO the natal nakshatra.

    Args:
        planetary_positions: Dict with current transit planet data
        natal_nakshatra: The entity's birth Moon nakshatra name
        natal_nakshatra_idx: Index of natal nakshatra (0-26), calculated if not provided
        asset_type: 'crypto' or 'commodity' - determines interpretation

    Returns:
        Dict with personalized vedha weights
    """
    # Standard 27 nakshatra names
    nak_names_27 = [
        'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
        'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
        'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
        'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
        'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
    ]

    # Get natal nakshatra index
    if natal_nakshatra_idx is None:
        try:
            natal_nakshatra_idx = nak_names_27.index(natal_nakshatra)
        except ValueError:
            # Try partial match
            for i, nak in enumerate(nak_names_27):
                if natal_nakshatra.lower() in nak.lower() or nak.lower() in natal_nakshatra.lower():
                    natal_nakshatra_idx = i
                    break
            else:
                # Default to Uttara Bhadrapada (Bitcoin's nakshatra)
                natal_nakshatra_idx = 25

    # Find which nakshatras create vedha TO the natal nakshatra
    # We need to find planets in nakshatras that have vedha relationship with natal nakshatra
    vedha_source_nakshatras = set()

    # Check all 27 nakshatras to find which ones create vedha to natal
    for source_idx in range(27):
        # Get the vedha target from this source
        target_idx = get_vedha_target_nakshatra(source_idx, 'front')
        if target_idx == natal_nakshatra_idx:
            vedha_source_nakshatras.add(source_idx)

        # Also check back vedha
        back_target_idx = get_vedha_target_nakshatra(source_idx, 'back')
        if back_target_idx == natal_nakshatra_idx:
            vedha_source_nakshatras.add(source_idx)

    # Get Sun longitude for combustion check
    sun_lon = planetary_positions.get('Sun', {}).get('longitude', 0)

    positive_weight = 0.0  # Malefic vedhas = TEJI (bullish for price)
    negative_weight = 0.0  # Benefic vedhas = MANDI (bearish for price)
    vedha_details = []
    affecting_planets = []

    for planet, data in planetary_positions.items():
        if planet in ['Lagna', 'Ascendant'] or not isinstance(data, dict):
            continue

        # Get planet's current nakshatra
        nakshatra = data.get('nakshatra', '')

        try:
            if 'nakshatra_idx' in data:
                planet_nak_idx = data['nakshatra_idx']
            else:
                planet_nak_idx = nak_names_27.index(nakshatra) if nakshatra in nak_names_27 else -1
        except (ValueError, IndexError):
            lon = data.get('longitude', 0)
            planet_nak_idx = int(lon / 13.333333) % 27

        if planet_nak_idx < 0 or planet_nak_idx >= 27:
            continue

        # Check if this planet is in a nakshatra that creates vedha to natal nakshatra
        creates_vedha = planet_nak_idx in vedha_source_nakshatras

        # Also check if planet is in the same nakshatra as natal (direct aspect)
        same_nakshatra = planet_nak_idx == natal_nakshatra_idx

        if creates_vedha or same_nakshatra:
            # Calculate strength
            rasi = data.get('rasi', data.get('sign', ''))
            is_retro = data.get('is_retrograde', False)
            speed = data.get('speed', 0)
            planet_lon = data.get('longitude', 0)

            strength, modifiers = calculate_planet_strength(
                planet, rasi, is_retro, speed, sun_lon, planet_lon
            )

            vedha_weight = strength * VEDHA_TYPE_WEIGHT.get('front', 1.0)

            # Same nakshatra has stronger effect
            if same_nakshatra:
                vedha_weight *= 1.5

            # Determine nature and accumulate weight
            is_malefic = planet in MALEFIC_PLANETS
            nature = 'MALEFIC' if is_malefic else 'BENEFIC'
            effect = 'TEJI' if is_malefic else 'MANDI'

            if is_malefic:
                positive_weight += vedha_weight
            else:
                negative_weight += vedha_weight

            affecting_planets.append(planet)

            vedha_details.append({
                'planet': planet,
                'from_nakshatra': nak_names_27[planet_nak_idx],
                'to_nakshatra': natal_nakshatra,
                'vedha_type': 'direct' if same_nakshatra else 'front',
                'nature': nature,
                'effect': effect,
                'base_weight': PLANET_BASE_WEIGHT.get(planet, 1.0),
                'modifiers': modifiers,
                'final_weight': round(vedha_weight, 2),
                'rasi': rasi,
                'is_retrograde': is_retro,
                'creates_vedha': creates_vedha,
                'same_nakshatra': same_nakshatra
            })

    # Calculate net score and sentiment
    net_score = positive_weight - negative_weight

    # For crypto: INVERT the traditional interpretation
    if asset_type == 'crypto':
        # Invert: net_score > 0 means more malefic, which is BEARISH for crypto
        if net_score > 2.0:
            sentiment = 'STRONGLY_BEARISH'
        elif net_score > 0.5:
            sentiment = 'MODERATELY_BEARISH'
        elif net_score > -0.5:
            sentiment = 'NEUTRAL'
        elif net_score > -2.0:
            sentiment = 'MODERATELY_BULLISH'
        else:
            sentiment = 'STRONGLY_BULLISH'
    else:
        # Traditional commodity interpretation
        if net_score > 2.0:
            sentiment = 'STRONGLY_BULLISH'
        elif net_score > 0.5:
            sentiment = 'MODERATELY_BULLISH'
        elif net_score > -0.5:
            sentiment = 'NEUTRAL'
        elif net_score > -2.0:
            sentiment = 'MODERATELY_BEARISH'
        else:
            sentiment = 'STRONGLY_BEARISH'

    return {
        'positive_weight': round(positive_weight, 2),
        'negative_weight': round(negative_weight, 2),
        'net_score': round(net_score, 2),
        'sentiment': sentiment,
        'asset_type': asset_type,
        'interpretation': 'crypto (benefic=bullish)' if asset_type == 'crypto' else 'commodity (malefic=TEJI=bullish)',
        'natal_nakshatra': natal_nakshatra,
        'natal_nakshatra_idx': natal_nakshatra_idx,
        'affecting_planets': affecting_planets,
        'vedha_sources': [nak_names_27[i] for i in vedha_source_nakshatras],
        'vedha_details': vedha_details,
        'malefic_breakdown': [v for v in vedha_details if v['nature'] == 'MALEFIC'],
        'benefic_breakdown': [v for v in vedha_details if v['nature'] == 'BENEFIC']
    }


# =====================================================
# SBC EXCEPTION RULES & CONFIDENCE SCORING
# Based on backtesting analysis of NY Session data
# =====================================================

# High-failure Moon Nakshatras (50%+ failure rate in filtered trades)
# Updated based on 2024-2025 backtest analysis
HIGH_FAIL_MOON_NAKSHATRAS = {
    'Anuradha': 0.71,      # 71% failure - Saturn ruled
    'Mrigashira': 0.69,    # 69% failure - Mars ruled
    'Ardra': 0.61,         # 61% failure - Rahu ruled (NEW)
    'Purva Ashadha': 0.62, # 62% failure - Venus ruled
    'Ashlesha': 0.62,      # 62% failure - Mercury ruled
    'Revati': 0.58,        # 58% failure - Mercury ruled
    'Mula': 0.58,          # 58% failure - Ketu ruled
    'Magha': 0.57,         # 57% failure - Ketu ruled
    'Rohini': 0.55,        # 55% failure - Moon ruled (NEW - surprising!)
    'Punarvasu': 0.53,     # 53% failure - Jupiter ruled (NEW)
}

# High-confidence Moon Nakshatras (65%+ accuracy in filtered trades)
HIGH_CONFIDENCE_MOON_NAKSHATRAS = {
    'Bharani': 0.72,       # 72% accuracy - Venus ruled
    'Chitra': 0.67,        # 67% accuracy - Mars ruled
    'Vishakha': 0.65,      # 65% accuracy - Jupiter ruled
}

# Additional HIGH-FAIL nakshatras discovered in filtered set analysis (Dec 2025)
HIGH_FAIL_MOON_NAKSHATRAS_FILTERED = {
    'Purva Bhadrapada': 0.455,  # 45.5% fail rate in filtered trades
    'Purva Phalguni': 0.438,   # 43.8% fail rate
    'Shravana': 0.421,         # 42.1% fail rate (removed from high-confidence!)
    'Pushya': 0.412,           # 41.2% fail rate
}

# Signal-specific nakshatra combinations with 100% fail rate - MUST SKIP
SIGNAL_NAKSHATRA_SKIP_PATTERNS = {
    ('MODERATELY_BEARISH', 'Shravana'): 1.00,      # 100% fail (4/4)
    ('NEUTRAL', 'Purva Ashadha'): 1.00,            # 100% fail (4/4)
    ('MODERATELY_BEARISH', 'Vishakha'): 1.00,      # 100% fail (2/2)
}

# Signal-specific nakshatra high-fail combinations
SIGNAL_NAKSHATRA_HIGH_FAIL = {
    ('MODERATELY_BEARISH', 'Pushya'): 0.833,       # 83.3% fail (5/6)
    ('MODERATELY_BULLISH', 'Purva Bhadrapada'): 0.75,  # 75% fail (3/4)
    ('MODERATELY_BULLISH', 'Jyeshtha'): 0.667,     # 66.7% fail (2/3)
    ('STRONGLY_BULLISH', 'Purva Phalguni'): 0.60,  # 60% fail (3/5)
}

# High-failure Tithis
HIGH_FAIL_TITHIS = {
    'Ashtami': 0.68,           # 68% failure - 8th lunar day
    'Pratipada': 0.50,         # 50% failure - 1st lunar day (NEW refined data)
    'Purnima/Amavasya': 0.45,  # 45% failure - Full/New Moon (NEW)
    'Dvitiya': 0.444,          # 44.4% failure - 2nd lunar day
}

# High-confidence Tithis (based on filtered trade analysis)
HIGH_CONFIDENCE_TITHIS = {
    'Navami': 0.63,        # 63% accuracy - 9th lunar day
    'Panchami': 0.62,      # 62% accuracy - 5th lunar day
    'Chaturdashi': 0.63,   # 63% accuracy - 14th lunar day
    'Shashthi': 0.60,      # 60% accuracy - 6th lunar day
}

# High-failure days of week
HIGH_FAIL_DAYS = {
    'Sunday': 0.53,        # 53% failure rate
    'Saturday': 0.50,      # Weekend - skip trading
}

# Days to completely skip trading (weekends - no NYSE session)
SKIP_TRADING_DAYS = {'Saturday', 'Sunday'}


def calculate_signal_confidence(
    moon_nakshatra: str,
    tithi: str,
    vedhas_by_factor: Dict,
    retrograde_planets: list = None,
    signal: str = None,
    day_of_week: str = None
) -> Dict:
    """
    Calculate confidence score for SBC signal based on exception rules.

    Args:
        moon_nakshatra: Current Moon nakshatra
        tithi: Current tithi name
        vedhas_by_factor: Dict with vedha info for each panchang factor
        retrograde_planets: List of retrograde planet names
        signal: The calculated SBC signal
        day_of_week: Day of week (e.g., 'Sunday', 'Monday')

    Returns:
        Dict with:
            - confidence: 0.0 to 1.0 confidence score
            - confidence_level: 'HIGH', 'MEDIUM', 'LOW', 'SKIP'
            - warnings: List of warning messages
            - boosters: List of confidence boosters
            - recommendation: Trading recommendation
    """
    base_confidence = 0.55  # Base accuracy of the model
    warnings = []
    boosters = []

    # ===== NEGATIVE FACTORS (Reduce confidence) =====

    # 1. Moon in high-failure nakshatra
    if moon_nakshatra in HIGH_FAIL_MOON_NAKSHATRAS:
        fail_rate = HIGH_FAIL_MOON_NAKSHATRAS[moon_nakshatra]
        base_confidence -= 0.15
        warnings.append(f"⚠️ Moon in {moon_nakshatra} ({fail_rate*100:.0f}% historical failure)")

    # 2. High-failure tithi
    if tithi in HIGH_FAIL_TITHIS:
        fail_rate = HIGH_FAIL_TITHIS[tithi]
        base_confidence -= 0.12
        warnings.append(f"⚠️ {tithi} tithi ({fail_rate*100:.0f}% historical failure)")

    # 3. Moon creates positive nakshatra vedha (4.3x more failures!)
    nakshatra_vedhas = vedhas_by_factor.get('nakshatra', {})
    positive_vedhas = nakshatra_vedhas.get('positive', [])
    if any(v.get('planet') == 'Moon' for v in positive_vedhas):
        base_confidence -= 0.20
        warnings.append("⚠️ Moon creates positive nakshatra vedha (78% historical failure)")

    # 4. Mercury positive swara vedha (3x more failures)
    swara_vedhas = vedhas_by_factor.get('swara', {})
    swara_positive = swara_vedhas.get('positive', [])
    if any(v.get('planet') == 'Mercury' for v in swara_positive):
        base_confidence -= 0.08
        warnings.append("⚠️ Mercury creates positive swara vedha (3x more failures)")

    # 5. Mars negative akshara vedha (2.4x more failures)
    akshara_vedhas = vedhas_by_factor.get('akshara', {})
    akshara_negative = akshara_vedhas.get('negative', [])
    if any(v.get('planet') == 'Mars' for v in akshara_negative):
        base_confidence -= 0.06
        warnings.append("⚠️ Mars creates negative akshara vedha (2.4x more failures)")

    # 6. Akshara has BOTH positive & negative (conflicting vedhas)
    akshara_positive = akshara_vedhas.get('positive', [])
    if akshara_positive and akshara_negative:
        base_confidence -= 0.05
        warnings.append("⚠️ Conflicting vedhas on akshara factor")

    # 7. Uranus or Saturn retrograde
    if retrograde_planets:
        if 'Uranus' in retrograde_planets:
            base_confidence -= 0.03
            warnings.append("⚠️ Uranus retrograde (53% historical failure)")
        if 'Saturn' in retrograde_planets:
            base_confidence -= 0.02
            warnings.append("⚠️ Saturn retrograde (52% historical failure)")

    # 8. Sun negative swara vedha (1.70x more in failures)
    if any(v.get('planet') == 'Sun' for v in swara_vedhas.get('negative', [])):
        base_confidence -= 0.07
        warnings.append("⚠️ Sun creates negative swara vedha (1.7x more failures)")

    # 9. Mercury positive tithi vedha (1.41x more in failures)
    tithi_vedhas = vedhas_by_factor.get('tithi', {})
    if any(v.get('planet') == 'Mercury' for v in tithi_vedhas.get('positive', [])):
        base_confidence -= 0.05
        warnings.append("⚠️ Mercury creates positive tithi vedha (1.4x more failures)")

    # 10. Signal-Nakshatra SKIP patterns (100% fail rate - FORCE SKIP)
    if signal and moon_nakshatra:
        if (signal, moon_nakshatra) in SIGNAL_NAKSHATRA_SKIP_PATTERNS:
            base_confidence = 0.0
            warnings.append(f"⛔ {signal} + {moon_nakshatra} = 100% historical failure (SKIP)")

    # 11. Signal-Nakshatra high-fail combinations (66-83% fail)
    if signal and moon_nakshatra:
        if (signal, moon_nakshatra) in SIGNAL_NAKSHATRA_HIGH_FAIL:
            fail_rate = SIGNAL_NAKSHATRA_HIGH_FAIL[(signal, moon_nakshatra)]
            base_confidence -= 0.20
            warnings.append(f"⚠️ {signal} + {moon_nakshatra} ({fail_rate*100:.0f}% historical failure)")

    # 12. Venus positive tithi vedha (69.2% fail rate!)
    if any(v.get('planet') == 'Venus' for v in tithi_vedhas.get('positive', [])):
        base_confidence -= 0.15
        warnings.append("⚠️ Venus creates positive tithi vedha (69% historical failure)")

    # 13. Mercury positive + Mars negative rashi vedha (100% fail!)
    rashi_vedhas = vedhas_by_factor.get('rashi', {})
    rashi_pos = rashi_vedhas.get('positive', [])
    rashi_neg = rashi_vedhas.get('negative', [])
    has_mercury_pos_rashi = any(v.get('planet') == 'Mercury' for v in rashi_pos)
    has_mars_neg_rashi = any(v.get('planet') == 'Mars' for v in rashi_neg)
    if has_mercury_pos_rashi and has_mars_neg_rashi:
        base_confidence = 0.0
        warnings.append("⛔ Mercury+Mars rashi vedha conflict (100% historical failure)")

    # 14. Mercury positive + Sun negative akshara vedha (100% fail!)
    has_mercury_pos_akshara = any(v.get('planet') == 'Mercury' for v in akshara_positive)
    has_sun_neg_akshara = any(v.get('planet') == 'Sun' for v in akshara_negative)
    if has_mercury_pos_akshara and has_sun_neg_akshara:
        base_confidence = 0.0
        warnings.append("⛔ Mercury+Sun akshara vedha conflict (100% historical failure)")

    # 15. Mercury positive + Moon negative akshara vedha (75% fail)
    has_moon_neg_akshara = any(v.get('planet') == 'Moon' for v in akshara_negative)
    if has_mercury_pos_akshara and has_moon_neg_akshara:
        base_confidence -= 0.20
        warnings.append("⚠️ Mercury+Moon akshara vedha conflict (75% historical failure)")

    # 16. Moon in filtered high-fail nakshatras (additional from Dec 2025 analysis)
    if moon_nakshatra in HIGH_FAIL_MOON_NAKSHATRAS_FILTERED:
        fail_rate = HIGH_FAIL_MOON_NAKSHATRAS_FILTERED[moon_nakshatra]
        base_confidence -= 0.10
        warnings.append(f"⚠️ Moon in {moon_nakshatra} ({fail_rate*100:.0f}% fail in filtered trades)")

    # 17. Jupiter retrograde (35.4% fail vs 30.3% when direct)
    if retrograde_planets and 'Jupiter' in retrograde_planets:
        base_confidence -= 0.03
        warnings.append("⚠️ Jupiter retrograde (35% failure rate)")

    # ===== HIDDEN BENEFIC ANALYSIS (Dec 2025) =====
    # NOTE: These patterns were identified in already-filtered LOW confidence trades
    # They explain WHY those trades failed, but applying penalties globally hurts accuracy
    # The existing rules (signal-nakshatra combos, vedha conflicts) already capture these
    #
    # Key findings preserved for reference:
    # - Moon positive nakshatra vedha: 87.5% inversion (already penalized in rule #3)
    # - Mercury positive nakshatra vedha: 83.3% inversion in weak bearish
    # - Venus positive rashi vedha: 80% inversion, avg +3.07%
    # - Venus positive swara vedha: 77.8% inversion
    # - Moon positive akshara vedha: 60% inversion

    # ===== POSITIVE FACTORS (Increase confidence) =====

    # 1. NEUTRAL signal (81% accuracy!)
    if signal == 'NEUTRAL':
        base_confidence = 0.81
        boosters.append("✅ NEUTRAL signal (81% historical accuracy)")

    # 2. Moon in high-confidence nakshatra
    if moon_nakshatra in HIGH_CONFIDENCE_MOON_NAKSHATRAS:
        accuracy = HIGH_CONFIDENCE_MOON_NAKSHATRAS[moon_nakshatra]
        base_confidence += 0.10
        boosters.append(f"✅ Moon in {moon_nakshatra} ({accuracy*100:.0f}% historical accuracy)")

    # 3. High-confidence tithi
    if tithi in HIGH_CONFIDENCE_TITHIS:
        accuracy = HIGH_CONFIDENCE_TITHIS[tithi]
        base_confidence += 0.08
        boosters.append(f"✅ {tithi} tithi ({accuracy*100:.0f}% historical accuracy)")

    # Clamp confidence to valid range
    confidence = max(0.0, min(1.0, base_confidence))

    # FINAL OVERRIDE: Weekends are ALWAYS skipped (no NYSE session)
    if day_of_week and day_of_week in SKIP_TRADING_DAYS:
        confidence = 0.0
        confidence_level = 'SKIP'
        recommendation = f'NO TRADE - {day_of_week} (no NYSE session)'
        return {
            'confidence': 0.0,
            'confidence_level': 'SKIP',
            'confidence_pct': "0%",
            'warnings': [f"⛔ {day_of_week} - No NYSE session (weekend)"],
            'boosters': [],
            'warning_count': 1,
            'booster_count': 0,
            'recommendation': recommendation,
            'should_trade': False,
            'position_size_multiplier': 0.0
        }

    # Determine confidence level
    if confidence >= 0.65:
        confidence_level = 'HIGH'
        recommendation = 'Full position size recommended'
    elif confidence >= 0.50:
        confidence_level = 'MEDIUM'
        recommendation = 'Reduced position size recommended'
    elif confidence >= 0.35:
        confidence_level = 'LOW'
        recommendation = 'Minimal position or skip trade'
    else:
        confidence_level = 'SKIP'
        recommendation = 'AVOID trade - too many warning signals'

    return {
        'confidence': round(confidence, 3),
        'confidence_level': confidence_level,
        'confidence_pct': f"{confidence*100:.0f}%",
        'warnings': warnings,
        'boosters': boosters,
        'warning_count': len(warnings),
        'booster_count': len(boosters),
        'recommendation': recommendation,
        'should_trade': confidence_level in ['HIGH', 'MEDIUM'],
        'position_size_multiplier': confidence if confidence >= 0.35 else 0.0
    }


def get_enhanced_sbc_signal(
    base_signal: str,
    net_score: float,
    moon_nakshatra: str,
    tithi: str,
    vedhas_by_factor: Dict,
    retrograde_planets: list = None,
    day_of_week: str = None
) -> Dict:
    """
    Get enhanced SBC signal with confidence scoring and exception filters.

    Returns complete trading signal with:
    - Original signal
    - Confidence-adjusted signal
    - Position size recommendation
    - All warnings and boosters
    """
    # Calculate confidence
    confidence_data = calculate_signal_confidence(
        moon_nakshatra=moon_nakshatra,
        tithi=tithi,
        vedhas_by_factor=vedhas_by_factor,
        retrograde_planets=retrograde_planets,
        signal=base_signal,
        day_of_week=day_of_week
    )

    # Determine adjusted signal
    if confidence_data['confidence_level'] == 'SKIP':
        adjusted_signal = 'NO_TRADE'
    elif confidence_data['confidence_level'] == 'LOW':
        adjusted_signal = 'WEAK_' + base_signal
    else:
        adjusted_signal = base_signal

    return {
        'original_signal': base_signal,
        'adjusted_signal': adjusted_signal,
        'net_score': net_score,
        'confidence': confidence_data['confidence'],
        'confidence_level': confidence_data['confidence_level'],
        'confidence_pct': confidence_data['confidence_pct'],
        'should_trade': confidence_data['should_trade'],
        'position_size': confidence_data['position_size_multiplier'],
        'recommendation': confidence_data['recommendation'],
        'warnings': confidence_data['warnings'],
        'boosters': confidence_data['boosters'],
        'moon_nakshatra': moon_nakshatra,
        'tithi': tithi
    }


def forecast_vedha_weights(days: int = 7) -> Dict:
    """
    Forecast vedha weights for the next N days and identify optimal trade timing.

    Returns:
        Dict with:
            - daily_forecast: List of daily vedha weight predictions
            - best_buy_time: When sentiment shifts from bearish to bullish
            - best_sell_time: When sentiment shifts from bullish to bearish
            - trend_analysis: Overall trend direction
            - key_dates: Important dates with significant changes
    """
    try:
        import swisseph as swe
        from datetime import datetime, timedelta
        import pytz
    except ImportError:
        return {'error': 'Required modules not available'}

    # Set sidereal mode
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    RASI_NAMES = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    NAK_NAMES = [
        'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
        'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
        'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
        'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
        'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
    ]

    planet_ids = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
        'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
        'Venus': swe.VENUS, 'Saturn': swe.SATURN
    }

    ny_tz = pytz.timezone('America/New_York')
    now = datetime.now(ny_tz)

    daily_forecast = []
    prev_sentiment = None

    for day_offset in range(days + 1):  # Include today
        target_date = now + timedelta(days=day_offset)
        utc_date = target_date.astimezone(pytz.UTC)
        jd = swe.julday(utc_date.year, utc_date.month, utc_date.day, 12.0)  # Noon

        # Build planetary positions for this day
        positions = {}

        for name, pid in planet_ids.items():
            result = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SPEED)
            lon = result[0][0]
            speed = result[0][3]
            nak_idx = int(lon / 13.333333) % 27
            rasi_idx = int(lon / 30)

            positions[name] = {
                'longitude': lon,
                'nakshatra': NAK_NAMES[nak_idx],
                'nakshatra_idx': nak_idx,
                'rasi': RASI_NAMES[rasi_idx],
                'is_retrograde': speed < 0,
                'speed': speed
            }

        # Rahu/Ketu
        result = swe.calc_ut(jd, swe.MEAN_NODE, swe.FLG_SIDEREAL)
        rahu_lon = result[0][0]
        ketu_lon = (rahu_lon + 180) % 360

        for name, lon in [('Rahu', rahu_lon), ('Ketu', ketu_lon)]:
            nak_idx = int(lon / 13.333333) % 27
            rasi_idx = int(lon / 30)
            positions[name] = {
                'longitude': lon,
                'nakshatra': NAK_NAMES[nak_idx],
                'nakshatra_idx': nak_idx,
                'rasi': RASI_NAMES[rasi_idx],
                'is_retrograde': True,
                'speed': -0.05
            }

        # Calculate vedha weights for this day
        weights = calculate_vedha_weights(positions)

        # Detect sentiment change
        current_sentiment = weights['sentiment']
        sentiment_changed = prev_sentiment is not None and prev_sentiment != current_sentiment

        # Determine if this is a good entry/exit point
        is_bullish_shift = sentiment_changed and 'BULLISH' in current_sentiment and 'BEARISH' in (prev_sentiment or '')
        is_bearish_shift = sentiment_changed and 'BEARISH' in current_sentiment and 'BULLISH' in (prev_sentiment or '')

        daily_forecast.append({
            'date': target_date.strftime('%Y-%m-%d'),
            'day_name': target_date.strftime('%A'),
            'day_offset': day_offset,
            'positive_weight': weights['positive_weight'],
            'negative_weight': weights['negative_weight'],
            'net_score': weights['net_score'],
            'sentiment': current_sentiment,
            'sentiment_changed': sentiment_changed,
            'prev_sentiment': prev_sentiment,
            'is_bullish_shift': is_bullish_shift,
            'is_bearish_shift': is_bearish_shift,
            'moon_nakshatra': positions['Moon']['nakshatra'],
            'key_planets': {
                'Jupiter': {'retrograde': positions['Jupiter']['is_retrograde'], 'nakshatra': positions['Jupiter']['nakshatra']},
                'Saturn': {'retrograde': positions['Saturn']['is_retrograde'], 'nakshatra': positions['Saturn']['nakshatra']},
                'Mars': {'nakshatra': positions['Mars']['nakshatra']},
                'Venus': {'nakshatra': positions['Venus']['nakshatra']}
            }
        })

        prev_sentiment = current_sentiment

    # Analyze the forecast
    best_buy_times = []
    best_sell_times = []
    key_dates = []

    for i, day in enumerate(daily_forecast):
        if day['is_bullish_shift']:
            best_buy_times.append({
                'date': day['date'],
                'day_name': day['day_name'],
                'reason': f"Sentiment shifts from {day['prev_sentiment']} to {day['sentiment']}",
                'net_score': day['net_score']
            })
            key_dates.append({
                'date': day['date'],
                'event': 'BULLISH_SHIFT',
                'action': 'BUY',
                'description': f"Market sentiment turns bullish (Net: {day['net_score']:+.2f})"
            })

        if day['is_bearish_shift']:
            best_sell_times.append({
                'date': day['date'],
                'day_name': day['day_name'],
                'reason': f"Sentiment shifts from {day['prev_sentiment']} to {day['sentiment']}",
                'net_score': day['net_score']
            })
            key_dates.append({
                'date': day['date'],
                'event': 'BEARISH_SHIFT',
                'action': 'SELL',
                'description': f"Market sentiment turns bearish (Net: {day['net_score']:+.2f})"
            })

        # Also flag days with extreme scores
        if day['net_score'] >= 3.0 and day['day_offset'] > 0:
            if not any(k['date'] == day['date'] for k in key_dates):
                key_dates.append({
                    'date': day['date'],
                    'event': 'STRONG_BULLISH',
                    'action': 'HOLD_LONG',
                    'description': f"Strong bullish day (Net: {day['net_score']:+.2f})"
                })
        elif day['net_score'] <= -3.0 and day['day_offset'] > 0:
            if not any(k['date'] == day['date'] for k in key_dates):
                key_dates.append({
                    'date': day['date'],
                    'event': 'STRONG_BEARISH',
                    'action': 'HOLD_SHORT',
                    'description': f"Strong bearish day (Net: {day['net_score']:+.2f})"
                })

    # Find local minima (best buy) and maxima (best sell) in net_score
    for i in range(1, len(daily_forecast) - 1):
        prev_score = daily_forecast[i-1]['net_score']
        curr_score = daily_forecast[i]['net_score']
        next_score = daily_forecast[i+1]['net_score']

        # Local minimum - potential buy point
        if curr_score < prev_score and curr_score < next_score and curr_score < 0:
            if not any(b['date'] == daily_forecast[i]['date'] for b in best_buy_times):
                best_buy_times.append({
                    'date': daily_forecast[i]['date'],
                    'day_name': daily_forecast[i]['day_name'],
                    'reason': f"Local minimum in vedha score (bottom before reversal)",
                    'net_score': curr_score
                })

        # Local maximum - potential sell point
        if curr_score > prev_score and curr_score > next_score and curr_score > 0:
            if not any(s['date'] == daily_forecast[i]['date'] for s in best_sell_times):
                best_sell_times.append({
                    'date': daily_forecast[i]['date'],
                    'day_name': daily_forecast[i]['day_name'],
                    'reason': f"Local maximum in vedha score (peak before reversal)",
                    'net_score': curr_score
                })

    # Calculate overall trend
    if len(daily_forecast) >= 2:
        start_score = daily_forecast[0]['net_score']
        end_score = daily_forecast[-1]['net_score']
        score_change = end_score - start_score

        if score_change > 1.0:
            trend = 'IMPROVING'
            trend_description = f"Vedha balance improving by {score_change:+.2f} over {days} days"
        elif score_change < -1.0:
            trend = 'DETERIORATING'
            trend_description = f"Vedha balance deteriorating by {score_change:+.2f} over {days} days"
        else:
            trend = 'STABLE'
            trend_description = f"Vedha balance relatively stable (change: {score_change:+.2f})"
    else:
        trend = 'UNKNOWN'
        trend_description = 'Insufficient data'

    # Sort key dates by date
    key_dates.sort(key=lambda x: x['date'])

    return {
        'forecast_generated': now.strftime('%Y-%m-%d %H:%M %Z'),
        'forecast_days': days,
        'daily_forecast': daily_forecast,
        'best_buy_times': best_buy_times,
        'best_sell_times': best_sell_times,
        'key_dates': key_dates,
        'trend': trend,
        'trend_description': trend_description,
        'today': {
            'date': daily_forecast[0]['date'],
            'sentiment': daily_forecast[0]['sentiment'],
            'net_score': daily_forecast[0]['net_score'],
            'recommendation': 'BUY' if daily_forecast[0]['net_score'] > 1.0 else ('SELL' if daily_forecast[0]['net_score'] < -1.0 else 'WAIT')
        }
    }


def forecast_hourly_vedha_weights(target_date: str = None, hours: int = 24) -> Dict:
    """
    Forecast vedha weights for each hour of a specific day to find optimal intraday timing.
    Uses the Moon's rapid movement (~13°/day) to detect hourly shifts in sentiment.

    The Moon moves through each nakshatra in about 1 day, so hourly changes can be significant.
    This helps find the best hour to enter/exit trades within a given day.

    Args:
        target_date: Date to forecast (YYYY-MM-DD), defaults to today
        hours: Number of hours to forecast (default 24)

    Returns:
        Dict with:
            - hourly_forecast: List of hourly vedha weight predictions
            - best_buy_hour: Best hour to buy (when sentiment shifts bullish or is at local minimum)
            - best_sell_hour: Best hour to sell (when sentiment shifts bearish or is at local maximum)
            - moon_transitions: When Moon changes nakshatra
            - intraday_trend: Overall intraday sentiment trend
    """
    try:
        import swisseph as swe
        from datetime import datetime, timedelta
        import pytz
    except ImportError:
        return {'error': 'Required modules not available'}

    # Set sidereal mode
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    RASI_NAMES = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo',
                  'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces']
    NAK_NAMES = [
        'Ashwini', 'Bharani', 'Krittika', 'Rohini', 'Mrigashira', 'Ardra',
        'Punarvasu', 'Pushya', 'Ashlesha', 'Magha', 'Purva Phalguni', 'Uttara Phalguni',
        'Hasta', 'Chitra', 'Swati', 'Vishakha', 'Anuradha', 'Jyeshtha',
        'Mula', 'Purva Ashadha', 'Uttara Ashadha', 'Shravana', 'Dhanishta',
        'Shatabhisha', 'Purva Bhadrapada', 'Uttara Bhadrapada', 'Revati'
    ]

    planet_ids = {
        'Sun': swe.SUN, 'Moon': swe.MOON, 'Mars': swe.MARS,
        'Mercury': swe.MERCURY, 'Jupiter': swe.JUPITER,
        'Venus': swe.VENUS, 'Saturn': swe.SATURN
    }

    ny_tz = pytz.timezone('America/New_York')

    # Parse target date or use today
    if target_date:
        try:
            base_date = datetime.strptime(target_date, '%Y-%m-%d')
            base_date = ny_tz.localize(base_date.replace(hour=0, minute=0, second=0))
        except ValueError:
            base_date = datetime.now(ny_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        base_date = datetime.now(ny_tz).replace(hour=0, minute=0, second=0, microsecond=0)

    hourly_forecast = []
    prev_sentiment = None
    prev_moon_nak = None
    moon_transitions = []

    for hour_offset in range(hours):
        target_time = base_date + timedelta(hours=hour_offset)
        utc_time = target_time.astimezone(pytz.UTC)
        # Julian day with fractional hours
        jd = swe.julday(utc_time.year, utc_time.month, utc_time.day,
                        utc_time.hour + utc_time.minute / 60.0)

        # Build planetary positions for this hour
        positions = {}

        for name, pid in planet_ids.items():
            result = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL | swe.FLG_SPEED)
            lon = result[0][0]
            speed = result[0][3]
            nak_idx = int(lon / 13.333333) % 27
            rasi_idx = int(lon / 30)

            positions[name] = {
                'longitude': lon,
                'nakshatra': NAK_NAMES[nak_idx],
                'nakshatra_idx': nak_idx,
                'rasi': RASI_NAMES[rasi_idx],
                'is_retrograde': speed < 0,
                'speed': speed
            }

        # Rahu/Ketu
        result = swe.calc_ut(jd, swe.MEAN_NODE, swe.FLG_SIDEREAL)
        rahu_lon = result[0][0]
        ketu_lon = (rahu_lon + 180) % 360

        for name, lon in [('Rahu', rahu_lon), ('Ketu', ketu_lon)]:
            nak_idx = int(lon / 13.333333) % 27
            rasi_idx = int(lon / 30)
            positions[name] = {
                'longitude': lon,
                'nakshatra': NAK_NAMES[nak_idx],
                'nakshatra_idx': nak_idx,
                'rasi': RASI_NAMES[rasi_idx],
                'is_retrograde': True,
                'speed': -0.05
            }

        # Calculate vedha weights for this hour
        weights = calculate_vedha_weights(positions)

        # Track Moon nakshatra transitions
        current_moon_nak = positions['Moon']['nakshatra']
        moon_transition = False
        if prev_moon_nak is not None and prev_moon_nak != current_moon_nak:
            moon_transition = True
            moon_transitions.append({
                'hour': target_time.strftime('%H:%M'),
                'hour_offset': hour_offset,
                'from_nakshatra': prev_moon_nak,
                'to_nakshatra': current_moon_nak,
                'significance': 'Moon nakshatra change affects market sentiment'
            })

        # Detect sentiment change
        current_sentiment = weights['sentiment']
        sentiment_changed = prev_sentiment is not None and prev_sentiment != current_sentiment

        is_bullish_shift = sentiment_changed and 'BULLISH' in current_sentiment and 'BEARISH' in (prev_sentiment or '')
        is_bearish_shift = sentiment_changed and 'BEARISH' in current_sentiment and 'BULLISH' in (prev_sentiment or '')

        hourly_forecast.append({
            'hour': target_time.strftime('%H:%M'),
            'hour_12': target_time.strftime('%I:%M %p'),
            'hour_offset': hour_offset,
            'timestamp': target_time.isoformat(),
            'positive_weight': weights['positive_weight'],
            'negative_weight': weights['negative_weight'],
            'net_score': weights['net_score'],
            'sentiment': current_sentiment,
            'sentiment_changed': sentiment_changed,
            'prev_sentiment': prev_sentiment,
            'is_bullish_shift': is_bullish_shift,
            'is_bearish_shift': is_bearish_shift,
            'moon_nakshatra': current_moon_nak,
            'moon_transition': moon_transition,
            'moon_longitude': positions['Moon']['longitude']
        })

        prev_sentiment = current_sentiment
        prev_moon_nak = current_moon_nak

    # Find best buy/sell hours
    best_buy_hours = []
    best_sell_hours = []

    for i, hour in enumerate(hourly_forecast):
        if hour['is_bullish_shift']:
            best_buy_hours.append({
                'hour': hour['hour'],
                'hour_12': hour['hour_12'],
                'reason': f"Sentiment shifts from {hour['prev_sentiment']} to {hour['sentiment']}",
                'net_score': hour['net_score'],
                'priority': 'HIGH'
            })

        if hour['is_bearish_shift']:
            best_sell_hours.append({
                'hour': hour['hour'],
                'hour_12': hour['hour_12'],
                'reason': f"Sentiment shifts from {hour['prev_sentiment']} to {hour['sentiment']}",
                'net_score': hour['net_score'],
                'priority': 'HIGH'
            })

    # Find local minima/maxima
    for i in range(1, len(hourly_forecast) - 1):
        prev_score = hourly_forecast[i-1]['net_score']
        curr_score = hourly_forecast[i]['net_score']
        next_score = hourly_forecast[i+1]['net_score']

        # Local minimum - potential buy point
        if curr_score < prev_score and curr_score < next_score:
            if not any(b['hour'] == hourly_forecast[i]['hour'] for b in best_buy_hours):
                best_buy_hours.append({
                    'hour': hourly_forecast[i]['hour'],
                    'hour_12': hourly_forecast[i]['hour_12'],
                    'reason': 'Local minimum in vedha score (dip before recovery)',
                    'net_score': curr_score,
                    'priority': 'MEDIUM' if curr_score < 0 else 'LOW'
                })

        # Local maximum - potential sell point
        if curr_score > prev_score and curr_score > next_score:
            if not any(s['hour'] == hourly_forecast[i]['hour'] for s in best_sell_hours):
                best_sell_hours.append({
                    'hour': hourly_forecast[i]['hour'],
                    'hour_12': hourly_forecast[i]['hour_12'],
                    'reason': 'Local maximum in vedha score (peak before decline)',
                    'net_score': curr_score,
                    'priority': 'MEDIUM' if curr_score > 0 else 'LOW'
                })

    # Sort by priority and score
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    best_buy_hours.sort(key=lambda x: (priority_order[x['priority']], x['net_score']))
    best_sell_hours.sort(key=lambda x: (priority_order[x['priority']], -x['net_score']))

    # Calculate intraday trend
    if len(hourly_forecast) >= 2:
        morning_avg = sum(h['net_score'] for h in hourly_forecast[:12]) / 12 if len(hourly_forecast) >= 12 else hourly_forecast[0]['net_score']
        afternoon_avg = sum(h['net_score'] for h in hourly_forecast[12:]) / max(1, len(hourly_forecast) - 12) if len(hourly_forecast) > 12 else morning_avg

        if afternoon_avg > morning_avg + 0.5:
            intraday_trend = 'STRENGTHENING'
            trend_description = f"Sentiment improves through the day (AM avg: {morning_avg:+.2f}, PM avg: {afternoon_avg:+.2f})"
        elif afternoon_avg < morning_avg - 0.5:
            intraday_trend = 'WEAKENING'
            trend_description = f"Sentiment weakens through the day (AM avg: {morning_avg:+.2f}, PM avg: {afternoon_avg:+.2f})"
        else:
            intraday_trend = 'STABLE'
            trend_description = f"Sentiment relatively stable (AM avg: {morning_avg:+.2f}, PM avg: {afternoon_avg:+.2f})"
    else:
        intraday_trend = 'UNKNOWN'
        trend_description = 'Insufficient data'

    # Get current hour's analysis
    now = datetime.now(ny_tz)
    current_hour_idx = min(now.hour, len(hourly_forecast) - 1) if target_date is None else 0

    return {
        'forecast_generated': datetime.now(ny_tz).strftime('%Y-%m-%d %H:%M %Z'),
        'target_date': base_date.strftime('%Y-%m-%d'),
        'target_day': base_date.strftime('%A'),
        'hours_forecast': hours,
        'hourly_forecast': hourly_forecast,
        'best_buy_hours': best_buy_hours[:5],  # Top 5
        'best_sell_hours': best_sell_hours[:5],  # Top 5
        'moon_transitions': moon_transitions,
        'intraday_trend': intraday_trend,
        'trend_description': trend_description,
        'current_hour': {
            'hour': hourly_forecast[current_hour_idx]['hour'],
            'hour_12': hourly_forecast[current_hour_idx]['hour_12'],
            'sentiment': hourly_forecast[current_hour_idx]['sentiment'],
            'net_score': hourly_forecast[current_hour_idx]['net_score'],
            'moon_nakshatra': hourly_forecast[current_hour_idx]['moon_nakshatra']
        },
        'trading_windows': {
            'morning': {
                'range': '09:00-12:00',
                'avg_score': sum(h['net_score'] for h in hourly_forecast[9:12]) / 3 if len(hourly_forecast) > 11 else 0,
                'sentiment': _get_sentiment(sum(h['net_score'] for h in hourly_forecast[9:12]) / 3 if len(hourly_forecast) > 11 else 0)
            },
            'afternoon': {
                'range': '12:00-16:00',
                'avg_score': sum(h['net_score'] for h in hourly_forecast[12:16]) / 4 if len(hourly_forecast) > 15 else 0,
                'sentiment': _get_sentiment(sum(h['net_score'] for h in hourly_forecast[12:16]) / 4 if len(hourly_forecast) > 15 else 0)
            },
            'evening': {
                'range': '16:00-20:00',
                'avg_score': sum(h['net_score'] for h in hourly_forecast[16:20]) / 4 if len(hourly_forecast) > 19 else 0,
                'sentiment': _get_sentiment(sum(h['net_score'] for h in hourly_forecast[16:20]) / 4 if len(hourly_forecast) > 19 else 0)
            }
        }
    }


def _get_sentiment(score: float) -> str:
    """Helper to get sentiment string from score."""
    if score > 2.0:
        return 'STRONGLY_BULLISH'
    elif score > 0.5:
        return 'MODERATELY_BULLISH'
    elif score > -0.5:
        return 'NEUTRAL'
    elif score > -2.0:
        return 'MODERATELY_BEARISH'
    else:
        return 'STRONGLY_BEARISH'
