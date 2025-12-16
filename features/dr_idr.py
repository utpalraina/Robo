"""
DR/IDR (Defining Range / Initial Defining Range) Indicator

Based on the TradingView Pine Script DR/IDR V1.5 by TheMas7er and bmistiaen

Sessions (New York Time):
- RDR (Regular Defining Range): 09:30-10:30 NY, extends to 16:00
- ADR (After Defining Range): 19:30-20:30 NY, extends to 02:00 next day
- ODR (Overnight Defining Range): 03:00-04:00 NY, extends to 08:30

Key Concepts:
- DR (Defining Range): The high-low range during the defining hour
- IDR (Initial Defining Range): The open-close range (candle bodies) during the defining hour
- Middle lines: Midpoint of DR and IDR
- STD Lines: Standard deviation levels based on 0.5 IDR increments
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import Dict, List, Optional, Tuple
import pytz


class DRIDRIndicator:
    """Calculates DR/IDR levels for trading sessions."""

    def __init__(self, timezone: str = 'America/New_York'):
        self.tz = pytz.timezone(timezone)
        self.utc = pytz.UTC

        # Major Trading Sessions (times in NY timezone)
        # New York: 9:30 AM - 4:00 PM NY (main US session)
        # London: 3:00 AM - 12:00 PM NY (8:00 AM - 5:00 PM London)
        # Asia: 7:00 PM - 4:00 AM NY (8:00 AM - 5:00 PM Tokyo next day)
        self.sessions = {
            'NY': {
                'name': 'New York',
                'start': time(9, 30),   # 9:30 AM NY
                'end': time(10, 30),    # First hour: 9:30-10:30 (Defining Range)
                'extend_end': time(16, 0),  # Extends to 4:00 PM NY
                'color': 'rgba(59, 130, 246, 0.15)',   # Blue
                'border_color': '#3b82f6'
            },
            'LONDON': {
                'name': 'London',
                'start': time(3, 0),    # 3:00 AM NY = 8:00 AM London
                'end': time(4, 0),      # First hour: 3:00-4:00 AM NY
                'extend_end': time(9, 30),  # Extends to NY open
                'color': 'rgba(34, 197, 94, 0.15)',    # Green
                'border_color': '#22c55e'
            },
            'ASIA': {
                'name': 'Asia',
                'start': time(19, 0),   # 7:00 PM NY = 8:00 AM Tokyo (next day)
                'end': time(20, 0),     # First hour: 7:00-8:00 PM NY
                'extend_end': time(3, 0),   # Extends to London open
                'color': 'rgba(245, 158, 11, 0.15)',   # Orange
                'border_color': '#f59e0b'
            }
        }

    def _to_ny_time(self, dt) -> datetime:
        """Convert datetime to New York timezone."""
        if isinstance(dt, pd.Timestamp):
            dt = dt.to_pydatetime()
        if dt.tzinfo is None:
            dt = self.utc.localize(dt)
        return dt.astimezone(self.tz)

    def _to_timestamp(self, dt) -> int:
        """Convert datetime to milliseconds timestamp."""
        if isinstance(dt, pd.Timestamp):
            return int(dt.timestamp() * 1000)
        return int(dt.timestamp() * 1000)

    def find_all_sessions(self, df: pd.DataFrame) -> List[Dict]:
        """
        Find all DR/IDR sessions in the data with their time boundaries.
        Returns a list of sessions with their levels and time ranges.
        """
        if df.empty:
            return []

        sessions_found = []

        # Group data by date (in NY timezone)
        df = df.copy()
        df['ny_time'] = df.index.map(lambda x: self._to_ny_time(x))
        df['ny_date'] = df['ny_time'].apply(lambda x: x.date())

        unique_dates = df['ny_date'].unique()

        for date in unique_dates:
            day_data = df[df['ny_date'] == date]

            for session_key, session_config in self.sessions.items():
                session_result = self._calculate_session_for_date(
                    day_data, date, session_key, session_config
                )
                if session_result:
                    sessions_found.append(session_result)

        return sessions_found

    def _calculate_session_for_date(self, day_data: pd.DataFrame, date,
                                     session_key: str, session_config: Dict) -> Optional[Dict]:
        """Calculate DR/IDR for a specific session on a specific date."""

        start_time = session_config['start']
        end_time = session_config['end']

        # Filter candles within the session time
        session_mask = day_data['ny_time'].apply(
            lambda x: start_time <= x.time() < end_time
        )
        session_data = day_data[session_mask]

        if session_data.empty or len(session_data) < 1:
            return None

        # Calculate DR (Defining Range) - High/Low of the session
        dr_high = float(session_data['high'].max())
        dr_low = float(session_data['low'].min())
        dr_middle = (dr_high + dr_low) / 2

        # Calculate IDR (Initial Defining Range) - max/min of open/close
        idr_high = float(max(session_data['open'].max(), session_data['close'].max()))
        idr_low = float(min(session_data['open'].min(), session_data['close'].min()))
        idr_middle = (idr_high + idr_low) / 2

        # Session open price
        session_open = float(session_data['open'].iloc[0])

        # Time boundaries (in milliseconds for Chart.js)
        session_start_ts = self._to_timestamp(session_data.index[0])
        session_end_ts = self._to_timestamp(session_data.index[-1])

        # Calculate extend end time
        extend_end_time = session_config['extend_end']

        # Find the actual extend end from data or estimate it
        if extend_end_time < start_time:  # Crosses midnight
            # Look for next day data
            extend_end_ts = session_end_ts + (16 * 3600 * 1000)  # Approximate
        else:
            extend_mask = day_data['ny_time'].apply(
                lambda x: end_time <= x.time() <= extend_end_time
            )
            extend_data = day_data[extend_mask]
            if not extend_data.empty:
                extend_end_ts = self._to_timestamp(extend_data.index[-1])
            else:
                extend_end_ts = session_end_ts + (6 * 3600 * 1000)  # 6 hours default

        # Calculate STD levels (0.5 IDR increments)
        idr_range = idr_high - idr_low
        std_step = idr_range * 0.5 if idr_range > 0 else 0

        std_levels = []
        if std_step > 0:
            # Positive STD levels (above IDR high)
            for i in range(1, 11):
                std_levels.append({
                    'level': idr_high + (i * std_step),
                    'label': f'-{i * 0.5}',  # Negative because above the range
                    'side': 'above'
                })

            # Negative STD levels (below IDR low)
            for i in range(1, 11):
                std_levels.append({
                    'level': idr_low - (i * std_step),
                    'label': f'-{i * 0.5}',
                    'side': 'below'
                })

        return {
            'session': session_key,
            'session_name': session_config['name'],
            'date': str(date),
            'session_start_ts': session_start_ts,
            'session_end_ts': session_end_ts,
            'extend_end_ts': extend_end_ts,
            'session_open': session_open,
            'dr': {
                'high': dr_high,
                'low': dr_low,
                'middle': dr_middle,
                'range': dr_high - dr_low
            },
            'idr': {
                'high': idr_high,
                'low': idr_low,
                'middle': idr_middle,
                'range': idr_range
            },
            'std_levels': std_levels,
            'std_step': std_step,
            'box_color': session_config['color'],
            'border_color': session_config['border_color']
        }


def calculate_dr_idr_for_chart(df: pd.DataFrame,
                                show_dr: bool = True,
                                show_idr: bool = True,
                                show_middle_dr: bool = False,
                                show_middle_idr: bool = True,
                                show_open: bool = True,
                                show_std: bool = True,
                                std_levels_count: int = 5,
                                show_ny: bool = True,
                                show_london: bool = True,
                                show_asia: bool = True) -> Dict:
    """
    Calculate DR/IDR levels formatted for chart display.
    Returns all sessions with their boxes and lines.

    Sessions:
    - NY (New York): 9:30-10:30 AM NY time
    - London: 3:00-4:00 AM NY time (8:00-9:00 AM London)
    - Asia: 7:00-8:00 PM NY time (8:00-9:00 AM Tokyo next day)
    """
    indicator = DRIDRIndicator()
    all_sessions = indicator.find_all_sessions(df)

    # Filter sessions based on settings
    filtered_sessions = []
    for session in all_sessions:
        if session['session'] == 'NY' and show_ny:
            filtered_sessions.append(session)
        elif session['session'] == 'LONDON' and show_london:
            filtered_sessions.append(session)
        elif session['session'] == 'ASIA' and show_asia:
            filtered_sessions.append(session)

    # Build chart annotations
    boxes = []
    lines = []
    labels = []

    for idx, session in enumerate(filtered_sessions):
        prefix = f"{session['session']}_{session['date']}"

        # IDR Box (shaded area)
        if show_idr:
            boxes.append({
                'id': f'{prefix}_idr_box',
                'type': 'idr_box',
                'xMin': session['session_start_ts'],
                'xMax': session['session_end_ts'],
                'yMin': session['idr']['low'],
                'yMax': session['idr']['high'],
                'backgroundColor': session['box_color'],
                'borderColor': session['border_color'],
                'borderWidth': 1
            })

        # DR Lines (gray, solid)
        if show_dr:
            lines.append({
                'id': f'{prefix}_dr_high',
                'type': 'dr_high',
                'xMin': session['session_start_ts'],
                'xMax': session['extend_end_ts'],
                'y': session['dr']['high'],
                'color': '#808080',
                'style': 'solid',
                'width': 1,
                'label': 'DR High'
            })
            lines.append({
                'id': f'{prefix}_dr_low',
                'type': 'dr_low',
                'xMin': session['session_start_ts'],
                'xMax': session['extend_end_ts'],
                'y': session['dr']['low'],
                'color': '#808080',
                'style': 'solid',
                'width': 1,
                'label': 'DR Low'
            })

        # IDR Lines (red, dashed)
        if show_idr:
            lines.append({
                'id': f'{prefix}_idr_high',
                'type': 'idr_high',
                'xMin': session['session_start_ts'],
                'xMax': session['extend_end_ts'],
                'y': session['idr']['high'],
                'color': '#ef4444',
                'style': 'dashed',
                'width': 1,
                'label': 'IDR High'
            })
            lines.append({
                'id': f'{prefix}_idr_low',
                'type': 'idr_low',
                'xMin': session['session_start_ts'],
                'xMax': session['extend_end_ts'],
                'y': session['idr']['low'],
                'color': '#ef4444',
                'style': 'dashed',
                'width': 1,
                'label': 'IDR Low'
            })

        # Middle IDR line (dotted)
        if show_middle_idr:
            lines.append({
                'id': f'{prefix}_idr_mid',
                'type': 'idr_middle',
                'xMin': session['session_start_ts'],
                'xMax': session['extend_end_ts'],
                'y': session['idr']['middle'],
                'color': '#ef4444',
                'style': 'dotted',
                'width': 1,
                'label': 'IDR Mid'
            })

        # Opening line (green, dotted)
        if show_open:
            lines.append({
                'id': f'{prefix}_open',
                'type': 'open',
                'xMin': session['session_start_ts'],
                'xMax': session['extend_end_ts'],
                'y': session['session_open'],
                'color': '#22c55e',
                'style': 'dotted',
                'width': 1,
                'label': 'Open'
            })

        # STD Lines (gray, dotted) - only for most recent NY session
        if show_std and session['std_levels'] and session['session'] == 'NY':
            for i, std in enumerate(session['std_levels'][:std_levels_count * 2]):
                lines.append({
                    'id': f'{prefix}_std_{i}',
                    'type': 'std',
                    'xMin': session['session_end_ts'],
                    'xMax': session['extend_end_ts'],
                    'y': std['level'],
                    'color': '#808080',
                    'style': 'dotted',
                    'width': 1,
                    'label': std['label'],
                    'showLabel': True
                })

    # Get the most recent session's data for summary
    latest_ny = None
    for session in reversed(filtered_sessions):
        if session['session'] == 'NY':
            latest_ny = session
            break

    return {
        'sessions': filtered_sessions,
        'boxes': boxes,
        'lines': lines,
        'current_session': latest_ny,
        'dr': latest_ny['dr'] if latest_ny else None,
        'idr': latest_ny['idr'] if latest_ny else None
    }
