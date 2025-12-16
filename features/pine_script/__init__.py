"""Pine Script parser and interpreter for custom indicators."""

from .lexer import PineLexer
from .parser import PineParser
from .interpreter import PineInterpreter
from .functions import BuiltinFunctions

__all__ = ['PineLexer', 'PineParser', 'PineInterpreter', 'BuiltinFunctions', 'parse_and_execute']


def parse_and_execute(pine_script: str, ohlcv_data: dict) -> dict:
    """
    Parse and execute a Pine Script indicator.

    Args:
        pine_script: Pine Script source code
        ohlcv_data: Dictionary with 'open', 'high', 'low', 'close', 'volume' arrays

    Returns:
        Dictionary with:
        - 'indicator': Indicator metadata (name, overlay, etc.)
        - 'inputs': List of input definitions
        - 'plots': List of plot data
        - 'hlines': List of horizontal lines
        - 'errors': List of any errors
    """
    try:
        lexer = PineLexer()
        parser = PineParser()
        interpreter = PineInterpreter()

        tokens = lexer.tokenize(pine_script)
        ast = parser.parse(tokens)
        result = interpreter.execute(ast, ohlcv_data)

        return result
    except Exception as e:
        return {
            'indicator': None,
            'inputs': [],
            'plots': [],
            'hlines': [],
            'errors': [str(e)]
        }


def validate_script(pine_script: str) -> dict:
    """
    Validate a Pine Script without executing.

    Returns:
        Dictionary with:
        - 'valid': Boolean
        - 'indicator': Indicator metadata if valid
        - 'inputs': List of input definitions
        - 'errors': List of error messages
    """
    try:
        lexer = PineLexer()
        parser = PineParser()

        tokens = lexer.tokenize(pine_script)
        ast = parser.parse(tokens)

        return {
            'valid': True,
            'indicator': ast.get('indicator'),
            'inputs': ast.get('inputs', []),
            'plots': [p['title'] for p in ast.get('plots', [])],
            'errors': []
        }
    except Exception as e:
        return {
            'valid': False,
            'indicator': None,
            'inputs': [],
            'plots': [],
            'errors': [str(e)]
        }
