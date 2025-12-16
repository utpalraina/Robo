"""Pine Script interpreter - executes AST with OHLCV data."""

import numpy as np
from typing import Dict, Any, List, Optional, Union
from loguru import logger
from .functions import FUNCTION_MAP, COLOR_MAP


class PineInterpreter:
    """Interpreter for Pine Script AST."""

    def __init__(self):
        self.variables: Dict[str, Any] = {}
        self.ohlcv: Dict[str, np.ndarray] = {}
        self.plots: List[Dict] = []
        self.hlines: List[Dict] = []
        self.fills: List[Dict] = []
        self.inputs: Dict[str, Any] = {}
        self.indicator_meta: Dict = {}
        self.bar_count: int = 0

    def execute(self, ast: Dict, ohlcv_data: Dict, input_overrides: Optional[Dict] = None) -> Dict:
        """
        Execute Pine Script AST with OHLCV data.

        Args:
            ast: Parsed AST from PineParser
            ohlcv_data: Dictionary with 'open', 'high', 'low', 'close', 'volume', 'time' arrays
            input_overrides: Optional dictionary to override input defaults

        Returns:
            Dictionary with plots, hlines, fills, and indicator metadata
        """
        self._reset()
        self._setup_ohlcv(ohlcv_data)

        if input_overrides:
            self.inputs = input_overrides.copy()

        # Process indicator metadata
        if ast.get('indicator'):
            self.indicator_meta = {
                'name': ast['indicator'].get('name', 'Custom Indicator'),
                'overlay': ast['indicator'].get('overlay', True),
                'shorttitle': ast['indicator'].get('shorttitle', '')
            }

        # Process inputs first (to collect default values)
        for input_def in ast.get('inputs', []):
            self._process_input(input_def)

        # Process variable assignments
        for var in ast.get('variables', []):
            self._process_assignment(var)

        # Process plot statements
        for plot in ast.get('plots', []):
            self._process_plot(plot)

        # Process hlines
        for hline in ast.get('hlines', []):
            self._process_hline(hline)

        # Process fills
        for fill in ast.get('fills', []):
            self._process_fill(fill)

        return {
            'indicator': self.indicator_meta,
            'inputs': [
                {'name': k, 'value': v, 'type': type(v).__name__}
                for k, v in self.inputs.items()
            ],
            'plots': self.plots,
            'hlines': self.hlines,
            'fills': self.fills,
            'errors': []
        }

    def _reset(self):
        """Reset interpreter state."""
        self.variables = {}
        self.ohlcv = {}
        self.plots = []
        self.hlines = []
        self.fills = []
        self.inputs = {}
        self.indicator_meta = {}
        self.bar_count = 0

    def _setup_ohlcv(self, data: Dict):
        """Setup OHLCV data and built-in variables."""
        # Convert to numpy arrays if needed
        for key in ['open', 'high', 'low', 'close', 'volume']:
            if key in data:
                self.ohlcv[key] = np.array(data[key], dtype=float)

        if 'time' in data:
            self.ohlcv['time'] = np.array(data['time'])

        self.bar_count = len(self.ohlcv.get('close', []))

        # Setup built-in price variables
        self.variables['open'] = self.ohlcv.get('open', np.array([]))
        self.variables['high'] = self.ohlcv.get('high', np.array([]))
        self.variables['low'] = self.ohlcv.get('low', np.array([]))
        self.variables['close'] = self.ohlcv.get('close', np.array([]))
        self.variables['volume'] = self.ohlcv.get('volume', np.array([]))
        self.variables['time'] = self.ohlcv.get('time', np.arange(self.bar_count))

        # Computed price variables
        if self.bar_count > 0:
            self.variables['hl2'] = (self.variables['high'] + self.variables['low']) / 2
            self.variables['hlc3'] = (self.variables['high'] + self.variables['low'] + self.variables['close']) / 3
            self.variables['ohlc4'] = (self.variables['open'] + self.variables['high'] +
                                       self.variables['low'] + self.variables['close']) / 4
        else:
            self.variables['hl2'] = np.array([])
            self.variables['hlc3'] = np.array([])
            self.variables['ohlc4'] = np.array([])

        # Bar index
        self.variables['bar_index'] = np.arange(self.bar_count)

    def _process_input(self, input_def: Dict):
        """Process an input definition."""
        # For simplicity, use a generated name or title
        title = input_def.get('title')
        default = input_def.get('default')

        if title:
            # Clean title to make a valid variable name
            var_name = title.lower().replace(' ', '_')
        else:
            var_name = f"input_{len(self.inputs)}"

        # Use override if provided, otherwise use default
        value = self.inputs.get(var_name, default)
        if value is None:
            value = default

        # Convert value based on type
        input_type = input_def.get('input_type', 'float')
        if input_type == 'int':
            value = int(value) if value is not None else 14
        elif input_type == 'float':
            value = float(value) if value is not None else 0.0
        elif input_type == 'bool':
            value = bool(value) if value is not None else False
        elif input_type == 'source':
            # Source refers to a price series
            if isinstance(value, dict) and value.get('type') == 'identifier':
                source_name = value.get('name', 'close')
            elif isinstance(value, str):
                source_name = value
            else:
                source_name = 'close'
            value = self.variables.get(source_name, self.variables.get('close'))

        self.inputs[var_name] = value
        self.variables[var_name] = value

    def _process_assignment(self, var: Dict):
        """Process a variable assignment."""
        name = var.get('name')
        value_expr = var.get('value')

        if name and value_expr:
            value = self._evaluate(value_expr)
            self.variables[name] = value

    def _process_plot(self, plot: Dict):
        """Process a plot statement."""
        plot_type = plot.get('type', 'plot')

        if plot_type == 'plot':
            series_expr = plot.get('series') or (plot.get('args', [None])[0])
            series = self._evaluate(series_expr)

            if series is None:
                return

            # Convert to list for JSON serialization
            if isinstance(series, np.ndarray):
                series_list = series.tolist()
            else:
                series_list = [series] * self.bar_count if self.bar_count > 0 else []

            # Build plot data with time
            time_data = self.ohlcv.get('time', list(range(len(series_list))))
            if isinstance(time_data, np.ndarray):
                time_data = time_data.tolist()

            plot_data = [
                {'time': int(t) if not np.isnan(t) else 0, 'value': float(v) if not np.isnan(v) else None}
                for t, v in zip(time_data, series_list)
            ]

            self.plots.append({
                'type': 'line',
                'title': plot.get('title') or 'Plot',
                'color': self._resolve_color(plot.get('color', 'color.blue')),
                'lineWidth': plot.get('linewidth', 2),
                'data': plot_data
            })

        elif plot_type == 'plotshape':
            series_expr = plot.get('series') or (plot.get('args', [None])[0])
            series = self._evaluate(series_expr)

            if series is None:
                return

            # For plotshape, series is typically boolean
            if isinstance(series, np.ndarray):
                series_bool = series.astype(bool)
            else:
                series_bool = np.array([bool(series)] * self.bar_count)

            time_data = self.ohlcv.get('time', list(range(self.bar_count)))
            if isinstance(time_data, np.ndarray):
                time_data = time_data.tolist()

            # Get price level for marker placement
            location = plot.get('location', 'location.belowbar')
            if 'abovebar' in location:
                price_data = self.variables.get('high', [0] * self.bar_count)
            else:
                price_data = self.variables.get('low', [0] * self.bar_count)

            if isinstance(price_data, np.ndarray):
                price_data = price_data.tolist()

            # Build marker data (only where series is True)
            markers = []
            for i, (t, p, show) in enumerate(zip(time_data, price_data, series_bool)):
                if show:
                    markers.append({
                        'time': int(t),
                        'position': 'aboveBar' if 'abovebar' in location else 'belowBar',
                        'color': self._resolve_color(plot.get('color', 'color.green')),
                        'shape': 'arrowUp' if 'triangleup' in str(plot.get('style', '')) else 'arrowDown',
                        'text': plot.get('title', '')
                    })

            if markers:
                self.plots.append({
                    'type': 'markers',
                    'title': plot.get('title') or 'Signal',
                    'markers': markers
                })

    def _process_hline(self, hline: Dict):
        """Process an hline statement."""
        price_expr = hline.get('price') or (hline.get('args', [0])[0])
        price = self._evaluate(price_expr)

        if isinstance(price, np.ndarray):
            price = float(price[0]) if len(price) > 0 else 0

        self.hlines.append({
            'price': float(price),
            'title': hline.get('title') or '',
            'color': self._resolve_color(hline.get('color', 'color.gray')),
            'lineStyle': 'dashed' if 'dashed' in str(hline.get('linestyle', '')) else 'solid'
        })

    def _process_fill(self, fill: Dict):
        """Process a fill statement."""
        # Fill is more complex - would need plot references
        # For now, store the definition
        self.fills.append({
            'plot1': fill.get('plot1'),
            'plot2': fill.get('plot2'),
            'color': self._resolve_color(fill.get('color', 'color.blue'))
        })

    def _evaluate(self, expr: Any) -> Any:
        """Evaluate an expression."""
        if expr is None:
            return None

        if not isinstance(expr, dict):
            return expr

        expr_type = expr.get('type')

        if expr_type == 'number':
            return expr.get('value')

        elif expr_type == 'string':
            return expr.get('value')

        elif expr_type == 'bool':
            return expr.get('value')

        elif expr_type == 'na':
            return np.nan

        elif expr_type == 'color':
            return expr.get('value')

        elif expr_type == 'identifier':
            name = expr.get('name')
            # Check variables first
            if name in self.variables:
                return self.variables[name]
            # Check inputs
            if name in self.inputs:
                return self.inputs[name]
            # Return the name itself (might be a function name)
            return name

        elif expr_type == 'call':
            return self._evaluate_call(expr)

        elif expr_type == 'binary':
            return self._evaluate_binary(expr)

        elif expr_type == 'unary':
            return self._evaluate_unary(expr)

        elif expr_type == 'ternary':
            return self._evaluate_ternary(expr)

        elif expr_type == 'array_access':
            return self._evaluate_array_access(expr)

        elif expr_type == 'property_access':
            return self._evaluate_property_access(expr)

        return None

    def _evaluate_call(self, expr: Dict) -> Any:
        """Evaluate a function call."""
        callee = expr.get('callee')
        args = expr.get('args', [])

        # Get function name
        if isinstance(callee, dict):
            func_name = callee.get('name', '')
        else:
            func_name = str(callee)

        # Evaluate arguments
        eval_args = []
        for arg in args:
            if isinstance(arg, tuple):
                # Keyword argument
                key, val = arg
                eval_args.append((key, self._evaluate(val)))
            else:
                eval_args.append(self._evaluate(arg))

        # Look up function
        if func_name in FUNCTION_MAP:
            func = FUNCTION_MAP[func_name]
            # Extract positional args (skip tuples which are kwargs)
            pos_args = [a for a in eval_args if not isinstance(a, tuple)]

            try:
                # Handle special cases
                if func_name == 'ta.macd':
                    # MACD returns tuple
                    result = func(*pos_args)
                    return result  # Will be unpacked if used in multiple assignment
                elif func_name == 'ta.bb':
                    # Bollinger Bands returns tuple
                    result = func(*pos_args)
                    return result
                elif func_name in ('ta.vwma',):
                    # VWMA needs volume
                    if len(pos_args) == 2:
                        return func(pos_args[0], self.variables['volume'], pos_args[1])
                elif func_name in ('ta.stoch', 'ta.atr', 'ta.tr'):
                    # These need high, low, close
                    if len(pos_args) == 1:
                        # Single length argument, use OHLC from context
                        return func(
                            self.variables['high'],
                            self.variables['low'],
                            self.variables['close'],
                            pos_args[0]
                        )
                else:
                    return func(*pos_args)
            except Exception as e:
                logger.warning(f"Error calling {func_name}: {e}")
                return np.full(self.bar_count, np.nan)

        # Handle input functions
        if func_name.startswith('input.'):
            input_type = func_name.split('.')[1]
            default_val = eval_args[0] if eval_args else None
            title = None
            for arg in eval_args:
                if isinstance(arg, tuple) and arg[0] == 'title':
                    title = arg[1]
            return default_val

        # Handle color.new
        if func_name == 'color.new':
            base_color = eval_args[0] if eval_args else 'color.blue'
            transparency = eval_args[1] if len(eval_args) > 1 else 0
            return self._resolve_color(base_color)

        logger.warning(f"Unknown function: {func_name}")
        return np.full(self.bar_count, np.nan)

    def _evaluate_binary(self, expr: Dict) -> Any:
        """Evaluate a binary operation."""
        op = expr.get('op')
        left = self._evaluate(expr.get('left'))
        right = self._evaluate(expr.get('right'))

        # Convert scalars to arrays if one operand is array
        if isinstance(left, np.ndarray) and not isinstance(right, np.ndarray):
            right = np.full_like(left, right)
        elif isinstance(right, np.ndarray) and not isinstance(left, np.ndarray):
            left = np.full_like(right, left)

        if op == '+':
            return left + right
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            return np.where(right != 0, left / right, np.nan)
        elif op == '%':
            return np.where(right != 0, left % right, np.nan)
        elif op == '==':
            return left == right
        elif op == '!=':
            return left != right
        elif op == '<':
            return left < right
        elif op == '>':
            return left > right
        elif op == '<=':
            return left <= right
        elif op == '>=':
            return left >= right
        elif op == 'and':
            return np.logical_and(left, right)
        elif op == 'or':
            return np.logical_or(left, right)

        return None

    def _evaluate_unary(self, expr: Dict) -> Any:
        """Evaluate a unary operation."""
        op = expr.get('op')
        operand = self._evaluate(expr.get('operand'))

        if op == '-':
            return -operand
        elif op == 'not':
            return np.logical_not(operand)

        return operand

    def _evaluate_ternary(self, expr: Dict) -> Any:
        """Evaluate a ternary expression."""
        condition = self._evaluate(expr.get('condition'))
        true_val = self._evaluate(expr.get('true_value'))
        false_val = self._evaluate(expr.get('false_value'))

        if isinstance(condition, np.ndarray):
            return np.where(condition, true_val, false_val)
        else:
            return true_val if condition else false_val

    def _evaluate_array_access(self, expr: Dict) -> Any:
        """Evaluate array/series access (e.g., close[1])."""
        array = self._evaluate(expr.get('array'))
        index = self._evaluate(expr.get('index'))

        if not isinstance(array, np.ndarray):
            return None

        if isinstance(index, (int, float)):
            index = int(index)
            # Historical access: array[n] means n bars ago
            result = np.roll(array, index)
            result[:index] = np.nan
            return result

        return None

    def _evaluate_property_access(self, expr: Dict) -> Any:
        """Evaluate property access."""
        obj = self._evaluate(expr.get('object'))
        prop = expr.get('property')

        # Handle tuple unpacking from MACD, BB, etc.
        if isinstance(obj, tuple):
            if prop == '0' or prop == 'macd':
                return obj[0]
            elif prop == '1' or prop == 'signal':
                return obj[1]
            elif prop == '2' or prop == 'histogram':
                return obj[2]

        return None

    def _resolve_color(self, color: Any) -> str:
        """Resolve a color value to hex string."""
        if color is None:
            return '#2962FF'

        if isinstance(color, dict):
            color = color.get('value', 'color.blue')

        if isinstance(color, str):
            if color.startswith('#'):
                return color
            if color in COLOR_MAP:
                return COLOR_MAP[color]
            # Handle color.xyz format
            if color.startswith('color.'):
                return COLOR_MAP.get(color, '#2962FF')

        return '#2962FF'  # Default blue
