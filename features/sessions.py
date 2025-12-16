"""
Trading Session Time Filter Module.

This module provides utilities for identifying and filtering trades
based on trading sessions (NY, London, Asia) and specific time windows
like the ICT Silver Bullet setups.

Key Sessions (All times in EST/New York):
- Asia Session: 7:00 PM - 4:00 AM
- London Session: 3:00 AM - 12:00 PM
- NY AM Session (Killzone): 8:30 AM - 12:00 PM
- NY PM Session: 1:30 PM - 4:00 PM
- Silver Bullet AM: 10:00 AM - 11:00 AM
- Silver Bullet PM: 2:00 PM - 3:00 PM
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Optional, Tuple, List, Dict
from enum import Enum
from zoneinfo import ZoneInfo

# Try to import pytz for timezone handling, fall back to zoneinfo
try:
    import pytz
    NY_TZ = pytz.timezone('America/New_York')
    UTC_TZ = pytz.UTC
    USE_PYTZ = True
except ImportError:
    NY_TZ = ZoneInfo('America/New_York')
    UTC_TZ = ZoneInfo('UTC')
    USE_PYTZ = False


class TradingSession(Enum):
    """Trading session identifiers."""
    ASIA = "asia"
    LONDON = "london"
    LONDON_NY_OVERLAP = "london_ny_overlap"
    NY_OPEN = "ny_open"
    NY_AM_KILLZONE = "ny_am_killzone"
    NY_LUNCH = "ny_lunch"
    NY_PM = "ny_pm"
    NY_CLOSE = "ny_close"
    SILVER_BULLET_AM = "silver_bullet_am"
    SILVER_BULLET_PM = "silver_bullet_pm"
    OFF_HOURS = "off_hours"


class SessionConfig:
    """
    Session time configurations.

    All times are in EST (Eastern Standard Time) / New York local time.
    """

    # Main sessions
    ASIA_START = time(19, 0)  # 7:00 PM
    ASIA_END = time(4, 0)  # 4:00 AM next day

    LONDON_START = time(3, 0)  # 3:00 AM
    LONDON_END = time(12, 0)  # 12:00 PM

    NY_OPEN_START = time(9, 30)  # 9:30 AM (market open)
    NY_CLOSE_END = time(16, 0)  # 4:00 PM (market close)

    # ICT Specific Windows
    NY_AM_KILLZONE_START = time(8, 30)  # 8:30 AM
    NY_AM_KILLZONE_END = time(11, 0)  # 11:00 AM

    NY_LUNCH_START = time(12, 0)  # 12:00 PM
    NY_LUNCH_END = time(13, 30)  # 1:30 PM

    NY_PM_START = time(13, 30)  # 1:30 PM
    NY_PM_END = time(16, 0)  # 4:00 PM

    # Silver Bullet Windows (High probability setups)
    SILVER_BULLET_AM_START = time(10, 0)  # 10:00 AM
    SILVER_BULLET_AM_END = time(11, 0)  # 11:00 AM

    SILVER_BULLET_PM_START = time(14, 0)  # 2:00 PM
    SILVER_BULLET_PM_END = time(15, 0)  # 3:00 PM

    # London-NY Overlap (High volatility)
    OVERLAP_START = time(8, 0)  # 8:00 AM
    OVERLAP_END = time(12, 0)  # 12:00 PM


class SessionFilter:
    """
    Filter and identify trading sessions.

    This class provides methods to:
    - Identify the current trading session
    - Check if current time is in optimal trading windows
    - Filter DataFrame rows by session
    - Get session-specific statistics
    """

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize SessionFilter.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

        # Preferred sessions for trading (default: NY AM Killzone and Silver Bullets)
        self.preferred_sessions = self.config.get('preferred_sessions', [
            TradingSession.NY_AM_KILLZONE,
            TradingSession.SILVER_BULLET_AM,
            TradingSession.SILVER_BULLET_PM,
            TradingSession.LONDON_NY_OVERLAP
        ])

        # Sessions to avoid
        self.avoid_sessions = self.config.get('avoid_sessions', [
            TradingSession.NY_LUNCH,
            TradingSession.OFF_HOURS
        ])

    def to_ny_time(self, dt: datetime) -> datetime:
        """
        Convert datetime to New York time.

        Args:
            dt: Datetime object (can be naive or aware)

        Returns:
            Datetime in New York timezone
        """
        if dt.tzinfo is None:
            # Assume UTC if naive
            if USE_PYTZ:
                dt = UTC_TZ.localize(dt)
            else:
                dt = dt.replace(tzinfo=UTC_TZ)

        if USE_PYTZ:
            return dt.astimezone(NY_TZ)
        else:
            return dt.astimezone(NY_TZ)

    def get_session(self, timestamp: Optional[datetime] = None) -> TradingSession:
        """
        Identify the trading session for a given timestamp.

        Args:
            timestamp: Datetime (defaults to current time)

        Returns:
            TradingSession enum value
        """
        if timestamp is None:
            timestamp = datetime.now(UTC_TZ if USE_PYTZ else ZoneInfo('UTC'))

        ny_time = self.to_ny_time(timestamp)
        current_time = ny_time.time()

        # Check specific windows first (most specific to least specific)

        # Silver Bullet AM (10:00 - 11:00 AM)
        if SessionConfig.SILVER_BULLET_AM_START <= current_time < SessionConfig.SILVER_BULLET_AM_END:
            return TradingSession.SILVER_BULLET_AM

        # Silver Bullet PM (2:00 - 3:00 PM)
        if SessionConfig.SILVER_BULLET_PM_START <= current_time < SessionConfig.SILVER_BULLET_PM_END:
            return TradingSession.SILVER_BULLET_PM

        # NY AM Killzone (8:30 - 11:00 AM)
        if SessionConfig.NY_AM_KILLZONE_START <= current_time < SessionConfig.NY_AM_KILLZONE_END:
            return TradingSession.NY_AM_KILLZONE

        # NY Lunch (12:00 - 1:30 PM) - Low volatility, avoid
        if SessionConfig.NY_LUNCH_START <= current_time < SessionConfig.NY_LUNCH_END:
            return TradingSession.NY_LUNCH

        # NY PM (1:30 - 4:00 PM)
        if SessionConfig.NY_PM_START <= current_time < SessionConfig.NY_PM_END:
            return TradingSession.NY_PM

        # London-NY Overlap (8:00 AM - 12:00 PM)
        if SessionConfig.OVERLAP_START <= current_time < SessionConfig.OVERLAP_END:
            return TradingSession.LONDON_NY_OVERLAP

        # London Session (3:00 AM - 12:00 PM)
        if SessionConfig.LONDON_START <= current_time < SessionConfig.LONDON_END:
            return TradingSession.LONDON

        # Asia Session (7:00 PM - 4:00 AM) - wraps around midnight
        if current_time >= SessionConfig.ASIA_START or current_time < SessionConfig.ASIA_END:
            return TradingSession.ASIA

        # NY Close (4:00 PM - 5:00 PM)
        if time(16, 0) <= current_time < time(17, 0):
            return TradingSession.NY_CLOSE

        return TradingSession.OFF_HOURS

    def is_optimal_time(self, timestamp: Optional[datetime] = None) -> Tuple[bool, TradingSession, str]:
        """
        Check if current time is optimal for trading.

        Args:
            timestamp: Datetime (defaults to current time)

        Returns:
            Tuple of (is_optimal, session, reason)
        """
        session = self.get_session(timestamp)

        if session in self.preferred_sessions:
            return True, session, f"In {session.value} - optimal trading window"

        if session in self.avoid_sessions:
            return False, session, f"In {session.value} - avoid trading"

        return False, session, f"In {session.value} - not preferred but tradeable"

    def is_silver_bullet_window(self, timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if current time is in a Silver Bullet window.

        Silver Bullet is a high-probability ICT setup window.

        Args:
            timestamp: Datetime

        Returns:
            Tuple of (is_silver_bullet, window_name)
        """
        session = self.get_session(timestamp)

        if session == TradingSession.SILVER_BULLET_AM:
            return True, "AM Silver Bullet (10:00-11:00 AM)"
        elif session == TradingSession.SILVER_BULLET_PM:
            return True, "PM Silver Bullet (2:00-3:00 PM)"

        return False, "Not in Silver Bullet window"

    def is_killzone(self, timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if current time is in a Killzone (high probability window).

        Args:
            timestamp: Datetime

        Returns:
            Tuple of (is_killzone, description)
        """
        session = self.get_session(timestamp)

        killzones = {
            TradingSession.NY_AM_KILLZONE: "NY AM Killzone (8:30-11:00 AM)",
            TradingSession.SILVER_BULLET_AM: "Silver Bullet AM (10:00-11:00 AM)",
            TradingSession.SILVER_BULLET_PM: "Silver Bullet PM (2:00-3:00 PM)",
            TradingSession.LONDON_NY_OVERLAP: "London-NY Overlap (8:00 AM-12:00 PM)"
        }

        if session in killzones:
            return True, killzones[session]

        return False, "Not in a Killzone"

    def get_next_optimal_session(self, timestamp: Optional[datetime] = None) -> Dict:
        """
        Get information about the next optimal trading session.

        Args:
            timestamp: Current datetime

        Returns:
            Dictionary with next session info
        """
        if timestamp is None:
            timestamp = datetime.now(UTC_TZ if USE_PYTZ else ZoneInfo('UTC'))

        ny_time = self.to_ny_time(timestamp)
        current_time = ny_time.time()

        # Define optimal session start times in order
        optimal_sessions = [
            (SessionConfig.NY_AM_KILLZONE_START, TradingSession.NY_AM_KILLZONE, "NY AM Killzone"),
            (SessionConfig.SILVER_BULLET_AM_START, TradingSession.SILVER_BULLET_AM, "Silver Bullet AM"),
            (SessionConfig.SILVER_BULLET_PM_START, TradingSession.SILVER_BULLET_PM, "Silver Bullet PM"),
        ]

        for start_time, session, name in optimal_sessions:
            if current_time < start_time:
                # Calculate time until this session
                today = ny_time.date()
                session_start = datetime.combine(today, start_time)
                if USE_PYTZ:
                    session_start = NY_TZ.localize(session_start)
                else:
                    session_start = session_start.replace(tzinfo=NY_TZ)

                time_until = session_start - ny_time

                return {
                    'session': session,
                    'name': name,
                    'starts_at': session_start.isoformat(),
                    'time_until': str(time_until),
                    'minutes_until': int(time_until.total_seconds() / 60)
                }

        # All sessions passed today, next is tomorrow's NY AM Killzone
        tomorrow = ny_time.date() + timedelta(days=1)
        session_start = datetime.combine(tomorrow, SessionConfig.NY_AM_KILLZONE_START)
        if USE_PYTZ:
            session_start = NY_TZ.localize(session_start)
        else:
            session_start = session_start.replace(tzinfo=NY_TZ)

        time_until = session_start - ny_time

        return {
            'session': TradingSession.NY_AM_KILLZONE,
            'name': "NY AM Killzone (Tomorrow)",
            'starts_at': session_start.isoformat(),
            'time_until': str(time_until),
            'minutes_until': int(time_until.total_seconds() / 60)
        }

    def filter_df_by_session(
        self,
        df: pd.DataFrame,
        sessions: List[TradingSession],
        timestamp_col: str = None
    ) -> pd.DataFrame:
        """
        Filter DataFrame to only include rows from specified sessions.

        Args:
            df: DataFrame with datetime index or timestamp column
            sessions: List of sessions to include
            timestamp_col: Column name if timestamp is not index

        Returns:
            Filtered DataFrame
        """
        if df.empty:
            return df

        # Get timestamps
        if timestamp_col:
            timestamps = pd.to_datetime(df[timestamp_col])
        else:
            timestamps = pd.to_datetime(df.index)

        # Filter rows
        mask = timestamps.apply(lambda ts: self.get_session(ts) in sessions)

        return df[mask]

    def add_session_column(
        self,
        df: pd.DataFrame,
        timestamp_col: str = None,
        session_col: str = 'session'
    ) -> pd.DataFrame:
        """
        Add a session column to DataFrame.

        Args:
            df: DataFrame with datetime index or timestamp column
            timestamp_col: Column name if timestamp is not index
            session_col: Name for the new session column

        Returns:
            DataFrame with session column added
        """
        if df.empty:
            return df

        df = df.copy()

        if timestamp_col:
            timestamps = pd.to_datetime(df[timestamp_col])
        else:
            timestamps = pd.to_datetime(df.index)

        df[session_col] = timestamps.apply(lambda ts: self.get_session(ts).value)

        return df

    def get_session_stats(
        self,
        df: pd.DataFrame,
        price_col: str = 'close',
        timestamp_col: str = None
    ) -> Dict:
        """
        Calculate statistics by session.

        Args:
            df: DataFrame with OHLCV data
            price_col: Column for price data
            timestamp_col: Timestamp column name

        Returns:
            Dictionary with session statistics
        """
        df_with_session = self.add_session_column(df, timestamp_col)

        stats = {}
        for session in TradingSession:
            session_df = df_with_session[df_with_session['session'] == session.value]

            if len(session_df) > 0:
                returns = session_df[price_col].pct_change().dropna()

                stats[session.value] = {
                    'count': len(session_df),
                    'avg_return': float(returns.mean()) if len(returns) > 0 else 0,
                    'volatility': float(returns.std()) if len(returns) > 0 else 0,
                    'max_return': float(returns.max()) if len(returns) > 0 else 0,
                    'min_return': float(returns.min()) if len(returns) > 0 else 0,
                    'positive_pct': float((returns > 0).sum() / len(returns) * 100) if len(returns) > 0 else 0
                }
            else:
                stats[session.value] = {
                    'count': 0,
                    'avg_return': 0,
                    'volatility': 0,
                    'max_return': 0,
                    'min_return': 0,
                    'positive_pct': 0
                }

        return stats


def get_ny_time(timestamp: Optional[datetime] = None) -> datetime:
    """
    Get current time in New York timezone.

    Args:
        timestamp: Optional timestamp to convert

    Returns:
        Datetime in NY timezone
    """
    if timestamp is None:
        if USE_PYTZ:
            return datetime.now(NY_TZ)
        else:
            return datetime.now(NY_TZ)

    if timestamp.tzinfo is None:
        if USE_PYTZ:
            timestamp = UTC_TZ.localize(timestamp)
        else:
            timestamp = timestamp.replace(tzinfo=UTC_TZ)

    if USE_PYTZ:
        return timestamp.astimezone(NY_TZ)
    else:
        return timestamp.astimezone(NY_TZ)


def format_session_time(session: TradingSession) -> str:
    """
    Get formatted time range for a session.

    Args:
        session: TradingSession enum

    Returns:
        Formatted string like "8:30 AM - 11:00 AM EST"
    """
    session_times = {
        TradingSession.ASIA: "7:00 PM - 4:00 AM",
        TradingSession.LONDON: "3:00 AM - 12:00 PM",
        TradingSession.LONDON_NY_OVERLAP: "8:00 AM - 12:00 PM",
        TradingSession.NY_AM_KILLZONE: "8:30 AM - 11:00 AM",
        TradingSession.NY_LUNCH: "12:00 PM - 1:30 PM",
        TradingSession.NY_PM: "1:30 PM - 4:00 PM",
        TradingSession.NY_CLOSE: "4:00 PM - 5:00 PM",
        TradingSession.SILVER_BULLET_AM: "10:00 AM - 11:00 AM",
        TradingSession.SILVER_BULLET_PM: "2:00 PM - 3:00 PM",
        TradingSession.OFF_HOURS: "Off Hours",
    }

    return f"{session_times.get(session, 'Unknown')} EST"


# Convenience functions
def is_ny_killzone(timestamp: Optional[datetime] = None) -> bool:
    """Check if timestamp is in NY AM Killzone."""
    sf = SessionFilter()
    session = sf.get_session(timestamp)
    return session == TradingSession.NY_AM_KILLZONE


def is_silver_bullet(timestamp: Optional[datetime] = None) -> bool:
    """Check if timestamp is in Silver Bullet window."""
    sf = SessionFilter()
    is_sb, _ = sf.is_silver_bullet_window(timestamp)
    return is_sb


def is_london_session(timestamp: Optional[datetime] = None) -> bool:
    """Check if timestamp is in London session."""
    sf = SessionFilter()
    session = sf.get_session(timestamp)
    return session in [TradingSession.LONDON, TradingSession.LONDON_NY_OVERLAP]


def is_asia_session(timestamp: Optional[datetime] = None) -> bool:
    """Check if timestamp is in Asia session."""
    sf = SessionFilter()
    session = sf.get_session(timestamp)
    return session == TradingSession.ASIA


def should_trade_now(timestamp: Optional[datetime] = None) -> Tuple[bool, str]:
    """
    Quick check if current time is good for trading.

    Returns:
        Tuple of (should_trade, reason)
    """
    sf = SessionFilter()
    is_optimal, session, reason = sf.is_optimal_time(timestamp)
    return is_optimal, reason
