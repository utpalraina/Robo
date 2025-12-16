"""
5-Minute Candle Collector Service

Collects OHLCV data every 5 minutes, calculates all indicators,
generates predictions, and stores everything in the database
with New York timezone timestamps.
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import pytz
from loguru import logger

from data.storage import DataStorage
from data.fetcher import DataFetcher
from features.indicators import FeatureEngineer


class CandleCollector:
    """
    Service that collects 5-minute candle data with indicators and predictions.

    Stores OHLCV, all technical indicators, signal explanation, and prediction
    with both UTC and New York timestamps.
    """

    NY_TZ = pytz.timezone('America/New_York')
    UTC_TZ = pytz.UTC

    def __init__(
        self,
        data_fetcher: DataFetcher,
        feature_engineer: FeatureEngineer,
        storage: DataStorage,
        strategy=None,
        symbol: str = "BTC/USD"
    ):
        """
        Initialize the candle collector.

        Args:
            data_fetcher: DataFetcher instance for getting OHLCV data
            feature_engineer: FeatureEngineer for calculating indicators
            storage: DataStorage for persisting snapshots
            strategy: Optional ML strategy for generating predictions
            symbol: Trading pair to collect data for
        """
        self.data_fetcher = data_fetcher
        self.feature_engineer = feature_engineer
        self.storage = storage
        self.strategy = strategy
        self.symbol = symbol
        self.running = False
        self.last_candle_time: Optional[datetime] = None

    def _utc_to_ny(self, utc_dt: datetime) -> str:
        """Convert UTC datetime to New York time string."""
        if utc_dt.tzinfo is None:
            utc_dt = self.UTC_TZ.localize(utc_dt)
        ny_dt = utc_dt.astimezone(self.NY_TZ)
        return ny_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

    def _get_current_5min_boundary(self) -> datetime:
        """Get the current 5-minute boundary timestamp."""
        now = datetime.utcnow()
        # Round down to nearest 5 minutes
        minute = (now.minute // 5) * 5
        return now.replace(minute=minute, second=0, microsecond=0)

    def _analyze_indicators(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze indicators and generate signal explanation.

        Returns dict with:
            - prediction: BUY/SELL/HOLD
            - bullish_count: number of bullish signals
            - bearish_count: number of bearish signals
            - neutral_count: number of neutral signals
            - reasons: list of explanation strings
        """
        reasons = []
        bullish = 0
        bearish = 0
        neutral = 0

        # 1. RSI(14) analysis
        rsi = indicators.get('rsi_14')
        if rsi is not None:
            if rsi < 30:
                reasons.append(f"RSI(14) at {rsi:.1f} - oversold, potential bounce")
                bullish += 1
            elif rsi > 70:
                reasons.append(f"RSI(14) at {rsi:.1f} - overbought, potential pullback")
                bearish += 1
            else:
                reasons.append(f"RSI(14) at {rsi:.1f} - neutral zone")
                neutral += 1

        # 2. RSI(7) analysis
        rsi7 = indicators.get('rsi_7')
        if rsi7 is not None:
            if rsi7 < 30:
                reasons.append(f"RSI(7) at {rsi7:.1f} - short-term oversold")
                bullish += 1
            elif rsi7 > 70:
                reasons.append(f"RSI(7) at {rsi7:.1f} - short-term overbought")
                bearish += 1
            else:
                neutral += 1

        # 3. Stochastic analysis
        stoch_k = indicators.get('stoch_k')
        stoch_d = indicators.get('stoch_d')
        if stoch_k is not None:
            if stoch_k < 20:
                reasons.append(f"Stochastic K at {stoch_k:.0f} - oversold momentum")
                bullish += 1
            elif stoch_k > 80:
                reasons.append(f"Stochastic K at {stoch_k:.0f} - overbought momentum")
                bearish += 1
            else:
                neutral += 1

            # K/D crossover
            if stoch_d is not None:
                if stoch_k > stoch_d and stoch_k < 50:
                    reasons.append("Stochastic K crossed above D - bullish signal")
                    bullish += 1
                elif stoch_k < stoch_d and stoch_k > 50:
                    reasons.append("Stochastic K crossed below D - bearish signal")
                    bearish += 1

        # 4. CCI analysis
        cci = indicators.get('cci')
        if cci is not None:
            if cci > 100:
                reasons.append(f"CCI at {cci:.0f} - strong upward momentum")
                bullish += 1
            elif cci < -100:
                reasons.append(f"CCI at {cci:.0f} - strong downward momentum")
                bearish += 1
            else:
                neutral += 1

        # 5. ROC analysis
        roc = indicators.get('roc_10')
        if roc is not None:
            if roc > 2:
                reasons.append(f"ROC at {roc:.2f}% - strong positive momentum")
                bullish += 1
            elif roc < -2:
                reasons.append(f"ROC at {roc:.2f}% - strong negative momentum")
                bearish += 1
            else:
                neutral += 1

        # 6. MACD analysis
        macd_hist = indicators.get('macd_hist')
        if macd_hist is not None:
            if macd_hist > 0:
                reasons.append(f"MACD histogram positive ({macd_hist:.2f}) - bullish momentum")
                bullish += 1
            elif macd_hist < 0:
                reasons.append(f"MACD histogram negative ({macd_hist:.2f}) - bearish momentum")
                bearish += 1
            else:
                neutral += 1

        # 7. ADX analysis
        adx = indicators.get('adx')
        if adx is not None:
            if adx > 25:
                reasons.append(f"ADX at {adx:.1f} - strong trend present")
            else:
                reasons.append(f"ADX at {adx:.1f} - weak/ranging market")
            neutral += 1

        # 8. DI+/DI- analysis
        di_plus = indicators.get('di_plus')
        di_minus = indicators.get('di_minus')
        if di_plus is not None and di_minus is not None:
            if di_plus > di_minus:
                reasons.append(f"DI+ ({di_plus:.0f}) > DI- ({di_minus:.0f}) - bullish trend")
                bullish += 1
            else:
                reasons.append(f"DI- ({di_minus:.0f}) > DI+ ({di_plus:.0f}) - bearish trend")
                bearish += 1

        # 9. EMA 9/21 crossover
        ema9 = indicators.get('ema_9')
        ema21 = indicators.get('ema_21')
        if ema9 is not None and ema21 is not None:
            if ema9 > ema21:
                reasons.append("EMA 9 above EMA 21 - short-term bullish trend")
                bullish += 1
            else:
                reasons.append("EMA 9 below EMA 21 - short-term bearish trend")
                bearish += 1

        # 10. SMA 20/50 crossover
        sma20 = indicators.get('sma_20')
        sma50 = indicators.get('sma_50')
        if sma20 is not None and sma50 is not None:
            if sma20 > sma50:
                reasons.append("SMA 20 above SMA 50 - medium-term bullish")
                bullish += 1
            else:
                reasons.append("SMA 20 below SMA 50 - medium-term bearish")
                bearish += 1

        # 11. ATR volatility
        atr_pct = indicators.get('atr_pct')
        if atr_pct is not None:
            if atr_pct > 0.03:
                reasons.append(f"ATR at {atr_pct*100:.2f}% - high volatility")
            elif atr_pct < 0.01:
                reasons.append(f"ATR at {atr_pct*100:.2f}% - low volatility, potential breakout")
            neutral += 1

        # 12. Bollinger Band position
        bb_pct = indicators.get('bb_pct')
        if bb_pct is not None:
            if bb_pct < 0.2:
                reasons.append(f"Price near lower BB ({bb_pct*100:.0f}%) - potential bounce")
                bullish += 1
            elif bb_pct > 0.8:
                reasons.append(f"Price near upper BB ({bb_pct*100:.0f}%) - potential reversal")
                bearish += 1
            else:
                neutral += 1

        # 13. Bollinger Band Width
        bb_width = indicators.get('bb_width')
        if bb_width is not None:
            if bb_width < 0.02:
                reasons.append(f"BB Width {bb_width*100:.2f}% - squeeze, breakout expected")
                neutral += 1
            elif bb_width > 0.06:
                reasons.append(f"BB Width {bb_width*100:.2f}% - high volatility")
                neutral += 1

        # 14. Volume analysis
        vol_ratio = indicators.get('volume_ratio')
        if vol_ratio is not None:
            if vol_ratio > 1.5:
                reasons.append(f"High volume ({vol_ratio:.2f}x avg) - confirms price action")
                bullish += 1
            elif vol_ratio < 0.5:
                reasons.append(f"Low volume ({vol_ratio:.2f}x avg) - weak conviction")
                bearish += 1
            else:
                neutral += 1

        # 15. Price vs VWAP
        vwap = indicators.get('vwap')
        close = indicators.get('close')
        if vwap is not None and close is not None:
            if close > vwap:
                reasons.append("Price above VWAP - bullish intraday bias")
                bullish += 1
            else:
                reasons.append("Price below VWAP - bearish intraday bias")
                bearish += 1

        # Determine prediction
        if bullish > bearish + 3:
            prediction = "BUY"
        elif bearish > bullish + 3:
            prediction = "SELL"
        else:
            prediction = "HOLD"

        return {
            'prediction': prediction,
            'bullish_count': bullish,
            'bearish_count': bearish,
            'neutral_count': neutral,
            'reasons': reasons
        }

    def _validate_previous_predictions(self, current_close: float):
        """
        Validate any unvalidated predictions using the current close price.

        Args:
            current_close: Current candle's close price
        """
        try:
            unvalidated = self.storage.get_unvalidated_predictions(self.symbol)

            if not unvalidated:
                return

            # Validate all except the most recent (which is the current candle)
            # We skip the last one since we're processing it now
            for snapshot in unvalidated[:-1]:
                self.storage.validate_prediction(
                    snapshot_id=snapshot['id'],
                    next_close=current_close,
                    flat_threshold=0.1  # 0.1% threshold for FLAT
                )
                logger.debug(f"Validated prediction {snapshot['id']}")

            if len(unvalidated) > 1:
                logger.info(f"Validated {len(unvalidated) - 1} previous predictions")

        except Exception as e:
            logger.error(f"Error validating predictions: {e}")

    def collect_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Collect a single 5-minute candle snapshot with all indicators.

        Returns:
            Dictionary with all snapshot data or None on error
        """
        try:
            # Fetch 5-minute OHLCV data
            df = self.data_fetcher.fetch_ohlcv(self.symbol, "5m", limit=200)

            if df.empty:
                logger.warning(f"No data returned for {self.symbol}")
                return None

            # Calculate indicators
            df_features = self.feature_engineer.generate_features(df)
            latest = df_features.iloc[-1]
            candle_time = df_features.index[-1]

            # Check if this is a new candle
            if self.last_candle_time is not None and candle_time <= self.last_candle_time:
                logger.debug(f"Candle {candle_time} already processed")
                return None

            self.last_candle_time = candle_time

            # Validate previous predictions with current close price
            current_close = float(latest['close'])
            self._validate_previous_predictions(current_close)

            # Convert timestamp
            timestamp_utc = candle_time.to_pydatetime()
            timestamp_ny = self._utc_to_ny(timestamp_utc)

            # Extract OHLCV
            ohlcv = {
                'open': float(latest['open']),
                'high': float(latest['high']),
                'low': float(latest['low']),
                'close': float(latest['close']),
                'volume': float(latest['volume'])
            }

            # Extract indicators
            indicators = {
                'rsi_14': latest.get('rsi_14'),
                'rsi_7': latest.get('rsi_7'),
                'stoch_k': latest.get('stoch_k'),
                'stoch_d': latest.get('stoch_d'),
                'cci': latest.get('cci'),
                'roc_10': latest.get('roc_10'),
                'momentum_10': latest.get('momentum_10'),
                'macd': latest.get('macd'),
                'macd_signal': latest.get('macd_signal'),
                'macd_hist': latest.get('macd_hist'),
                'adx': latest.get('adx'),
                'di_plus': latest.get('di_plus'),
                'di_minus': latest.get('di_minus'),
                'ema_9': latest.get('ema_9'),
                'ema_21': latest.get('ema_21'),
                'ema_50': latest.get('ema_50'),
                'sma_20': latest.get('sma_20'),
                'sma_50': latest.get('sma_50'),
                'atr_14': latest.get('atr_14'),
                'atr_pct': latest.get('atr_pct'),
                'bb_upper': latest.get('bb_upper'),
                'bb_middle': latest.get('bb_middle'),
                'bb_lower': latest.get('bb_lower'),
                'bb_width': latest.get('bb_width'),
                'bb_pct': latest.get('bb_pct'),
                'volume_ratio': latest.get('volume_ratio'),
                'obv': latest.get('obv'),
                'vwap': latest.get('vwap'),
                'close': float(latest['close'])  # Include for VWAP comparison
            }

            # Convert NaN to None
            indicators = {k: (None if v != v else v) for k, v in indicators.items()}

            # Analyze indicators and generate prediction
            analysis = self._analyze_indicators(indicators)

            # Get ML model prediction if available
            confidence = 50.0  # Default confidence
            if self.strategy:
                try:
                    signal, conf = self.strategy.generate_signal(df)
                    confidence = conf * 100
                    # Use ML prediction if high confidence
                    if conf > 0.7:
                        analysis['prediction'] = signal.name
                except Exception as e:
                    logger.debug(f"ML prediction error: {e}")

            # Create explanation JSON
            explanation = json.dumps({
                'prediction': analysis['prediction'],
                'summary': f"{analysis['bullish_count']} bullish, {analysis['bearish_count']} bearish, {analysis['neutral_count']} neutral signals",
                'reasons': analysis['reasons']
            })

            # Save to database
            self.storage.save_candle_snapshot(
                symbol=self.symbol,
                timestamp_utc=timestamp_utc,
                timestamp_ny=timestamp_ny,
                ohlcv=ohlcv,
                indicators=indicators,
                prediction=analysis['prediction'],
                confidence=confidence,
                signal_counts={
                    'bullish': analysis['bullish_count'],
                    'bearish': analysis['bearish_count'],
                    'neutral': analysis['neutral_count']
                },
                explanation=explanation
            )

            logger.info(f"Saved 5m candle snapshot: {self.symbol} @ {timestamp_ny} - {analysis['prediction']}")

            return {
                'symbol': self.symbol,
                'timestamp_utc': timestamp_utc.isoformat(),
                'timestamp_ny': timestamp_ny,
                'ohlcv': ohlcv,
                'prediction': analysis['prediction'],
                'confidence': confidence
            }

        except Exception as e:
            logger.error(f"Error collecting candle snapshot: {e}")
            return None

    async def run(self, interval_seconds: int = 300):
        """
        Run the collector continuously.

        Args:
            interval_seconds: Collection interval (default 5 minutes)
        """
        self.running = True
        logger.info(f"Starting candle collector for {self.symbol} every {interval_seconds}s")

        while self.running:
            try:
                # Collect snapshot
                self.collect_snapshot()

                # Wait for next interval
                await asyncio.sleep(interval_seconds)

            except asyncio.CancelledError:
                logger.info("Candle collector cancelled")
                break
            except Exception as e:
                logger.error(f"Collector error: {e}")
                await asyncio.sleep(60)  # Wait before retry

        self.running = False
        logger.info("Candle collector stopped")

    def stop(self):
        """Stop the collector."""
        self.running = False


# Helper function to create and start collector
async def start_candle_collector(
    data_fetcher: DataFetcher,
    feature_engineer: FeatureEngineer,
    storage: DataStorage,
    strategy=None,
    symbol: str = "BTC/USD"
) -> CandleCollector:
    """
    Create and start a candle collector.

    Args:
        data_fetcher: DataFetcher instance
        feature_engineer: FeatureEngineer instance
        storage: DataStorage instance
        strategy: Optional ML strategy
        symbol: Trading pair

    Returns:
        CandleCollector instance
    """
    collector = CandleCollector(
        data_fetcher=data_fetcher,
        feature_engineer=feature_engineer,
        storage=storage,
        strategy=strategy,
        symbol=symbol
    )

    # Start collector in background
    asyncio.create_task(collector.run())

    return collector
