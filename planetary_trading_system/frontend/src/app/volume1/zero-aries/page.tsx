'use client';

import { useState } from 'react';
import Header from '@/components/layout/Header';
import { Card, Button } from '@/components/common';

type TabType = 'analysis' | 'console' | 'book-example' | 'tutorial' | 'confluence' | 'backtest' | 'forecast';

export default function ZeroAriesPage() {
  const [targetDate, setTargetDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [targetDegree, setTargetDegree] = useState<string>('');
  const [targetPrice, setTargetPrice] = useState<string>('');
  const [selectedAsset, setSelectedAsset] = useState<string>('AUTO');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any>(null);
  const [priceResults, setPriceResults] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<TabType>('analysis');
  const [consoleLog, setConsoleLog] = useState<string[]>([]);
  const [confluenceDate, setConfluenceDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [confluencePrice, setConfluencePrice] = useState<string>('4341');
  const [confluenceAsset, setConfluenceAsset] = useState<string>('GOLD');
  const [confluenceResults, setConfluenceResults] = useState<any>(null);
  const [confluenceLoading, setConfluenceLoading] = useState(false);

  // Asset-specific harmonics based on Jenkins methodology
  const assetHarmonics: { [key: string]: { name: string, symbol: string, divisor: number, notes: string, priceRange: string } } = {
    'AUTO': { name: 'Auto-Detect', symbol: '🔄', divisor: 1, notes: 'Automatically finds best harmonic', priceRange: 'Any' },
    'BTC': { name: 'Bitcoin', symbol: '₿', divisor: 100, notes: 'High-priced: divide by 100', priceRange: '$10K-$200K' },
    'ETH': { name: 'Ethereum', symbol: 'Ξ', divisor: 10, notes: 'Medium-high: divide by 10', priceRange: '$500-$10K' },
    'GOLD': { name: 'Gold (XAU)', symbol: '🥇', divisor: 36, notes: 'Modern: ÷36 ($10 increments) - 90% accuracy on turns', priceRange: '$1000-$3000' },
    'SILVER': { name: 'Silver (XAG)', symbol: '🥈', divisor: 0.1, notes: 'Low-priced: multiply by 10', priceRange: '$15-$50' },
    'SPY': { name: 'S&P 500 ETF', symbol: '📈', divisor: 1, notes: 'Medium: direct conversion', priceRange: '$300-$600' },
    'AAPL': { name: 'Apple', symbol: '🍎', divisor: 0.5, notes: 'Medium: multiply by 2', priceRange: '$100-$300' },
    'TSLA': { name: 'Tesla', symbol: '⚡', divisor: 1, notes: 'Medium-high: direct', priceRange: '$100-$500' },
    'NVDA': { name: 'NVIDIA', symbol: '🎮', divisor: 0.3, notes: 'High: multiply by ~3', priceRange: '$100-$200' },
    'OIL': { name: 'Crude Oil (CL)', symbol: '🛢️', divisor: 0.25, notes: 'Low: multiply by 4', priceRange: '$50-$150' },
    'EURUSD': { name: 'EUR/USD', symbol: '💱', divisor: 0.003, notes: 'Forex: multiply by ~333', priceRange: '0.90-1.20' },
    'DJI': { name: 'Dow Jones', symbol: '📊', divisor: 100, notes: 'Index: divide by 100', priceRange: '$30K-$50K' },
    'SOYBEAN': { name: 'Soybeans (ZS)', symbol: '🫘', divisor: 3, notes: 'Gann commodity: divide by 3', priceRange: '$800-$1800' },
    'CORN': { name: 'Corn (ZC)', symbol: '🌽', divisor: 1.5, notes: 'Gann commodity: divide by 1.5', priceRange: '$300-$800' },
  };

  // Auto-detect best harmonic based on price
  const autoDetectHarmonic = (price: number): { divisor: number, label: string } => {
    // Goal: convert price to a degree between 0-360 (or a small multiple)
    if (price < 1) {
      return { divisor: 0.003, label: '×333 (Forex)' };
    } else if (price < 50) {
      return { divisor: 0.1, label: '×10 (Low-priced)' };
    } else if (price < 360) {
      return { divisor: 1, label: '×1 (Direct)' };
    } else if (price < 1000) {
      return { divisor: 3, label: '÷3 (Medium)' };
    } else if (price < 3600) {
      return { divisor: 10, label: '÷10 (High)' };
    } else if (price < 36000) {
      return { divisor: 100, label: '÷100 (Very High)' };
    } else {
      return { divisor: 1000, label: '÷1000 (Extreme)' };
    }
  };

  // Zodiac signs with their degree ranges
  const zodiacSigns = [
    { name: 'Aries', symbol: '♈', start: 0, element: 'Fire', quality: 'Cardinal' },
    { name: 'Taurus', symbol: '♉', start: 30, element: 'Earth', quality: 'Fixed' },
    { name: 'Gemini', symbol: '♊', start: 60, element: 'Air', quality: 'Mutable' },
    { name: 'Cancer', symbol: '♋', start: 90, element: 'Water', quality: 'Cardinal' },
    { name: 'Leo', symbol: '♌', start: 120, element: 'Fire', quality: 'Fixed' },
    { name: 'Virgo', symbol: '♍', start: 150, element: 'Earth', quality: 'Mutable' },
    { name: 'Libra', symbol: '♎', start: 180, element: 'Air', quality: 'Cardinal' },
    { name: 'Scorpio', symbol: '♏', start: 210, element: 'Water', quality: 'Fixed' },
    { name: 'Sagittarius', symbol: '♐', start: 240, element: 'Fire', quality: 'Mutable' },
    { name: 'Capricorn', symbol: '♑', start: 270, element: 'Earth', quality: 'Cardinal' },
    { name: 'Aquarius', symbol: '♒', start: 300, element: 'Air', quality: 'Fixed' },
    { name: 'Pisces', symbol: '♓', start: 330, element: 'Water', quality: 'Mutable' },
  ];

  // Seasonal turn dates (15° increments from March 20)
  const seasonalDates = [
    { date: 'Mar 20', degree: 0, significance: 'Vernal Equinox - 0° Aries' },
    { date: 'Apr 6', degree: 15, significance: '15° Sun' },
    { date: 'Apr 20', degree: 30, significance: '0° Taurus' },
    { date: 'May 6', degree: 45, significance: 'Fixed Cross 45°' },
    { date: 'May 21', degree: 60, significance: '0° Gemini' },
    { date: 'Jun 6', degree: 75, significance: '15° Gemini' },
    { date: 'Jun 21', degree: 90, significance: 'Summer Solstice - 0° Cancer' },
    { date: 'Jul 7', degree: 105, significance: '15° Cancer' },
    { date: 'Jul 23', degree: 120, significance: '0° Leo' },
    { date: 'Aug 8', degree: 135, significance: 'Fixed Cross 135°' },
    { date: 'Aug 23', degree: 150, significance: '0° Virgo' },
    { date: 'Sep 8', degree: 165, significance: '15° Virgo' },
    { date: 'Sep 23', degree: 180, significance: 'Autumnal Equinox - 0° Libra' },
    { date: 'Oct 8', degree: 195, significance: '15° Libra' },
    { date: 'Oct 23', degree: 210, significance: '0° Scorpio' },
    { date: 'Nov 7', degree: 225, significance: 'Fixed Cross 225°' },
    { date: 'Nov 22', degree: 240, significance: '0° Sagittarius' },
    { date: 'Dec 7', degree: 255, significance: '15° Sagittarius' },
    { date: 'Dec 21', degree: 270, significance: 'Winter Solstice - 0° Capricorn' },
    { date: 'Jan 6', degree: 285, significance: '15° Capricorn' },
    { date: 'Jan 20', degree: 300, significance: '0° Aquarius' },
    { date: 'Feb 4', degree: 315, significance: 'Fixed Cross 315°' },
    { date: 'Feb 19', degree: 330, significance: '0° Pisces' },
    { date: 'Mar 6', degree: 345, significance: '15° Pisces' },
  ];

  const runAnalysis = async () => {
    setLoading(true);
    const logs: string[] = [];

    logs.push(`=== ZERO ARIES ANALYSIS ===`);
    logs.push(`Target Date: ${targetDate}`);
    logs.push(``);

    // Calculate degree from date
    const target = new Date(targetDate);
    const year = target.getFullYear();
    const vernalEquinox = new Date(year, 2, 20); // March 20

    let daysDiff = Math.floor((target.getTime() - vernalEquinox.getTime()) / (1000 * 60 * 60 * 24));
    if (daysDiff < 0) {
      daysDiff += 365;
    }

    const sunDegree = daysDiff % 360;

    logs.push(`--- DEGREE CALCULATION ---`);
    logs.push(`Days from March 20: ${daysDiff}`);
    logs.push(`Sun approximate degree: ${sunDegree}°`);
    logs.push(``);

    // Find zodiac sign
    const signIndex = Math.floor(sunDegree / 30);
    const sign = zodiacSigns[signIndex];
    const degreeInSign = sunDegree % 30;

    logs.push(`--- ZODIAC POSITION ---`);
    logs.push(`Sign: ${sign.name} (${sign.symbol})`);
    logs.push(`Degree in sign: ${degreeInSign.toFixed(1)}°`);
    logs.push(`Element: ${sign.element}`);
    logs.push(`Quality: ${sign.quality}`);
    logs.push(``);

    // Find nearest seasonal dates
    const nearestDates = seasonalDates.filter(sd => {
      const diff = Math.abs(sd.degree - sunDegree);
      return diff <= 15 || (360 - diff) <= 15;
    });

    logs.push(`--- NEARBY SEASONAL DATES ---`);
    nearestDates.forEach(sd => {
      logs.push(`  ${sd.date}: ${sd.degree}° - ${sd.significance}`);
    });

    // Calculate price equivalents for MULTIPLE ASSETS
    logs.push(``);
    logs.push(`--- ASSET-SPECIFIC PRICE EQUIVALENTS ---`);
    logs.push(`Prices that resonate with today's Sun degree (${sunDegree}°):`);
    logs.push(``);

    const assetPrices: { [key: string]: number[] } = {};

    // Gold (÷36)
    logs.push(`🥇 GOLD (÷36 harmonic):`);
    const goldPrices = [];
    for (let cycle = 0; cycle <= 8; cycle++) {
      const price = (sunDegree + (cycle * 360)) * 36;
      goldPrices.push(price);
    }
    assetPrices['GOLD'] = goldPrices;
    logs.push(`   ${goldPrices.filter(p => p > 1000 && p < 5000).map(p => '$' + p.toLocaleString()).join(', ')}`);

    // BTC (÷100)
    logs.push(`₿ BITCOIN (÷100 harmonic):`);
    const btcPrices = [];
    for (let cycle = 0; cycle <= 3; cycle++) {
      const price = (sunDegree + (cycle * 360)) * 100;
      btcPrices.push(price);
    }
    assetPrices['BTC'] = btcPrices;
    logs.push(`   ${btcPrices.filter(p => p > 10000 && p < 200000).map(p => '$' + p.toLocaleString()).join(', ')}`);

    // SPY (÷1 direct)
    logs.push(`📈 SPY (÷1 direct):`);
    const spyPrices = [];
    for (let cycle = 0; cycle <= 2; cycle++) {
      const price = sunDegree + (cycle * 360);
      spyPrices.push(price);
    }
    assetPrices['SPY'] = spyPrices;
    logs.push(`   ${spyPrices.filter(p => p > 300 && p < 700).map(p => '$' + p.toLocaleString()).join(', ')}`);

    logs.push(``);
    logs.push(`--- TRADING INTERPRETATION ---`);
    logs.push(`Sun at ${sunDegree}° ${sign.name} today means:`);
    logs.push(`• Assets at prices above are in RESONANCE with today`);
    logs.push(`• These price levels may act as support/resistance TODAY`);
    logs.push(`• Watch for price to touch these levels for potential turns`);
    logs.push(``);
    logs.push(`⚠️ This is NOT a buy/sell signal - it's a SENSITIVITY indicator.`);
    logs.push(`   Combine with aspects, retrogrades, and other confirmations.`);

    setResults({
      sunDegree,
      sign,
      degreeInSign,
      nearestDates,
      priceEquivalents: Array.from({ length: 6 }, (_, i) => sunDegree + (i * 360)),
      assetPrices
    });

    logs.push(``);
    logs.push(`=== ANALYSIS COMPLETE ===`);
    setConsoleLog(logs);
    setLoading(false);
  };

  const convertDegreeToDate = () => {
    const deg = parseFloat(targetDegree);
    if (isNaN(deg) || deg < 0 || deg >= 360) return;

    const logs: string[] = [];
    logs.push(`=== DEGREE TO DATE CONVERSION ===`);
    logs.push(`Input Degree: ${deg}°`);
    logs.push(``);

    // March 20 + degree days
    const year = new Date().getFullYear();
    const baseDate = new Date(year, 2, 20);
    const targetDateCalc = new Date(baseDate.getTime() + deg * 24 * 60 * 60 * 1000);

    logs.push(`--- RESULT ---`);
    logs.push(`Date: ${targetDateCalc.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })}`);
    logs.push(``);

    // Find sign
    const signIndex = Math.floor(deg / 30);
    const sign = zodiacSigns[signIndex];
    logs.push(`Zodiac: ${deg.toFixed(1)}° = ${(deg % 30).toFixed(1)}° ${sign.name}`);

    setConsoleLog(logs);
    setActiveTab('console');
  };

  const convertPriceToDegree = () => {
    const price = parseFloat(targetPrice);
    if (isNaN(price) || price <= 0) return;

    const logs: string[] = [];
    logs.push(`=== PRICE TO DEGREE CONVERSION ===`);
    logs.push(`Input Price: $${price.toLocaleString()}`);
    logs.push(`Selected Asset: ${assetHarmonics[selectedAsset].name}`);
    logs.push(``);

    // Gann's note on harmonics
    logs.push(`--- GANN'S PRINCIPLE ---`);
    logs.push(`"The scale must be adjusted to fit the price range`);
    logs.push(` of the commodity being studied." - W.D. Gann`);
    logs.push(``);

    let divisor: number;
    let harmonicLabel: string;

    if (selectedAsset === 'AUTO') {
      const detected = autoDetectHarmonic(price);
      divisor = detected.divisor;
      harmonicLabel = detected.label;
      logs.push(`--- AUTO-DETECTED HARMONIC ---`);
      logs.push(`Best fit: ${harmonicLabel}`);
    } else {
      const asset = assetHarmonics[selectedAsset];
      divisor = asset.divisor;
      harmonicLabel = divisor >= 1 ? `÷${divisor}` : `×${(1/divisor).toFixed(0)}`;
      logs.push(`--- ASSET HARMONIC ---`);
      logs.push(`${asset.name}: ${asset.notes}`);
      logs.push(`Harmonic: ${harmonicLabel}`);
    }

    // Explain the formula
    logs.push(``);
    logs.push(`--- FORMULA ---`);
    logs.push(`divisor = 360° / (price per degree)`);
    if (divisor >= 1) {
      const pricePerDegree = 360 / divisor;
      logs.push(`${divisor} = 360° / $${pricePerDegree.toFixed(2)}`);
      logs.push(`→ Every $${pricePerDegree.toFixed(2)} = 1° movement`);
      logs.push(`→ Full cycle (360°) = $${(360 * pricePerDegree).toLocaleString()}`);
    } else {
      const multiplier = 1 / divisor;
      logs.push(`Multiplier: ×${multiplier.toFixed(0)}`);
    }

    logs.push(``);
    logs.push(`--- CALCULATION ---`);

    const rawDegree = price / divisor;
    const normalizedDegree = rawDegree % 360;
    const fullCycles = Math.floor(rawDegree / 360);

    logs.push(`Raw: $${price} ${divisor >= 1 ? '÷' : '×'} ${divisor >= 1 ? divisor : (1/divisor).toFixed(0)} = ${rawDegree.toFixed(2)}°`);
    logs.push(`Full cycles: ${fullCycles} (completed ${fullCycles} × 360° circles)`);
    logs.push(`Normalized: ${normalizedDegree.toFixed(2)}° (position in current circle)`);
    logs.push(``);

    // Find zodiac sign
    const signIndex = Math.floor(normalizedDegree / 30);
    const sign = zodiacSigns[signIndex];
    const degreeInSign = normalizedDegree % 30;

    logs.push(`--- ZODIAC POSITION ---`);
    logs.push(`${normalizedDegree.toFixed(1)}° = ${degreeInSign.toFixed(1)}° ${sign.name} ${sign.symbol}`);
    logs.push(`Element: ${sign.element} | Quality: ${sign.quality}`);
    logs.push(``);

    // Calculate anniversary date
    const year = new Date().getFullYear();
    const baseDate = new Date(year, 2, 20);
    const anniversaryDate = new Date(baseDate.getTime() + normalizedDegree * 24 * 60 * 60 * 1000);

    logs.push(`--- ANNIVERSARY DATE (SENSITIVITY WINDOW) ---`);
    logs.push(`Date: ${anniversaryDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })} each year`);
    logs.push(``);
    logs.push(`⚠️  IMPORTANT: Anniversary dates show when the Sun`);
    logs.push(`    transits this price's degree - a SENSITIVITY window,`);
    logs.push(`    not a guaranteed turn date. Actual turns need`);
    logs.push(`    additional planetary triggers (aspects, retrogrades).`);
    logs.push(``);

    // Show related prices at same degree
    logs.push(`--- RELATED PRICES (same degree) ---`);
    for (let cycle = 0; cycle <= 5; cycle++) {
      const relatedDegree = normalizedDegree + (cycle * 360);
      const relatedPrice = relatedDegree * divisor;
      const marker = cycle === fullCycles ? ' ← current' : '';
      logs.push(`  Cycle ${cycle}: ${relatedDegree.toFixed(0)}° = $${relatedPrice.toLocaleString(undefined, {maximumFractionDigits: 2})}${marker}`);
    }

    // Show ALL harmonics comparison with anniversary dates
    logs.push(``);
    logs.push(`--- ALL HARMONICS COMPARISON ---`);
    logs.push(`(Different harmonics give different degrees & anniversaries)`);
    logs.push(``);
    const harmonicsToCompare = [
      { label: '÷1 (Direct)', divisor: 1, note: 'price = degree' },
      { label: '÷3.6 ($100)', divisor: 3.6, note: '360/100' },
      { label: '÷7.2 ($50)', divisor: 7.2, note: '360/50 - Gann era' },
      { label: '÷10', divisor: 10, note: 'simple' },
      { label: '÷36 ($10)', divisor: 36, note: '360/10 - modern Gold' },
      { label: '÷100', divisor: 100, note: 'high prices' },
    ];

    logs.push(`${'Harmonic'.padEnd(14)} ${'Degree'.padStart(8)} ${'Sign'.padEnd(12)} ${'Anniversary'.padEnd(12)}`);
    logs.push(`${'-'.repeat(50)}`);

    harmonicsToCompare.forEach(h => {
      const deg = (price / h.divisor) % 360;
      const s = zodiacSigns[Math.floor(deg / 30)];
      const annDate = new Date(baseDate.getTime() + deg * 24 * 60 * 60 * 1000);
      const annStr = annDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const marker = h.divisor === divisor ? ' ✓' : '';
      logs.push(`${h.label.padEnd(14)} ${deg.toFixed(1).padStart(7)}° ${(s.symbol + ' ' + s.name).padEnd(12)} ${annStr}${marker}`);
    });

    logs.push(``);
    logs.push(`💡 TIP: Test which harmonic's key degrees align with`);
    logs.push(`   actual historical turns for your specific asset.`);

    setPriceResults({
      price,
      divisor,
      harmonicLabel,
      rawDegree,
      normalizedDegree,
      fullCycles,
      sign,
      degreeInSign,
      anniversaryDate: anniversaryDate.toLocaleDateString('en-US', { month: 'long', day: 'numeric' }),
      relatedPrices: Array.from({ length: 6 }, (_, i) => ({
        cycle: i,
        degree: normalizedDegree + (i * 360),
        price: (normalizedDegree + (i * 360)) * divisor
      }))
    });

    logs.push(``);
    logs.push(`=== CONVERSION COMPLETE ===`);
    setConsoleLog(logs);
    setActiveTab('console');
  };

  const tabs = [
    { id: 'analysis' as TabType, label: 'Analysis' },
    { id: 'console' as TabType, label: 'Console' },
    { id: 'confluence' as TabType, label: '🎯 Confluence' },
    { id: 'forecast' as TabType, label: '📅 Forecast' },
    { id: 'book-example' as TabType, label: 'Book Example' },
    { id: 'tutorial' as TabType, label: 'Tutorial' },
    { id: 'backtest' as TabType, label: 'Backtest' },
  ];

  // Generate upcoming events for forecast
  const generateForecast = () => {
    const events: { date: Date; type: string; name: string; degree: number; importance: 'critical' | 'high' | 'medium' }[] = [];
    const today = new Date();
    const year = today.getFullYear();

    // Eclipses 2025-2026 (known dates)
    const eclipses = [
      { date: new Date(2025, 2, 29), name: 'Partial Solar Eclipse', type: 'eclipse' },
      { date: new Date(2025, 3, 13), name: 'Total Lunar Eclipse', type: 'eclipse' },
      { date: new Date(2025, 8, 7), name: 'Total Lunar Eclipse', type: 'eclipse' },
      { date: new Date(2025, 8, 21), name: 'Partial Solar Eclipse', type: 'eclipse' },
      { date: new Date(2026, 1, 17), name: 'Annular Solar Eclipse', type: 'eclipse' },
      { date: new Date(2026, 2, 3), name: 'Total Lunar Eclipse', type: 'eclipse' },
      { date: new Date(2026, 7, 12), name: 'Partial Solar Eclipse', type: 'eclipse' },
      { date: new Date(2026, 7, 28), name: 'Partial Lunar Eclipse', type: 'eclipse' },
    ];

    eclipses.forEach(e => {
      if (e.date >= today) {
        events.push({ ...e, degree: 0, importance: 'critical' });
      }
    });

    // Cardinal Ingresses (seasonal dates) - same every year
    const cardinalDates = [
      { month: 2, day: 20, name: 'Vernal Equinox (0° Aries)', degree: 0 },
      { month: 5, day: 21, name: 'Summer Solstice (0° Cancer)', degree: 90 },
      { month: 8, day: 23, name: 'Autumnal Equinox (0° Libra)', degree: 180 },
      { month: 11, day: 21, name: 'Winter Solstice (0° Capricorn)', degree: 270 },
    ];

    // Fixed Cross dates
    const fixedCrossDates = [
      { month: 4, day: 5, name: 'Fixed Cross (15° Taurus)', degree: 45 },
      { month: 7, day: 7, name: 'Fixed Cross (15° Leo)', degree: 135 },
      { month: 10, day: 7, name: 'Fixed Cross (15° Scorpio)', degree: 225 },
      { month: 1, day: 4, name: 'Fixed Cross (15° Aquarius)', degree: 315 },
    ];

    // Sign Ingresses
    const signIngresses = [
      { month: 3, day: 20, name: '0° Taurus', degree: 30 },
      { month: 4, day: 21, name: '0° Gemini', degree: 60 },
      { month: 6, day: 22, name: '0° Leo', degree: 120 },
      { month: 7, day: 23, name: '0° Virgo', degree: 150 },
      { month: 9, day: 23, name: '0° Scorpio', degree: 210 },
      { month: 10, day: 22, name: '0° Sagittarius', degree: 240 },
      { month: 0, day: 20, name: '0° Aquarius', degree: 300 },
      { month: 1, day: 19, name: '0° Pisces', degree: 330 },
    ];

    // Add cardinal dates for current and next year
    [year, year + 1].forEach(y => {
      cardinalDates.forEach(cd => {
        const date = new Date(y, cd.month, cd.day);
        if (date >= today && date <= new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000)) {
          events.push({ date, type: 'cardinal', name: cd.name, degree: cd.degree, importance: 'critical' });
        }
      });

      fixedCrossDates.forEach(fc => {
        const date = new Date(y, fc.month, fc.day);
        if (date >= today && date <= new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000)) {
          events.push({ date, type: 'fixed-cross', name: fc.name, degree: fc.degree, importance: 'high' });
        }
      });

      signIngresses.forEach(si => {
        const date = new Date(y, si.month, si.day);
        if (date >= today && date <= new Date(today.getTime() + 90 * 24 * 60 * 60 * 1000)) {
          events.push({ date, type: 'ingress', name: si.name, degree: si.degree, importance: 'medium' });
        }
      });
    });

    // Mercury Retrograde periods 2025-2026
    const mercuryRx = [
      { start: new Date(2025, 2, 15), end: new Date(2025, 3, 7), name: 'Mercury Rx (Aries)' },
      { start: new Date(2025, 6, 18), end: new Date(2025, 7, 11), name: 'Mercury Rx (Leo)' },
      { start: new Date(2025, 10, 9), end: new Date(2025, 10, 29), name: 'Mercury Rx (Sagittarius)' },
      { start: new Date(2026, 2, 1), end: new Date(2026, 2, 21), name: 'Mercury Rx (Pisces)' },
      { start: new Date(2026, 6, 2), end: new Date(2026, 6, 26), name: 'Mercury Rx (Cancer)' },
    ];

    mercuryRx.forEach(rx => {
      if (rx.start >= today || rx.end >= today) {
        events.push({ date: rx.start, type: 'mercury-rx-start', name: `${rx.name} Begins`, degree: 0, importance: 'high' });
        events.push({ date: rx.end, type: 'mercury-rx-end', name: `${rx.name} Ends`, degree: 0, importance: 'high' });
      }
    });

    // Sort by date
    events.sort((a, b) => a.date.getTime() - b.date.getTime());

    return events.slice(0, 20); // Next 20 events
  };

  const forecastEvents = generateForecast();

  // Confluence Checker - checks multiple factors for signal strength
  const checkConfluence = async () => {
    setConfluenceLoading(true);
    const price = parseFloat(confluencePrice);
    if (isNaN(price) || price <= 0) {
      setConfluenceLoading(false);
      return;
    }

    const checkDate = new Date(confluenceDate);
    const year = checkDate.getFullYear();
    const vernalEquinox = new Date(year, 2, 20);
    let daysDiff = Math.floor((checkDate.getTime() - vernalEquinox.getTime()) / (1000 * 60 * 60 * 24));
    if (daysDiff < 0) daysDiff += 365;
    const sunDegree = daysDiff % 360;

    // Get asset harmonic
    const asset = assetHarmonics[confluenceAsset] || assetHarmonics['AUTO'];
    const divisor = asset.divisor;
    const priceDegree = (price / divisor) % 360;

    // Calculate Moon phase (approximate)
    const lunarCycle = 29.53;
    const knownNewMoon = new Date(2024, 0, 11); // Jan 11, 2024 was a new moon
    const daysSinceNewMoon = Math.floor((checkDate.getTime() - knownNewMoon.getTime()) / (1000 * 60 * 60 * 24));
    const moonPhase = (daysSinceNewMoon % lunarCycle) / lunarCycle;
    const moonPhaseName = moonPhase < 0.03 || moonPhase > 0.97 ? 'New Moon' :
                          moonPhase > 0.47 && moonPhase < 0.53 ? 'Full Moon' :
                          moonPhase > 0.22 && moonPhase < 0.28 ? 'First Quarter' :
                          moonPhase > 0.72 && moonPhase < 0.78 ? 'Last Quarter' : 'Waxing/Waning';

    // Seasonal dates check
    const seasonalDegrees = [0, 15, 30, 45, 60, 75, 90, 105, 120, 135, 150, 165, 180, 195, 210, 225, 240, 255, 270, 285, 300, 315, 330, 345];
    const nearestSeasonal = seasonalDegrees.reduce((prev, curr) =>
      Math.abs(curr - sunDegree) < Math.abs(prev - sunDegree) ? curr : prev
    );
    const seasonalDistance = Math.min(Math.abs(sunDegree - nearestSeasonal), 360 - Math.abs(sunDegree - nearestSeasonal));

    // Sun-Price alignment
    const sunPriceDistance = Math.min(Math.abs(sunDegree - priceDegree), 360 - Math.abs(sunDegree - priceDegree));

    // Mercury retrograde periods (approximate for 2024-2026)
    const mercuryRetrogrades = [
      { start: new Date(2024, 3, 1), end: new Date(2024, 3, 25) },
      { start: new Date(2024, 7, 5), end: new Date(2024, 7, 28) },
      { start: new Date(2024, 10, 25), end: new Date(2024, 11, 15) },
      { start: new Date(2025, 2, 15), end: new Date(2025, 3, 7) },
      { start: new Date(2025, 6, 18), end: new Date(2025, 7, 11) },
      { start: new Date(2025, 10, 9), end: new Date(2025, 10, 29) },
      { start: new Date(2026, 2, 1), end: new Date(2026, 2, 21) },
    ];
    const inMercuryRx = mercuryRetrogrades.some(rx => checkDate >= rx.start && checkDate <= rx.end);

    // Eclipse windows (approximate - within 14 days of eclipse)
    const eclipses = [
      new Date(2024, 2, 25), new Date(2024, 3, 8), new Date(2024, 8, 18), new Date(2024, 9, 2),
      new Date(2025, 2, 14), new Date(2025, 2, 29), new Date(2025, 8, 7), new Date(2025, 8, 21),
      new Date(2026, 1, 17), new Date(2026, 2, 3), new Date(2026, 7, 12), new Date(2026, 7, 28),
    ];
    const nearestEclipse = eclipses.reduce((prev, curr) =>
      Math.abs(curr.getTime() - checkDate.getTime()) < Math.abs(prev.getTime() - checkDate.getTime()) ? curr : prev
    );
    const daysFromEclipse = Math.abs(Math.floor((checkDate.getTime() - nearestEclipse.getTime()) / (1000 * 60 * 60 * 24)));

    // Cardinal ingress check (Sun near 0, 90, 180, 270)
    const cardinalDegrees = [0, 90, 180, 270];
    const nearestCardinal = cardinalDegrees.reduce((prev, curr) =>
      Math.abs(curr - sunDegree) < Math.abs(prev - sunDegree) ? curr : prev
    );
    const cardinalDistance = Math.min(Math.abs(sunDegree - nearestCardinal), 360 - Math.abs(sunDegree - nearestCardinal));

    // Calculate individual scores
    const factors = [
      {
        name: 'Sun-Price Alignment',
        icon: '☉',
        description: `Sun at ${sunDegree}°, Price at ${priceDegree.toFixed(1)}°`,
        distance: sunPriceDistance,
        score: sunPriceDistance <= 3 ? 3 : sunPriceDistance <= 10 ? 2 : sunPriceDistance <= 30 ? 1 : 0,
        maxScore: 3,
        status: sunPriceDistance <= 3 ? 'EXACT' : sunPriceDistance <= 10 ? 'CLOSE' : sunPriceDistance <= 30 ? 'MODERATE' : 'NONE',
      },
      {
        name: 'Lunar Phase',
        icon: '🌙',
        description: moonPhaseName,
        score: (moonPhaseName === 'New Moon' || moonPhaseName === 'Full Moon') ? 3 :
               (moonPhaseName === 'First Quarter' || moonPhaseName === 'Last Quarter') ? 1 : 0,
        maxScore: 3,
        status: (moonPhaseName === 'New Moon' || moonPhaseName === 'Full Moon') ? 'STRONG' :
                (moonPhaseName === 'First Quarter' || moonPhaseName === 'Last Quarter') ? 'MODERATE' : 'NONE',
      },
      {
        name: 'Seasonal Date',
        icon: '📅',
        description: `${seasonalDistance}° from ${nearestSeasonal}° seasonal point`,
        distance: seasonalDistance,
        score: seasonalDistance <= 2 ? 2 : seasonalDistance <= 5 ? 1 : 0,
        maxScore: 2,
        status: seasonalDistance <= 2 ? 'ON DATE' : seasonalDistance <= 5 ? 'CLOSE' : 'NONE',
      },
      {
        name: 'Mercury Retrograde',
        icon: '☿',
        description: inMercuryRx ? 'In Mercury Retrograde' : 'Mercury Direct',
        score: inMercuryRx ? 2 : 0,
        maxScore: 2,
        status: inMercuryRx ? 'RETROGRADE' : 'DIRECT',
      },
      {
        name: 'Eclipse Window',
        icon: '🌑',
        description: `${daysFromEclipse} days from nearest eclipse`,
        distance: daysFromEclipse,
        score: daysFromEclipse <= 3 ? 3 : daysFromEclipse <= 7 ? 2 : daysFromEclipse <= 14 ? 1 : 0,
        maxScore: 3,
        status: daysFromEclipse <= 3 ? 'ECLIPSE!' : daysFromEclipse <= 7 ? 'CLOSE' : daysFromEclipse <= 14 ? 'WINDOW' : 'NONE',
      },
      {
        name: 'Cardinal Ingress',
        icon: '♈',
        description: `Sun ${cardinalDistance}° from ${nearestCardinal}° cardinal point`,
        distance: cardinalDistance,
        score: cardinalDistance <= 2 ? 2 : cardinalDistance <= 5 ? 1 : 0,
        maxScore: 2,
        status: cardinalDistance <= 2 ? 'CARDINAL' : cardinalDistance <= 5 ? 'CLOSE' : 'NONE',
      },
    ];

    const totalScore = factors.reduce((sum, f) => sum + f.score, 0);
    const maxTotalScore = factors.reduce((sum, f) => sum + f.maxScore, 0);
    const percentage = Math.round((totalScore / maxTotalScore) * 100);

    // Anniversary date for the price
    const anniversaryDate = new Date(year, 2, 20);
    anniversaryDate.setDate(anniversaryDate.getDate() + Math.round(priceDegree));

    setConfluenceResults({
      date: confluenceDate,
      price,
      asset: confluenceAsset,
      sunDegree,
      priceDegree,
      factors,
      totalScore,
      maxTotalScore,
      percentage,
      rating: percentage >= 70 ? 'STRONG' : percentage >= 40 ? 'MODERATE' : 'WEAK',
      anniversaryDate: anniversaryDate.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    });

    setConfluenceLoading(false);
  };

  // Backtest cases for Zero Aries
  const backtestCases = [
    {
      name: 'March 20 = 0° Aries',
      inputDate: '2024-03-20',
      expectedDegree: 0,
      expectedSign: 'Aries',
      bookPage: 'p.40',
      bookQuote: 'Vernal Equinox, March 20, is 0° Aries - the starting point'
    },
    {
      name: 'June 21 = 90° Cancer',
      inputDate: '2024-06-21',
      expectedDegree: 90,
      expectedSign: 'Cancer',
      bookPage: 'p.42',
      bookQuote: 'Summer Solstice, June 21, is 0° Cancer (90° from Aries)'
    },
    {
      name: 'September 23 = 180° Libra',
      inputDate: '2024-09-23',
      expectedDegree: 180,
      expectedSign: 'Libra',
      bookPage: 'p.43',
      bookQuote: 'Autumnal Equinox, September 23, is 0° Libra (180° from Aries)'
    },
    {
      name: 'December 21 = 270° Capricorn',
      inputDate: '2024-12-21',
      expectedDegree: 270,
      expectedSign: 'Capricorn',
      bookPage: 'p.44',
      bookQuote: 'Winter Solstice, December 21, is 0° Capricorn (270° from Aries)'
    },
  ];

  const runBacktest = (testCase: typeof backtestCases[0]) => {
    const target = new Date(testCase.inputDate);
    const year = target.getFullYear();
    const vernalEquinox = new Date(year, 2, 20);
    let daysDiff = Math.floor((target.getTime() - vernalEquinox.getTime()) / (1000 * 60 * 60 * 24));
    if (daysDiff < 0) daysDiff += 365;
    const degree = daysDiff % 360;
    const signIndex = Math.floor(degree / 30);
    const signs = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn', 'Aquarius', 'Pisces'];

    const degreeMatch = Math.abs(degree - testCase.expectedDegree) <= 5;
    const signMatch = signs[signIndex] === testCase.expectedSign;

    return {
      calculatedDegree: degree,
      calculatedSign: signs[signIndex],
      degreePass: degreeMatch,
      signPass: signMatch,
      overallPass: degreeMatch && signMatch
    };
  };

  return (
    <div className="min-h-screen">
      <Header
        title="Zero Aries & Seasonal Dates"
        subtitle="The starting point for all measurements - 0° Aries = March 20"
      />

      <div className="p-6 space-y-6">
        <div className="flex gap-2 border-b border-border-color pb-2">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-accent-blue text-white'
                  : 'text-text-secondary hover:text-text-primary hover:bg-bg-secondary'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'analysis' && (
          <>
            <Card>
              <div className="flex items-start gap-4">
                <span className="text-4xl">♈</span>
                <div>
                  <h3 className="font-semibold text-lg">Book Examples 1-3: Zero Aries Foundation</h3>
                  <p className="text-text-secondary mt-1">
                    Zero Aries (0°) is the first degree of Aries, occurring at the Vernal Equinox around March 20.
                    This is the starting point for all zodiacal measurements. The Sun moves approximately 1° per day,
                    completing 360° in one year. Each degree corresponds to a calendar date and a price level.
                  </p>
                  <div className="mt-3 flex gap-4 text-sm">
                    <div className="px-3 py-1 bg-accent-blue/20 text-accent-blue rounded-full">
                      1° = 1 Day
                    </div>
                    <div className="px-3 py-1 bg-accent-green/20 text-accent-green rounded-full">
                      15° = Time Zone
                    </div>
                    <div className="px-3 py-1 bg-yellow-500/20 text-yellow-500 rounded-full">
                      72 Years = 1° Precession
                    </div>
                  </div>
                </div>
              </div>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Date to Degree */}
              <Card title="Date → Degree Conversion">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-text-secondary mb-1">Select Date</label>
                    <input
                      type="date"
                      value={targetDate}
                      onChange={(e) => setTargetDate(e.target.value)}
                      className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-blue"
                    />
                  </div>
                  <Button onClick={runAnalysis} loading={loading} className="w-full">
                    Calculate Degree
                  </Button>
                </div>
              </Card>

              {/* Degree to Date */}
              <Card title="Degree → Date Conversion">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-text-secondary mb-1">Enter Degree (0-359)</label>
                    <input
                      type="number"
                      value={targetDegree}
                      onChange={(e) => setTargetDegree(e.target.value)}
                      placeholder="e.g., 27"
                      min="0"
                      max="359"
                      className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-blue"
                    />
                  </div>
                  <Button onClick={convertDegreeToDate} className="w-full">
                    Calculate Date
                  </Button>
                </div>
              </Card>

              {/* Price to Degree - NEW */}
              <Card title="Price → Degree (Asset-Specific)" className="border border-accent-purple/30">
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs text-text-secondary mb-1">Select Asset</label>
                    <select
                      value={selectedAsset}
                      onChange={(e) => setSelectedAsset(e.target.value)}
                      className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-purple"
                    >
                      {Object.entries(assetHarmonics).map(([key, asset]) => (
                        <option key={key} value={key}>
                          {asset.symbol} {asset.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-text-secondary mb-1">Enter Price</label>
                    <input
                      type="number"
                      value={targetPrice}
                      onChange={(e) => setTargetPrice(e.target.value)}
                      placeholder={selectedAsset !== 'AUTO' ? assetHarmonics[selectedAsset].priceRange : 'e.g., 2650'}
                      step="any"
                      className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-purple"
                    />
                  </div>
                  <div className="text-xs text-text-muted p-2 bg-bg-secondary rounded">
                    {assetHarmonics[selectedAsset].notes}
                  </div>
                  <Button onClick={convertPriceToDegree} className="w-full bg-accent-purple hover:bg-accent-purple/80">
                    Convert Price → Degree
                  </Button>
                </div>
              </Card>
            </div>

            {/* Price Results */}
            {priceResults && (
              <Card title={`Price Analysis: $${priceResults.price.toLocaleString()}`} className="border border-accent-purple/30">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
                  <div className="text-center p-3 bg-accent-purple/10 rounded-lg">
                    <div className="text-3xl mb-1">{priceResults.sign.symbol}</div>
                    <div className="font-bold">{priceResults.sign.name}</div>
                    <div className="text-xs text-text-muted">{priceResults.degreeInSign.toFixed(1)}° in sign</div>
                  </div>
                  <div className="text-center p-3 bg-bg-secondary rounded-lg">
                    <div className="text-2xl font-bold text-accent-purple">{priceResults.normalizedDegree.toFixed(1)}°</div>
                    <div className="text-xs text-text-muted">Normalized Degree</div>
                  </div>
                  <div className="text-center p-3 bg-bg-secondary rounded-lg">
                    <div className="text-2xl font-bold text-accent-blue">{priceResults.fullCycles}</div>
                    <div className="text-xs text-text-muted">Full Cycles</div>
                  </div>
                  <div className="text-center p-3 bg-bg-secondary rounded-lg">
                    <div className="text-lg font-bold text-accent-green">{priceResults.harmonicLabel}</div>
                    <div className="text-xs text-text-muted">Harmonic Used</div>
                  </div>
                  <div className="text-center p-3 bg-yellow-500/10 rounded-lg">
                    <div className="text-lg font-bold text-yellow-500">{priceResults.anniversaryDate}</div>
                    <div className="text-xs text-text-muted">Anniversary Date</div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Related Prices (Same Degree)</h4>
                    <div className="flex flex-wrap gap-2">
                      {priceResults.relatedPrices.map((rp: any) => (
                        <div key={rp.cycle} className={`px-3 py-1 rounded text-sm font-mono ${
                          rp.cycle === priceResults.fullCycles ? 'bg-accent-purple/20 text-accent-purple font-bold' : 'bg-bg-secondary'
                        }`}>
                          ${rp.price.toLocaleString(undefined, {maximumFractionDigits: 0})}
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <h4 className="font-semibold text-sm mb-2">Key Info</h4>
                    <div className="text-sm space-y-1">
                      <div>Raw Degree: {priceResults.rawDegree.toFixed(2)}°</div>
                      <div>Position: {priceResults.degreeInSign.toFixed(1)}° {priceResults.sign.name}</div>
                      <div>Element: {priceResults.sign.element} / {priceResults.sign.quality}</div>
                    </div>
                  </div>
                </div>
              </Card>
            )}

            {results && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card className="text-center">
                    <div className="text-4xl mb-2">{results.sign.symbol}</div>
                    <div className="text-lg font-bold text-text-primary">{results.sign.name}</div>
                    <div className="text-xs text-text-secondary">{results.sign.element} / {results.sign.quality}</div>
                  </Card>
                  <Card className="text-center">
                    <div className="text-2xl font-bold text-accent-blue">{results.sunDegree}°</div>
                    <div className="text-xs text-text-secondary">Absolute Degree</div>
                  </Card>
                  <Card className="text-center">
                    <div className="text-2xl font-bold text-accent-green">{results.degreeInSign.toFixed(1)}°</div>
                    <div className="text-xs text-text-secondary">Degree in Sign</div>
                  </Card>
                  <Card className="text-center">
                    <div className="text-2xl font-bold text-yellow-500">${results.sunDegree}</div>
                    <div className="text-xs text-text-secondary">Base Price Level</div>
                  </Card>
                </div>

                <Card title="Asset-Specific Prices at This Sun Degree" subtitle={`Prices resonating with ${results.sunDegree}° - potential support/resistance levels TODAY`}>
                  <div className="space-y-4">
                    {/* Gold */}
                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xl">🥇</span>
                        <span className="font-bold text-yellow-500">GOLD</span>
                        <span className="text-xs text-text-muted">(÷36 harmonic)</span>
                      </div>
                      {(() => {
                        const goldPrices = Array.from({ length: 9 }, (_, i) => (results.sunDegree + (i * 360)) * 36)
                          .filter(p => p > 2000 && p < 6000);
                        const currentGoldPrice = 4341; // Approximate current Gold price
                        const currentGoldDegree = (currentGoldPrice / 36) % 360;
                        const goldAnniversary = new Date(new Date().getFullYear(), 2, 20);
                        goldAnniversary.setDate(goldAnniversary.getDate() + Math.round(currentGoldDegree));

                        return goldPrices.length > 0 ? (
                          <div className="flex flex-wrap gap-2">
                            {goldPrices.map((price, idx) => (
                              <div key={idx} className="px-3 py-1 bg-yellow-500/20 rounded font-mono text-sm">
                                ${price.toLocaleString()}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="text-sm text-text-muted">
                            <div className="italic mb-2">No Gold prices in $2,000-$6,000 range resonate with {results.sunDegree}°.</div>
                            <div className="p-2 bg-yellow-500/10 rounded">
                              <div className="text-yellow-500 font-semibold">Current Gold (~${currentGoldPrice.toLocaleString()}):</div>
                              <div>• Degree: {currentGoldDegree.toFixed(1)}° Leo</div>
                              <div>• Sensitive Date: <span className="text-yellow-500 font-semibold">{goldAnniversary.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span> (when Sun hits {currentGoldDegree.toFixed(0)}°)</div>
                              <div className="text-xs mt-1 text-text-muted">Today's Sun ({results.sunDegree}°) is {Math.abs(results.sunDegree - currentGoldDegree).toFixed(0)}° away from Gold's degree</div>
                            </div>
                          </div>
                        );
                      })()}
                    </div>

                    {/* Bitcoin */}
                    <div className="p-3 bg-orange-500/10 border border-orange-500/30 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xl">₿</span>
                        <span className="font-bold text-orange-500">BITCOIN</span>
                        <span className="text-xs text-text-muted">(÷100 harmonic)</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {Array.from({ length: 4 }, (_, i) => (results.sunDegree + (i * 360)) * 100)
                          .filter(p => p > 10000 && p < 200000)
                          .map((price, idx) => (
                            <div key={idx} className="px-3 py-1 bg-orange-500/20 rounded font-mono text-sm">
                              ${price.toLocaleString()}
                            </div>
                          ))}
                      </div>
                    </div>

                    {/* SPY */}
                    <div className="p-3 bg-accent-blue/10 border border-accent-blue/30 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="text-xl">📈</span>
                        <span className="font-bold text-accent-blue">SPY / Indices</span>
                        <span className="text-xs text-text-muted">(÷1 direct)</span>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {results.priceEquivalents
                          .filter((p: number) => p > 300 && p < 700)
                          .map((price: number, idx: number) => (
                            <div key={idx} className="px-3 py-1 bg-accent-blue/20 rounded font-mono text-sm">
                              ${price}
                            </div>
                          ))}
                      </div>
                    </div>

                    {/* Interpretation */}
                    <div className="p-3 bg-accent-red/10 border border-accent-red/30 rounded-lg">
                      <div className="font-bold text-accent-red mb-1">⚠️ How to Use This</div>
                      <p className="text-sm text-text-secondary">
                        These prices are in <strong>resonance</strong> with today's Sun position ({results.sunDegree}° {results.sign.name}).
                        They may act as support/resistance levels. This is a <strong>sensitivity indicator</strong>, not a trade signal.
                        Watch for price touching these levels combined with other confirmations.
                      </p>
                    </div>
                  </div>
                </Card>
              </>
            )}

            {/* Seasonal Turn Dates Table */}
            <Card title="Gann's Seasonal Turn Dates (15° increments)">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-color">
                      <th className="text-left py-2 px-3 text-text-muted">Date</th>
                      <th className="text-right py-2 px-3 text-text-muted">Degree</th>
                      <th className="text-left py-2 px-3 text-text-muted">Significance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {seasonalDates.map((sd, idx) => (
                      <tr key={idx} className={`border-b border-border-color/50 ${
                        sd.degree % 90 === 0 ? 'bg-accent-blue/10' :
                        sd.degree % 45 === 0 ? 'bg-accent-green/10' : ''
                      }`}>
                        <td className="py-2 px-3 font-mono">{sd.date}</td>
                        <td className="py-2 px-3 text-right font-mono">{sd.degree}°</td>
                        <td className="py-2 px-3 text-text-secondary">{sd.significance}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* Zodiac Wheel */}
            <Card title="Zodiac Degree Reference">
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                {zodiacSigns.map((sign) => (
                  <div key={sign.name} className="p-3 bg-bg-secondary rounded-lg text-center">
                    <div className="text-2xl mb-1">{sign.symbol}</div>
                    <div className="font-semibold text-text-primary">{sign.name}</div>
                    <div className="text-xs text-text-muted">{sign.start}°-{sign.start + 29}°</div>
                    <div className="text-xs mt-1">
                      <span className={`px-1.5 py-0.5 rounded ${
                        sign.element === 'Fire' ? 'bg-red-500/20 text-red-400' :
                        sign.element === 'Earth' ? 'bg-green-500/20 text-green-400' :
                        sign.element === 'Air' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-blue-500/20 text-blue-400'
                      }`}>
                        {sign.element}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </>
        )}

        {activeTab === 'console' && (
          <Card title="Analysis Console" subtitle="Step-by-step calculation log">
            <div className="bg-gray-900 rounded-lg p-4 font-mono text-sm h-[600px] overflow-y-auto">
              {consoleLog.length === 0 ? (
                <div className="text-gray-500">Run analysis to see calculation steps...</div>
              ) : (
                consoleLog.map((line, idx) => (
                  <div key={idx} className={`${
                    line.startsWith('===') ? 'text-accent-blue font-bold mt-2' :
                    line.startsWith('---') ? 'text-yellow-500 font-bold mt-2' :
                    line.startsWith('  ') ? 'text-gray-400 ml-4' :
                    'text-gray-300'
                  }`}>
                    {line || '\u00A0'}
                  </div>
                ))
              )}
            </div>
          </Card>
        )}

        {activeTab === 'book-example' && (
          <Card title="Book Example: Zero Aries Foundation (p.40-48)" subtitle="Date/Degree Conversions from Jenkins Volume I">
            <div className="space-y-6 text-text-secondary">
              <div className="p-4 bg-bg-secondary rounded-lg">
                <h4 className="font-bold text-text-primary mb-2">The Foundation of All Measurements</h4>
                <p>
                  Zero Aries (0°) is the starting point for all zodiacal measurements. It occurs at the
                  Vernal Equinox around March 20 when the Sun crosses the celestial equator.
                </p>
              </div>

              <div className="p-4 bg-accent-blue/10 border border-accent-blue/30 rounded-lg">
                <h4 className="font-bold text-accent-blue mb-3">Step-by-Step: Date to Degree Conversion</h4>
                <div className="space-y-4">
                  <div>
                    <div className="font-mono text-sm text-accent-blue">Step 1: Identify the Reference Point</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <div>0° Aries = March 20 (Vernal Equinox)</div>
                      <div>This is the "zero point" of the zodiac</div>
                    </div>
                  </div>

                  <div>
                    <div className="font-mono text-sm text-accent-blue">Step 2: Count Days from March 20</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <div>Example: April 17th</div>
                      <div>Days from March 20 = <span className="text-accent-green">27 days</span></div>
                    </div>
                  </div>

                  <div>
                    <div className="font-mono text-sm text-accent-blue">Step 3: Days = Degrees (Sun moves 1°/day)</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <div>27 days = <span className="text-accent-green">27°</span></div>
                      <div>April 17 = 27° Aries</div>
                    </div>
                  </div>

                  <div>
                    <div className="font-mono text-sm text-accent-blue">Step 4: Find Price Equivalents</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <div>27° = $27, $387, $747, $1107...</div>
                      <div className="text-yellow-500">All prices at 27° share this anniversary date!</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-accent-purple/10 border border-accent-purple/30 rounded-lg">
                <h4 className="font-bold text-accent-purple mb-3">Step-by-Step: Degree to Date Conversion</h4>
                <div className="space-y-4">
                  <div>
                    <div className="font-mono text-sm text-accent-purple">Step 1: Get the Zodiac Degree</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <div>Example: Planet at 120° (Leo)</div>
                    </div>
                  </div>

                  <div>
                    <div className="font-mono text-sm text-accent-purple">Step 2: Add Days to March 20</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <div>March 20 + 120 days = <span className="text-accent-green">July 18</span></div>
                    </div>
                  </div>

                  <div>
                    <div className="font-mono text-sm text-accent-purple">Step 3: This is the Anniversary Date</div>
                    <div className="font-mono bg-gray-900 p-2 rounded mt-2 text-sm">
                      <span className="text-accent-red">Watch July 18 for turns on assets at 120°!</span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-accent-green/10 border border-accent-green/30 rounded-lg">
                <h4 className="font-bold text-accent-green mb-3">Gann's Frequency Breakpoints</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="font-semibold mb-2">Divide by 2 (Square family):</div>
                    <div className="font-mono text-sm bg-gray-900 p-2 rounded">
                      <div>360° → 180° → 90° → 45°</div>
                      <div>→ 22.5° → 11.25° → 5.625°</div>
                    </div>
                  </div>
                  <div>
                    <div className="font-semibold mb-2">Divide by 3 (Trine family):</div>
                    <div className="font-mono text-sm bg-gray-900 p-2 rounded">
                      <div>360° → 120° → 60° → 30°</div>
                      <div>→ 15° → 7.5° → 3.75°</div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <h4 className="font-bold text-yellow-500 mb-2">Key Cardinal Dates</h4>
                <div className="grid grid-cols-4 gap-2 font-mono text-xs">
                  <div className="p-2 bg-gray-900 rounded text-center">Mar 20<br/>0° ♈</div>
                  <div className="p-2 bg-gray-900 rounded text-center">Jun 21<br/>90° ♋</div>
                  <div className="p-2 bg-gray-900 rounded text-center">Sep 23<br/>180° ♎</div>
                  <div className="p-2 bg-gray-900 rounded text-center">Dec 21<br/>270° ♑</div>
                </div>
                <p className="text-sm mt-3">These are equinoxes & solstices - the most powerful turn dates!</p>
              </div>

              <div className="p-4 bg-accent-green/10 border border-accent-green/30 rounded-lg">
                <h4 className="font-bold text-accent-green mb-2">Trading Application</h4>
                <ol className="list-decimal list-inside space-y-2">
                  <li>Convert significant prices to degrees (price MOD 360)</li>
                  <li>Calculate the anniversary date (March 20 + degree)</li>
                  <li>Watch 15° interval dates for seasonal turns</li>
                  <li>Cardinal points (0°, 90°, 180°, 270°) are strongest</li>
                  <li>Track when planets hit these key degrees</li>
                </ol>
              </div>

              <div className="p-4 bg-accent-red/10 border border-accent-red/30 rounded-lg">
                <h4 className="font-bold text-accent-red mb-2">Key Trading Insight</h4>
                <p>
                  "Prices gravitate to planetary locations. A planet at 34° means price tends to $34, $394 (360+34), $754 (720+34), etc.
                  The same degree resonates across all 360° cycles."
                </p>
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'tutorial' && (
          <Card title="Tutorial: Zero Aries Practical Guide" subtitle="Learn with real Gold examples">
            <div className="space-y-6 text-text-secondary">
              {/* Core Concept */}
              <div className="p-4 bg-gradient-to-r from-yellow-500/20 to-orange-500/20 border border-yellow-500/30 rounded-lg">
                <h4 className="font-bold text-yellow-500 text-lg mb-2">The Core Concept</h4>
                <p className="text-lg">
                  <strong>Every price has a "birthday" each year</strong> - a date when the Sun transits that price's zodiac degree.
                </p>
              </div>

              {/* Real Example: Gold $4,341 */}
              <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                <h4 className="font-bold text-yellow-500 mb-4">Real Example: Gold at $4,341</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <div className="p-3 bg-bg-secondary rounded">
                      <div className="text-xs text-text-muted">STEP 1: Price → Degree</div>
                      <div className="font-mono text-lg">$4,341 ÷ 36 = 120.6°</div>
                      <div className="text-sm text-text-muted">Gold uses ÷36 harmonic ($10 increments)</div>
                    </div>
                    <div className="p-3 bg-bg-secondary rounded">
                      <div className="text-xs text-text-muted">STEP 2: Degree → Zodiac</div>
                      <div className="font-mono text-lg">120.6° = 0.6° Leo</div>
                      <div className="text-sm text-text-muted">120° = start of Leo (30° × 4 signs)</div>
                    </div>
                    <div className="p-3 bg-bg-secondary rounded">
                      <div className="text-xs text-text-muted">STEP 3: Degree → Date</div>
                      <div className="font-mono text-lg">121° = <span className="text-yellow-500">July 18</span></div>
                      <div className="text-sm text-text-muted">March 20 + 121 days = July 18</div>
                    </div>
                  </div>
                  <div className="p-4 bg-yellow-500/20 rounded-lg">
                    <div className="text-center">
                      <div className="text-3xl mb-2">🥇</div>
                      <div className="text-xl font-bold text-yellow-500">July 18</div>
                      <div className="text-sm">Gold's "Birthday" for $4,341</div>
                      <div className="mt-4 text-sm text-text-secondary">
                        <p>On this date each year, if Gold is still near $4,341:</p>
                        <p className="font-semibold text-yellow-500 mt-1">Watch for a potential turn!</p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Today's Analysis */}
              <div className="p-4 bg-accent-blue/10 border border-accent-blue/30 rounded-lg">
                <h4 className="font-bold text-accent-blue mb-3">Why Today (January) is NOT a Turn Signal</h4>
                <div className="grid grid-cols-3 gap-4 text-center mb-4">
                  <div className="p-3 bg-bg-secondary rounded">
                    <div className="text-xs text-text-muted">Sun Today</div>
                    <div className="text-xl font-bold">288°</div>
                    <div className="text-sm">Capricorn</div>
                  </div>
                  <div className="p-3 bg-bg-secondary rounded">
                    <div className="text-xs text-text-muted">Gold's Degree</div>
                    <div className="text-xl font-bold">121°</div>
                    <div className="text-sm">Leo</div>
                  </div>
                  <div className="p-3 bg-accent-red/20 rounded">
                    <div className="text-xs text-text-muted">Distance</div>
                    <div className="text-xl font-bold text-accent-red">167°</div>
                    <div className="text-sm">NOT aligned!</div>
                  </div>
                </div>
                <p className="text-sm">
                  Sun at 288° is <strong>167° away</strong> from Gold's price degree (121°).
                  This means daily moves are market noise, not Gann-based planetary signals.
                  The sensitivity date is <strong>July 18</strong> (197 days away).
                </p>
              </div>

              {/* October 20-28 Complete Example */}
              <div className="p-4 bg-accent-purple/10 border border-accent-purple/30 rounded-lg">
                <h4 className="font-bold text-accent-purple mb-3">Complete Example: Gold Oct 20 High → Oct 28 Low</h4>

                {/* Timeline */}
                <div className="mb-4 p-3 bg-bg-secondary rounded-lg">
                  <div className="text-xs text-text-muted mb-2">WHAT HAPPENED:</div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="text-center">
                      <div className="text-accent-green font-bold">Oct 20</div>
                      <div>HIGH $4,341</div>
                    </div>
                    <div className="flex-1 border-t border-dashed border-text-muted mx-4 relative">
                      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-bg-secondary px-2 text-xs">8 days</div>
                    </div>
                    <div className="text-center">
                      <div className="text-accent-red font-bold">Oct 28</div>
                      <div>LOW $3,901</div>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Oct 20 Analysis */}
                  <div className="space-y-2">
                    <div className="font-semibold text-accent-green">Oct 20 HIGH - Why?</div>
                    <div className="text-sm space-y-1">
                      <div className="flex justify-between p-1 bg-bg-secondary rounded">
                        <span>Sun at 214°</span>
                        <span className="text-accent-green">Near 0° Scorpio (210°)</span>
                      </div>
                      <div className="flex justify-between p-1 bg-bg-secondary rounded">
                        <span>1 day before</span>
                        <span className="text-accent-red">Solar Eclipse (Oct 21)</span>
                      </div>
                    </div>
                  </div>

                  {/* Oct 28 Analysis */}
                  <div className="space-y-2">
                    <div className="font-semibold text-accent-red">Oct 28 LOW - Why?</div>
                    <div className="text-sm space-y-1">
                      <div className="flex justify-between p-1 bg-bg-secondary rounded">
                        <span>7 days after eclipse</span>
                        <span className="text-yellow-500">End of eclipse window</span>
                      </div>
                      <div className="flex justify-between p-1 bg-bg-secondary rounded">
                        <span>First Quarter Moon</span>
                        <span className="text-yellow-500">Lunar tension</span>
                      </div>
                      <div className="flex justify-between p-1 bg-bg-secondary rounded">
                        <span>$440 drop ÷ 55</span>
                        <span className="text-accent-green">= 8 days (Time=Price!)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* FORESIGHT Example */}
              <div className="p-4 bg-gradient-to-r from-accent-green/20 to-accent-blue/20 border border-accent-green/30 rounded-lg">
                <h4 className="font-bold text-accent-green mb-3">🔮 FORESIGHT: How to Predict This BEFORE It Happens</h4>
                <p className="text-sm mb-4">
                  All the factors above were <strong>predictable in advance</strong>. Here's what the Forecast tab would have shown on October 1, 2025:
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                  <div className="p-3 bg-bg-secondary rounded">
                    <div className="text-xs text-text-muted mb-2">UPCOMING EVENTS (as of Oct 1):</div>
                    <div className="space-y-1 text-sm">
                      <div className="flex gap-2"><span className="text-accent-red">🌑</span> Oct 21 - Solar Eclipse (CRITICAL)</div>
                      <div className="flex gap-2"><span className="text-yellow-500">○</span> Oct 23 - 0° Scorpio</div>
                      <div className="flex gap-2"><span className="text-yellow-500">✧</span> Nov 7 - Fixed Cross (225°)</div>
                    </div>
                  </div>
                  <div className="p-3 bg-accent-green/20 rounded">
                    <div className="text-xs text-text-muted mb-2">ACTION YOU WOULD TAKE:</div>
                    <div className="text-sm">
                      <div className="font-semibold mb-1">Mark Oct 14-28 as HIGH ALERT</div>
                      <ul className="text-xs space-y-1">
                        <li>• Eclipse window = ±7 days</li>
                        <li>• Expect major volatility</li>
                        <li>• Watch for reversal patterns</li>
                        <li>• Don't fight the turn!</li>
                      </ul>
                    </div>
                  </div>
                </div>

                <div className="p-2 bg-accent-green/30 rounded text-sm text-center">
                  <strong>Result:</strong> Both the Oct 20 HIGH and Oct 28 LOW happened exactly within the predicted window!
                </div>
              </div>

              {/* The 3 Questions */}
              <div className="p-4 bg-bg-secondary rounded-lg">
                <h4 className="font-bold text-text-primary mb-4">The 3 Questions Zero Aries Answers</h4>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border-color">
                        <th className="text-left py-2 px-3 text-text-muted">Question</th>
                        <th className="text-left py-2 px-3 text-text-muted">Tool</th>
                        <th className="text-left py-2 px-3 text-text-muted">Example</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr className="border-b border-border-color/50">
                        <td className="py-3 px-3">"What's today's Sun position?"</td>
                        <td className="py-3 px-3 font-semibold text-accent-blue">Date → Degree</td>
                        <td className="py-3 px-3">Jan 2 → 288° Capricorn</td>
                      </tr>
                      <tr className="border-b border-border-color/50 bg-accent-purple/5">
                        <td className="py-3 px-3">"When does Sun hit 120°?"</td>
                        <td className="py-3 px-3 font-semibold text-accent-purple">Degree → Date</td>
                        <td className="py-3 px-3">120° → July 18</td>
                      </tr>
                      <tr className="border-b border-border-color/50">
                        <td className="py-3 px-3">"What's Gold $4,341's birthday?"</td>
                        <td className="py-3 px-3 font-semibold text-yellow-500">Price → Degree</td>
                        <td className="py-3 px-3">$4,341 → 121° → July 18</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Trading Workflow */}
              <div className="p-4 bg-accent-green/10 border border-accent-green/30 rounded-lg">
                <h4 className="font-bold text-accent-green mb-4">Trading Workflow</h4>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-8 h-8 bg-accent-green text-white rounded-full flex items-center justify-center font-bold">1</span>
                    <div>
                      <div className="font-semibold text-text-primary">Enter your price in "Price → Degree"</div>
                      <div className="text-sm">Example: Gold $4,341 → 121° Leo → Anniversary: July 18</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-8 h-8 bg-accent-green text-white rounded-full flex items-center justify-center font-bold">2</span>
                    <div>
                      <div className="font-semibold text-text-primary">Mark the anniversary date on your calendar</div>
                      <div className="text-sm">July 18 (±3 days) = Gold's sensitivity window for $4,341</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-8 h-8 bg-accent-green text-white rounded-full flex items-center justify-center font-bold">3</span>
                    <div>
                      <div className="font-semibold text-text-primary">On that date, use "Confluence Checker"</div>
                      <div className="text-sm">Check if Moon phase, Mercury Rx, eclipses align for stronger signal</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-8 h-8 bg-yellow-500 text-black rounded-full flex items-center justify-center font-bold">4</span>
                    <div>
                      <div className="font-semibold text-text-primary">Watch for reversal patterns</div>
                      <div className="text-sm">If Gold is near $4,341 on July 18 with 50%+ confluence → high probability turn</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Key Insight */}
              <div className="p-4 bg-accent-red/10 border border-accent-red/30 rounded-lg">
                <h4 className="font-bold text-accent-red mb-2">⚠️ Sensitivity Windows ≠ Guaranteed Turns</h4>
                <p>
                  Anniversary dates create <strong>sensitivity windows</strong>, not guaranteed turns.
                  Actual market turns require additional factors (aspects, Moon phase, Mercury Rx).
                  Use these dates as <strong>watch dates</strong> and combine with confluence checking.
                </p>
              </div>

              {/* Quick Reference */}
              <div className="p-4 bg-bg-secondary rounded-lg">
                <h4 className="font-bold text-text-primary mb-3">Cardinal Points: The Strongest Turn Dates</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="text-center p-3 bg-gray-900 rounded">
                    <div className="text-2xl font-bold text-accent-blue">0°</div>
                    <div className="text-sm font-semibold">Mar 20</div>
                    <div className="text-xs text-text-muted">Vernal Equinox</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900 rounded">
                    <div className="text-2xl font-bold text-accent-blue">90°</div>
                    <div className="text-sm font-semibold">Jun 21</div>
                    <div className="text-xs text-text-muted">Summer Solstice</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900 rounded">
                    <div className="text-2xl font-bold text-accent-blue">180°</div>
                    <div className="text-sm font-semibold">Sep 23</div>
                    <div className="text-xs text-text-muted">Autumnal Equinox</div>
                  </div>
                  <div className="text-center p-3 bg-gray-900 rounded">
                    <div className="text-2xl font-bold text-accent-blue">270°</div>
                    <div className="text-sm font-semibold">Dec 21</div>
                    <div className="text-xs text-text-muted">Winter Solstice</div>
                  </div>
                </div>
                <p className="text-xs text-text-muted mt-3 text-center">
                  These are Gann's most powerful seasonal turn dates - always watch for reversals near these dates
                </p>
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'confluence' && (
          <Card title="🎯 Confluence Checker" subtitle="Check multiple Gann factors for signal strength">
            <div className="space-y-6">
              {/* Source Attribution */}
              <div className="p-4 bg-accent-blue/10 border border-accent-blue/30 rounded-lg">
                <h4 className="font-bold text-accent-blue mb-2">Factors from Gann/Jenkins Methodology</h4>
                <p className="text-sm text-text-secondary">
                  These confluence factors are derived from W.D. Gann's writings and Michael Jenkins' interpretations.
                  A single factor is weak; multiple factors aligning creates high-probability setups.
                </p>
              </div>

              {/* Input Section */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                  <label className="block text-xs text-text-secondary mb-1">Date to Check</label>
                  <input
                    type="date"
                    value={confluenceDate}
                    onChange={(e) => setConfluenceDate(e.target.value)}
                    className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-blue"
                  />
                </div>
                <div>
                  <label className="block text-xs text-text-secondary mb-1">Asset</label>
                  <select
                    value={confluenceAsset}
                    onChange={(e) => setConfluenceAsset(e.target.value)}
                    className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-blue"
                  >
                    {Object.entries(assetHarmonics).filter(([key]) => key !== 'AUTO').map(([key, asset]) => (
                      <option key={key} value={key}>
                        {asset.symbol} {asset.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-text-secondary mb-1">Current Price</label>
                  <input
                    type="number"
                    value={confluencePrice}
                    onChange={(e) => setConfluencePrice(e.target.value)}
                    placeholder="e.g., 4341"
                    className="w-full px-4 py-2 bg-bg-secondary border border-border-color rounded-lg text-text-primary focus:outline-none focus:border-accent-blue"
                  />
                </div>
                <div className="flex items-end">
                  <Button onClick={checkConfluence} loading={confluenceLoading} className="w-full">
                    Check Confluence
                  </Button>
                </div>
              </div>

              {/* Results */}
              {confluenceResults && (
                <>
                  {/* Overall Score */}
                  <div className={`p-6 rounded-lg border-2 ${
                    confluenceResults.rating === 'STRONG' ? 'bg-accent-green/10 border-accent-green' :
                    confluenceResults.rating === 'MODERATE' ? 'bg-yellow-500/10 border-yellow-500' :
                    'bg-accent-red/10 border-accent-red'
                  }`}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="text-sm text-text-muted">Confluence Score</div>
                        <div className={`text-4xl font-bold ${
                          confluenceResults.rating === 'STRONG' ? 'text-accent-green' :
                          confluenceResults.rating === 'MODERATE' ? 'text-yellow-500' :
                          'text-accent-red'
                        }`}>
                          {confluenceResults.percentage}%
                        </div>
                        <div className="text-sm">
                          {confluenceResults.totalScore} / {confluenceResults.maxTotalScore} points
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`text-2xl font-bold ${
                          confluenceResults.rating === 'STRONG' ? 'text-accent-green' :
                          confluenceResults.rating === 'MODERATE' ? 'text-yellow-500' :
                          'text-accent-red'
                        }`}>
                          {confluenceResults.rating}
                        </div>
                        <div className="text-sm text-text-muted">
                          {confluenceResults.rating === 'STRONG' ? 'High probability setup' :
                           confluenceResults.rating === 'MODERATE' ? 'Wait for more factors' :
                           'Low probability - avoid'}
                        </div>
                      </div>
                    </div>
                    <div className="mt-4 pt-4 border-t border-border-color">
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <span className="text-text-muted">Date:</span> {confluenceResults.date}
                        </div>
                        <div>
                          <span className="text-text-muted">Sun:</span> {confluenceResults.sunDegree}°
                        </div>
                        <div>
                          <span className="text-text-muted">Price Degree:</span> {confluenceResults.priceDegree.toFixed(1)}°
                        </div>
                        <div>
                          <span className="text-text-muted">Anniversary:</span> {confluenceResults.anniversaryDate}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Individual Factors */}
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {confluenceResults.factors.map((factor: any, idx: number) => (
                      <div key={idx} className={`p-4 rounded-lg border ${
                        factor.score === factor.maxScore ? 'bg-accent-green/10 border-accent-green/50' :
                        factor.score > 0 ? 'bg-yellow-500/10 border-yellow-500/50' :
                        'bg-bg-secondary border-border-color'
                      }`}>
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xl">{factor.icon}</span>
                            <span className="font-semibold text-sm">{factor.name}</span>
                          </div>
                          <div className={`px-2 py-0.5 rounded text-xs font-bold ${
                            factor.score === factor.maxScore ? 'bg-accent-green/20 text-accent-green' :
                            factor.score > 0 ? 'bg-yellow-500/20 text-yellow-500' :
                            'bg-bg-hover text-text-muted'
                          }`}>
                            {factor.status}
                          </div>
                        </div>
                        <div className="text-xs text-text-secondary">{factor.description}</div>
                        <div className="mt-2 flex gap-1">
                          {Array.from({ length: factor.maxScore }, (_, i) => (
                            <div key={i} className={`h-2 flex-1 rounded ${
                              i < factor.score ? 'bg-accent-green' : 'bg-bg-hover'
                            }`} />
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Factor Sources */}
                  <div className="p-4 bg-bg-secondary rounded-lg">
                    <h4 className="font-bold text-text-primary mb-3">📚 Gann/Jenkins Source References</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                      <div className="flex items-start gap-2">
                        <span>☉</span>
                        <div>
                          <span className="font-semibold">Sun-Price Alignment:</span>
                          <span className="text-text-muted"> "Prices gravitate to planetary locations" - Gann</span>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <span>🌙</span>
                        <div>
                          <span className="font-semibold">Lunar Phase:</span>
                          <span className="text-text-muted"> "Moon controls emotions of the masses" - Gann</span>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <span>📅</span>
                        <div>
                          <span className="font-semibold">Seasonal Dates:</span>
                          <span className="text-text-muted"> Gann's 15° increment turn dates (Vol I p.40-48)</span>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <span>☿</span>
                        <div>
                          <span className="font-semibold">Mercury Rx:</span>
                          <span className="text-text-muted"> "Mercury rules mind of masses" - Jenkins Vol I</span>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <span>🌑</span>
                        <div>
                          <span className="font-semibold">Eclipse Windows:</span>
                          <span className="text-text-muted"> Major energy shifts - Gann's eclipse studies</span>
                        </div>
                      </div>
                      <div className="flex items-start gap-2">
                        <span>♈</span>
                        <div>
                          <span className="font-semibold">Cardinal Ingress:</span>
                          <span className="text-text-muted"> 0°/90°/180°/270° are strongest - Gann</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Trading Guidance */}
                  <div className="p-4 bg-accent-red/10 border border-accent-red/30 rounded-lg">
                    <h4 className="font-bold text-accent-red mb-2">⚠️ Trading Guidance</h4>
                    <ul className="text-sm space-y-1 text-text-secondary">
                      <li>• <strong>70%+ (STRONG):</strong> High probability turn window - watch for reversal patterns</li>
                      <li>• <strong>40-69% (MODERATE):</strong> Some factors present - wait for more confirmation</li>
                      <li>• <strong>&lt;40% (WEAK):</strong> Low probability - daily noise likely, not a major turn</li>
                      <li>• <strong>Always use stop losses</strong> - confluence increases probability, not certainty</li>
                    </ul>
                  </div>
                </>
              )}
            </div>
          </Card>
        )}

        {activeTab === 'backtest' && (
          <Card title="Backtest: Verify Zero Aries Examples" subtitle="Cross-reference calculations against Jenkins Volume I">
            <div className="space-y-6">
              <div className="p-4 bg-accent-blue/10 border border-accent-blue/30 rounded-lg">
                <p className="text-sm">
                  This backtest verifies that our Zero Aries calculations (date to degree conversion)
                  match the cardinal points described in Jenkins Volume I.
                </p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border-color">
                      <th className="text-left py-3 px-4 text-text-muted">Test Case</th>
                      <th className="text-left py-3 px-4 text-text-muted">Date</th>
                      <th className="text-left py-3 px-4 text-text-muted">Expected°</th>
                      <th className="text-left py-3 px-4 text-text-muted">Calculated°</th>
                      <th className="text-left py-3 px-4 text-text-muted">Expected Sign</th>
                      <th className="text-left py-3 px-4 text-text-muted">Calculated Sign</th>
                      <th className="text-center py-3 px-4 text-text-muted">Result</th>
                    </tr>
                  </thead>
                  <tbody>
                    {backtestCases.map((testCase, idx) => {
                      const result = runBacktest(testCase);
                      return (
                        <tr key={idx} className="border-b border-border-color/50 hover:bg-bg-hover">
                          <td className="py-3 px-4">
                            <div className="font-medium">{testCase.name}</div>
                            <div className="text-xs text-text-muted">{testCase.bookPage}</div>
                          </td>
                          <td className="py-3 px-4 font-mono">{testCase.inputDate}</td>
                          <td className="py-3 px-4 font-mono">{testCase.expectedDegree}°</td>
                          <td className="py-3 px-4 font-mono">
                            <span className={result.degreePass ? 'text-accent-green' : 'text-accent-red'}>
                              {result.calculatedDegree}°
                            </span>
                          </td>
                          <td className="py-3 px-4">{testCase.expectedSign}</td>
                          <td className="py-3 px-4">
                            <span className={result.signPass ? 'text-accent-green' : 'text-accent-red'}>
                              {result.calculatedSign}
                            </span>
                          </td>
                          <td className="py-3 px-4 text-center">
                            <span className={`px-3 py-1 rounded-full text-xs font-bold ${
                              result.overallPass
                                ? 'bg-accent-green/20 text-accent-green'
                                : 'bg-accent-red/20 text-accent-red'
                            }`}>
                              {result.overallPass ? '✓ PASS' : '✗ FAIL'}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <div className="grid grid-cols-3 gap-4">
                <Card className="text-center bg-bg-secondary">
                  <div className="text-3xl font-bold text-accent-green">
                    {backtestCases.filter(tc => runBacktest(tc).overallPass).length}
                  </div>
                  <div className="text-xs text-text-muted">Tests Passed</div>
                </Card>
                <Card className="text-center bg-bg-secondary">
                  <div className="text-3xl font-bold text-accent-red">
                    {backtestCases.filter(tc => !runBacktest(tc).overallPass).length}
                  </div>
                  <div className="text-xs text-text-muted">Tests Failed</div>
                </Card>
                <Card className="text-center bg-bg-secondary">
                  <div className="text-3xl font-bold text-accent-blue">
                    {Math.round((backtestCases.filter(tc => runBacktest(tc).overallPass).length / backtestCases.length) * 100)}%
                  </div>
                  <div className="text-xs text-text-muted">Accuracy</div>
                </Card>
              </div>
            </div>
          </Card>
        )}

        {activeTab === 'forecast' && (
          <Card title="📅 Upcoming Turn Windows" subtitle="Predictable events for the next 90 days - FORESIGHT, not hindsight">
            <div className="space-y-6">
              {/* Key Insight */}
              <div className="p-4 bg-gradient-to-r from-accent-purple/20 to-accent-blue/20 border border-accent-purple/30 rounded-lg">
                <h4 className="font-bold text-accent-purple mb-2">Foresight, Not Hindsight</h4>
                <p className="text-sm">
                  These events are <strong>known in advance</strong>. Eclipses, cardinal ingresses, and Mercury retrograde dates
                  are predictable years ahead. Use this calendar to prepare for high-probability turn windows.
                </p>
              </div>

              {/* Events Calendar */}
              <div className="space-y-3">
                {forecastEvents.map((event, idx) => {
                  const daysAway = Math.ceil((event.date.getTime() - new Date().getTime()) / (1000 * 60 * 60 * 24));
                  const isThisWeek = daysAway <= 7;
                  const isThisMonth = daysAway <= 30;

                  return (
                    <div
                      key={idx}
                      className={`p-4 rounded-lg border ${
                        event.importance === 'critical'
                          ? 'bg-accent-red/10 border-accent-red/50'
                          : event.importance === 'high'
                          ? 'bg-yellow-500/10 border-yellow-500/50'
                          : 'bg-bg-secondary border-border-color'
                      } ${isThisWeek ? 'ring-2 ring-accent-red' : ''}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className={`text-2xl ${
                            event.type === 'eclipse' ? '' :
                            event.type === 'cardinal' ? '' :
                            event.type === 'fixed-cross' ? '' :
                            event.type.includes('mercury') ? '' : ''
                          }`}>
                            {event.type === 'eclipse' ? '🌑' :
                             event.type === 'cardinal' ? '♈' :
                             event.type === 'fixed-cross' ? '✧' :
                             event.type.includes('mercury') ? '☿' : '○'}
                          </div>
                          <div>
                            <div className="font-semibold text-text-primary">{event.name}</div>
                            <div className="text-sm text-text-muted">
                              {event.date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
                              {event.degree > 0 && <span className="ml-2 text-accent-purple">({event.degree}°)</span>}
                            </div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-lg font-bold ${
                            isThisWeek ? 'text-accent-red' : isThisMonth ? 'text-yellow-500' : 'text-text-muted'
                          }`}>
                            {daysAway === 0 ? 'TODAY' : daysAway === 1 ? 'Tomorrow' : `${daysAway} days`}
                          </div>
                          <div className={`text-xs px-2 py-0.5 rounded-full inline-block ${
                            event.importance === 'critical' ? 'bg-accent-red/20 text-accent-red' :
                            event.importance === 'high' ? 'bg-yellow-500/20 text-yellow-500' :
                            'bg-bg-hover text-text-muted'
                          }`}>
                            {event.importance.toUpperCase()}
                          </div>
                        </div>
                      </div>
                      {event.type === 'eclipse' && (
                        <div className="mt-2 text-xs text-text-muted bg-bg-secondary p-2 rounded">
                          ⚠️ Eclipse window: {new Date(event.date.getTime() - 7*24*60*60*1000).toLocaleDateString('en-US', {month: 'short', day: 'numeric'})} - {new Date(event.date.getTime() + 7*24*60*60*1000).toLocaleDateString('en-US', {month: 'short', day: 'numeric'})} (±7 days)
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Legend */}
              <div className="p-4 bg-bg-secondary rounded-lg">
                <h4 className="font-bold text-text-primary mb-3">Event Types</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="text-xl">🌑</span>
                    <div>
                      <div className="font-semibold">Eclipse</div>
                      <div className="text-xs text-text-muted">±7 day window</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl">♈</span>
                    <div>
                      <div className="font-semibold">Cardinal</div>
                      <div className="text-xs text-text-muted">Equinox/Solstice</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl">✧</span>
                    <div>
                      <div className="font-semibold">Fixed Cross</div>
                      <div className="text-xs text-text-muted">15° Fixed signs</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xl">☿</span>
                    <div>
                      <div className="font-semibold">Mercury Rx</div>
                      <div className="text-xs text-text-muted">Retrograde period</div>
                    </div>
                  </div>
                </div>
              </div>

              {/* October 2025 Example */}
              <div className="p-4 bg-accent-green/10 border border-accent-green/30 rounded-lg">
                <h4 className="font-bold text-accent-green mb-3">Example: How This Would Have Predicted Oct 2025</h4>
                <p className="text-sm mb-3">
                  If you had looked at this forecast on October 1, 2025, you would have seen:
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 p-2 bg-bg-secondary rounded">
                    <span className="text-accent-red font-bold">Oct 21</span>
                    <span>🌑 Solar Eclipse</span>
                    <span className="text-accent-red text-xs">(CRITICAL)</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-bg-secondary rounded">
                    <span className="text-yellow-500 font-bold">Oct 23</span>
                    <span>○ 0° Scorpio (Sign Ingress)</span>
                  </div>
                  <div className="flex items-center gap-2 p-2 bg-bg-secondary rounded">
                    <span className="text-yellow-500 font-bold">Nov 7</span>
                    <span>✧ Fixed Cross (15° Scorpio)</span>
                  </div>
                </div>
                <div className="mt-3 p-2 bg-accent-green/20 rounded text-sm">
                  <strong>Action:</strong> Mark Oct 14-28 as a HIGH VOLATILITY window.
                  Watch for major turns. The Oct 20 high and Oct 28 low both happened within this predicted window!
                </div>
              </div>

              {/* How to Use */}
              <div className="p-4 bg-accent-blue/10 border border-accent-blue/30 rounded-lg">
                <h4 className="font-bold text-accent-blue mb-2">How to Use This Forecast</h4>
                <ul className="text-sm space-y-2">
                  <li><strong>1. Mark CRITICAL events</strong> - Eclipses and Cardinal dates are highest priority</li>
                  <li><strong>2. Note the windows</strong> - Eclipses affect ±7 days, other events ±3 days</li>
                  <li><strong>3. Combine with price</strong> - Check if your asset's anniversary date falls in these windows</li>
                  <li><strong>4. Use Confluence Checker</strong> - On these dates, check for additional factors</li>
                  <li><strong>5. Watch for setups</strong> - Look for reversal patterns (pin bars, engulfing) on these dates</li>
                </ul>
              </div>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
