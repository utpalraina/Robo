"""
Python Indicator Framework for Robo Trader

Allows creating custom indicators in Python that can draw lines, boxes,
labels, and plots on the chart. Works alongside Pine Script indicators.

Sessions (New York Time):
- New York (Regular): 9:30 AM - 10:30 AM, extends to 4:00 PM
- Tokyo (After): 7:30 PM - 8:30 PM, extends to 2:00 AM next day
- London (Overnight): 3:00 AM - 4:00 AM, extends to 8:30 AM
"""

import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from enum import Enum
import pytz


class LineStyle(Enum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"


class BoxStyle(Enum):
    SOLID = "solid"
    DASHED = "dashed"


@dataclass
class Line:
    """Represents a line drawing on the chart."""
    x1: int  # Unix timestamp
    y1: float  # Price
    x2: int  # Unix timestamp
    y2: float  # Price
    color: str = "#808080"
    width: int = 1
    style: str = "solid"
    extend_right: bool = False
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Box:
    """Represents a box/rectangle drawing on the chart."""
    x1: int  # Unix timestamp (left)
    y1: float  # Price (top)
    x2: int  # Unix timestamp (right)
    y2: float  # Price (bottom)
    border_color: str = "#808080"
    background_color: str = "rgba(128, 128, 128, 0.2)"
    border_width: int = 1
    border_style: str = "solid"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Label:
    """Represents a text label on the chart."""
    x: int  # Unix timestamp
    y: float  # Price
    text: str
    color: str = "#808080"
    background_color: str = "transparent"
    font_size: int = 12
    position: str = "right"  # left, right, above, below

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HLine:
    """Represents a horizontal line across the entire chart."""
    y: float  # Price level
    color: str = "#808080"
    width: int = 1
    style: str = "dashed"
    label: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Plot:
    """Represents a plotted series (like SMA, RSI line)."""
    values: List[float]
    name: str = "Plot"
    color: str = "#2962FF"
    width: int = 2
    style: str = "line"  # line, histogram, circles

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IndicatorOutput:
    """Container for all indicator drawing outputs."""
    lines: List[Line] = field(default_factory=list)
    boxes: List[Box] = field(default_factory=list)
    labels: List[Label] = field(default_factory=list)
    hlines: List[HLine] = field(default_factory=list)
    plots: List[Plot] = field(default_factory=list)

    def add_line(self, x1: int, y1: float, x2: int, y2: float, **kwargs) -> Line:
        line = Line(x1=x1, y1=y1, x2=x2, y2=y2, **kwargs)
        self.lines.append(line)
        return line

    def add_box(self, x1: int, y1: float, x2: int, y2: float, **kwargs) -> Box:
        box = Box(x1=x1, y1=y1, x2=x2, y2=y2, **kwargs)
        self.boxes.append(box)
        return box

    def add_label(self, x: int, y: float, text: str, **kwargs) -> Label:
        label = Label(x=x, y=y, text=text, **kwargs)
        self.labels.append(label)
        return label

    def add_hline(self, y: float, **kwargs) -> HLine:
        hline = HLine(y=y, **kwargs)
        self.hlines.append(hline)
        return hline

    def add_plot(self, values: List[float], **kwargs) -> Plot:
        plot = Plot(values=values, **kwargs)
        self.plots.append(plot)
        return plot

    def to_dict(self) -> dict:
        return {
            "lines": [l.to_dict() for l in self.lines],
            "boxes": [b.to_dict() for b in self.boxes],
            "labels": [l.to_dict() for l in self.labels],
            "hlines": [h.to_dict() for h in self.hlines],
            "plots": [p.to_dict() for p in self.plots]
        }


class PythonIndicator(ABC):
    """Base class for Python indicators."""

    name: str = "Python Indicator"
    short_name: str = "PY"
    description: str = ""
    is_overlay: bool = True  # True = draws on price chart, False = separate pane

    def __init__(self, **settings):
        self.settings = settings
        self.output = IndicatorOutput()
        self.ny_tz = pytz.timezone('America/New_York')

    @abstractmethod
    def calculate(self, df: pd.DataFrame) -> IndicatorOutput:
        """
        Calculate indicator values and return drawing objects.

        Args:
            df: DataFrame with columns: open, high, low, close, volume
                Index should be datetime

        Returns:
            IndicatorOutput with lines, boxes, labels, etc.
        """
        pass

    def get_default_settings(self) -> Dict[str, Any]:
        """Return default settings for this indicator."""
        return {}

    def timestamp_to_unix(self, dt: datetime) -> int:
        """Convert datetime to Unix timestamp."""
        if dt.tzinfo is None:
            dt = self.ny_tz.localize(dt)
        return int(dt.timestamp())

    def unix_to_datetime(self, ts: int) -> datetime:
        """Convert Unix timestamp to NY datetime."""
        return datetime.fromtimestamp(ts, tz=self.ny_tz)


class DRIndicator(PythonIndicator):
    """
    DR/IDR (Defining Range / Initial Defining Range) Indicator

    Draws session ranges for:
    - New York session (Regular): 9:30 AM - 10:30 AM NY time
    - Tokyo session (After): 7:30 PM - 8:30 PM NY time
    - London session (Overnight): 3:00 AM - 4:00 AM NY time

    Features:
    - DR lines (session high/low)
    - IDR lines (initial body range - open/close extremes)
    - Middle lines
    - Opening price line
    - Session boxes
    - Standard deviation levels
    """

    name = "DR/IDR"
    short_name = "DR"
    description = "Defining Range / Initial Defining Range - Session-based trading ranges"
    is_overlay = True

    # Session times in NY timezone (hour, minute)
    SESSIONS = {
        'new_york': {
            'name': 'New York',
            'start': (9, 30),
            'end': (10, 30),
            'extend_end': (16, 0),
            'color': '#4CAF50',  # Green
        },
        'tokyo': {
            'name': 'Tokyo',
            'start': (19, 30),
            'end': (20, 30),
            'extend_end': (2, 0),  # Next day
            'color': '#2196F3',  # Blue
        },
        'london': {
            'name': 'London',
            'start': (3, 0),
            'end': (4, 0),
            'extend_end': (8, 30),
            'color': '#FF9800',  # Orange
        }
    }

    def get_default_settings(self) -> Dict[str, Any]:
        return {
            # Session toggles
            'show_new_york': True,
            'show_tokyo': True,
            'show_london': True,
            # How many days of sessions to show (0 = all)
            'days_to_show': 7,
            # Line options
            'show_dr_lines': True,
            'show_idr_lines': True,
            'show_middle_dr': False,
            'show_middle_idr': True,
            'show_open_line': False,
            'extend_dr_lines': True,
            'extend_idr_lines': True,
            # Box options
            'show_box': True,
            'box_type': 'idr',  # 'dr' or 'idr'
            # STD lines - only show for most recent session to reduce clutter
            'show_std_lines': True,
            'std_levels': 8,  # Number of 0.5 IDR levels each direction (matches TradingView -4 to +4)
            'std_only_latest': True,  # Only show STD for most recent session
            # Style (matching TradingView)
            'dr_line_color': '#808080',  # Gray for DR
            'idr_line_color': '#FF5252',  # Red for IDR
            'middle_line_color': '#9E9E9E',  # Light gray for middle
            'open_line_color': '#4CAF50',  # Green for open
            'std_line_color': '#9E9E9E',  # Light gray for STD
            'line_width': 1,
        }

    def calculate(self, df: pd.DataFrame) -> IndicatorOutput:
        """Calculate DR/IDR levels for recent sessions in the data."""
        self.output = IndicatorOutput()
        settings = {**self.get_default_settings(), **self.settings}

        if df.empty:
            return self.output

        # Ensure index is datetime with timezone
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert(self.ny_tz)
        else:
            df.index = df.index.tz_convert(self.ny_tz)

        # Filter to only recent days if specified
        days_to_show = settings.get('days_to_show', 14)
        if days_to_show > 0:
            cutoff_date = df.index.max().date() - timedelta(days=days_to_show)
            df = df[df.index.date >= cutoff_date]

        if df.empty:
            return self.output

        # Find the most recent date for STD lines
        most_recent_date = df.index.max().date()

        # Process each session type
        for session_key, session_config in self.SESSIONS.items():
            show_key = f'show_{session_key}'
            if not settings.get(show_key, True):
                continue

            self._process_session(df, session_key, session_config, settings, most_recent_date)

        return self.output

    def _process_session(self, df: pd.DataFrame, session_key: str,
                         session_config: dict, settings: dict, most_recent_date=None):
        """Process a single session type and draw its elements."""

        start_time = time(*session_config['start'])
        end_time = time(*session_config['end'])
        extend_time = time(*session_config['extend_end'])
        color = session_config['color']

        # Group by date and find sessions
        df['date'] = df.index.date

        for date in df['date'].unique():
            day_data = df[df['date'] == date]

            # Find candles within the session defining range
            session_mask = (day_data.index.time >= start_time) & (day_data.index.time <= end_time)
            session_data = day_data[session_mask]

            if session_data.empty:
                continue

            # Calculate DR (session high/low)
            dr_high = session_data['high'].max()
            dr_low = session_data['low'].min()

            # Calculate IDR (body range - max of open/close)
            idr_high = session_data[['open', 'close']].max().max()
            idr_low = session_data[['open', 'close']].min().min()

            # Get session open price
            session_open = session_data['open'].iloc[0]

            # Calculate middle levels
            dr_middle = (dr_high + dr_low) / 2
            idr_middle = (idr_high + idr_low) / 2

            # Timestamps
            start_ts = self.timestamp_to_unix(session_data.index[0].to_pydatetime())
            end_ts = self.timestamp_to_unix(session_data.index[-1].to_pydatetime())

            # Find extension end time
            if session_config['extend_end'][0] < session_config['start'][0]:
                # Extends to next day
                extend_date = date + timedelta(days=1)
            else:
                extend_date = date

            extend_dt = datetime.combine(extend_date, extend_time)
            extend_dt = self.ny_tz.localize(extend_dt)

            # Check if we have data until extend time
            extend_mask = day_data.index <= extend_dt
            if extend_mask.any():
                extend_ts = self.timestamp_to_unix(extend_dt)
            else:
                extend_ts = self.timestamp_to_unix(day_data.index[-1].to_pydatetime())

            line_end = extend_ts if settings['extend_dr_lines'] else end_ts

            # Draw DR lines
            if settings['show_dr_lines']:
                self.output.add_line(
                    start_ts, dr_high, line_end, dr_high,
                    color=settings['dr_line_color'],
                    width=settings['line_width'],
                    style='solid',
                    label=f"{session_config['name']} DR High"
                )
                self.output.add_line(
                    start_ts, dr_low, line_end, dr_low,
                    color=settings['dr_line_color'],
                    width=settings['line_width'],
                    style='solid',
                    label=f"{session_config['name']} DR Low"
                )

            # Draw IDR lines
            idr_line_end = extend_ts if settings['extend_idr_lines'] else end_ts
            if settings['show_idr_lines']:
                self.output.add_line(
                    start_ts, idr_high, idr_line_end, idr_high,
                    color=settings['idr_line_color'],
                    width=settings['line_width'],
                    style='dashed',
                    label=f"{session_config['name']} IDR High"
                )
                self.output.add_line(
                    start_ts, idr_low, idr_line_end, idr_low,
                    color=settings['idr_line_color'],
                    width=settings['line_width'],
                    style='dashed',
                    label=f"{session_config['name']} IDR Low"
                )

            # Draw middle DR line
            if settings['show_middle_dr']:
                self.output.add_line(
                    start_ts, dr_middle, line_end, dr_middle,
                    color=settings['middle_line_color'],
                    width=settings['line_width'],
                    style='dotted',
                    label=f"{session_config['name']} DR Mid"
                )

            # Draw middle IDR line
            if settings['show_middle_idr']:
                self.output.add_line(
                    start_ts, idr_middle, idr_line_end, idr_middle,
                    color=settings['middle_line_color'],
                    width=settings['line_width'],
                    style='dotted',
                    label=f"{session_config['name']} IDR Mid"
                )

            # Draw opening line
            if settings['show_open_line']:
                self.output.add_line(
                    start_ts, session_open, line_end, session_open,
                    color=settings['open_line_color'],
                    width=settings['line_width'],
                    style='dotted',
                    label=f"{session_config['name']} Open"
                )

            # Draw session box
            if settings['show_box']:
                if settings['box_type'] == 'dr':
                    box_high, box_low = dr_high, dr_low
                else:
                    box_high, box_low = idr_high, idr_low

                # Use neutral gray color like TradingView
                bg_color = 'rgba(128, 128, 128, 0.2)'  # Light gray
                border_color = 'rgba(128, 128, 128, 0.5)'  # Gray border

                self.output.add_box(
                    start_ts, box_high, end_ts, box_low,
                    border_color=border_color,
                    background_color=bg_color,
                    border_width=1
                )

            # Draw STD (Standard Deviation) lines - only for recent session if std_only_latest is True
            should_draw_std = settings['show_std_lines']
            if should_draw_std and settings.get('std_only_latest', True) and most_recent_date:
                # Only draw STD for the most recent day
                should_draw_std = (date == most_recent_date or date == most_recent_date - timedelta(days=1))

            if should_draw_std:
                idr_range = idr_high - idr_low
                step = idr_range * 0.5  # 0.5 IDR increments

                if step > 0:
                    num_levels = settings.get('std_levels', 5)

                    # Positive levels (above IDR high)
                    for i in range(1, num_levels + 1):
                        level = idr_high + (i * step)
                        self.output.add_line(
                            start_ts, level, extend_ts, level,
                            color=settings['std_line_color'],
                            width=1,
                            style='dotted',
                            label=f"+{i * 0.5}"
                        )

                    # Negative levels (below IDR low)
                    for i in range(1, num_levels + 1):
                        level = idr_low - (i * step)
                        self.output.add_line(
                            start_ts, level, extend_ts, level,
                            color=settings['std_line_color'],
                            width=1,
                            style='dotted',
                            label=f"-{i * 0.5}"
                        )


# Registry of available Python indicators
PYTHON_INDICATORS = {
    'dr': DRIndicator,
}


def get_python_indicator(name: str, **settings) -> Optional[PythonIndicator]:
    """Get a Python indicator instance by name."""
    indicator_class = PYTHON_INDICATORS.get(name.lower())
    if indicator_class:
        return indicator_class(**settings)
    return None


def list_python_indicators() -> List[Dict[str, Any]]:
    """List all available Python indicators."""
    result = []
    for key, cls in PYTHON_INDICATORS.items():
        indicator = cls()
        result.append({
            'id': key,
            'name': indicator.name,
            'short_name': indicator.short_name,
            'description': indicator.description,
            'is_overlay': indicator.is_overlay,
            'type': 'python',
            'default_settings': indicator.get_default_settings()
        })
    return result
