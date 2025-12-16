"""Pine Script lexer - tokenizes Pine Script source code."""

import re
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    """Token types for Pine Script."""
    # Literals
    NUMBER = auto()
    STRING = auto()
    COLOR = auto()
    BOOL = auto()
    NA = auto()

    # Identifiers and keywords
    IDENTIFIER = auto()
    KEYWORD = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    MULTIPLY = auto()
    DIVIDE = auto()
    MODULO = auto()
    ASSIGN = auto()
    REASSIGN = auto()
    EQ = auto()
    NE = auto()
    LT = auto()
    GT = auto()
    LE = auto()
    GE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    QUESTION = auto()
    COLON = auto()

    # Punctuation
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    DOT = auto()
    NEWLINE = auto()
    ARROW = auto()  # =>

    # Special
    COMMENT = auto()
    VERSION = auto()
    EOF = auto()


@dataclass
class Token:
    """Represents a single token."""
    type: TokenType
    value: any
    line: int
    column: int


class PineLexer:
    """Lexer for Pine Script."""

    KEYWORDS = {
        # Declaration keywords
        'indicator', 'strategy', 'library',
        'var', 'varip', 'const',
        # Control flow
        'if', 'else', 'for', 'while', 'switch', 'case', 'default', 'to', 'by', 'break', 'continue', 'return',
        # Boolean and null
        'true', 'false', 'na',
        # Logical operators
        'and', 'or', 'not',
        # Import/export
        'import', 'export', 'as',
        # Types
        'series', 'simple', 'input', 'int', 'float', 'bool', 'string', 'color',
        'array', 'matrix', 'map', 'line', 'label', 'box', 'table',
        # Plot functions
        'plot', 'plotshape', 'plotchar', 'plotarrow', 'plotcandle', 'plotbar',
        'hline', 'fill', 'bgcolor', 'barcolor',
        # Built-in namespaces
        'ta', 'math', 'str', 'chart', 'runtime', 'syminfo', 'timeframe', 'barstate', 'session',
        'request', 'ticker', 'timestamp', 'year', 'month', 'dayofmonth', 'dayofweek', 'hour', 'minute', 'second',
        # Common functions/variables
        'open', 'high', 'low', 'close', 'volume', 'time', 'bar_index',
        'hl2', 'hlc3', 'ohlc4', 'hlcc4',
        'nz', 'fixnan', 'na', 'isnull',
    }

    COLORS = {
        'color.aqua', 'color.black', 'color.blue', 'color.fuchsia',
        'color.gray', 'color.green', 'color.lime', 'color.maroon',
        'color.navy', 'color.olive', 'color.orange', 'color.purple',
        'color.red', 'color.silver', 'color.teal', 'color.white',
        'color.yellow',
    }

    def __init__(self):
        self.source = ""
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def tokenize(self, source: str) -> List[Token]:
        """Tokenize Pine Script source code."""
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens = []

        while self.pos < len(self.source):
            self._scan_token()

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    def _scan_token(self):
        """Scan a single token."""
        self._skip_whitespace()

        if self.pos >= len(self.source):
            return

        char = self.source[self.pos]

        # Comments
        if char == '/' and self._peek() == '/':
            self._scan_comment()
            return

        # Version directive
        if char == '/' and self._peek() == '@':
            self._scan_version()
            return

        # Newlines
        if char == '\n':
            self._add_token(TokenType.NEWLINE, '\n')
            self._advance()
            self.line += 1
            self.column = 1
            return

        # Numbers
        if char.isdigit() or (char == '.' and self._peek().isdigit()):
            self._scan_number()
            return

        # Strings
        if char in '"\'':
            self._scan_string(char)
            return

        # Identifiers and keywords
        if char.isalpha() or char == '_':
            self._scan_identifier()
            return

        # Operators and punctuation
        self._scan_operator()

    def _skip_whitespace(self):
        """Skip whitespace (but not newlines)."""
        while self.pos < len(self.source) and self.source[self.pos] in ' \t\r':
            self._advance()

    def _advance(self) -> str:
        """Advance position and return current character."""
        char = self.source[self.pos] if self.pos < len(self.source) else ''
        self.pos += 1
        self.column += 1
        return char

    def _peek(self, offset: int = 1) -> str:
        """Peek at upcoming character."""
        pos = self.pos + offset
        return self.source[pos] if pos < len(self.source) else ''

    def _add_token(self, token_type: TokenType, value: any):
        """Add a token to the list."""
        self.tokens.append(Token(token_type, value, self.line, self.column))

    def _scan_comment(self):
        """Scan a line comment."""
        start_col = self.column
        self._advance()  # Skip first /
        self._advance()  # Skip second /
        comment = ""
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            comment += self._advance()
        self._add_token(TokenType.COMMENT, comment.strip())

    def _scan_version(self):
        """Scan a version directive like //@version=5."""
        start_col = self.column
        self._advance()  # Skip /
        self._advance()  # Skip @
        directive = ""
        while self.pos < len(self.source) and self.source[self.pos] != '\n':
            directive += self._advance()
        if directive.startswith('version='):
            version = directive[8:].strip()
            self._add_token(TokenType.VERSION, version)

    def _scan_number(self):
        """Scan a number literal."""
        start = self.pos
        has_dot = False

        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char.isdigit():
                self._advance()
            elif char == '.' and not has_dot:
                has_dot = True
                self._advance()
            else:
                break

        value = self.source[start:self.pos]
        self._add_token(TokenType.NUMBER, float(value) if has_dot else int(value))

    def _scan_string(self, quote: str):
        """Scan a string literal."""
        self._advance()  # Skip opening quote
        value = ""

        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char == quote:
                self._advance()
                break
            elif char == '\\':
                self._advance()
                if self.pos < len(self.source):
                    escaped = self._advance()
                    if escaped == 'n':
                        value += '\n'
                    elif escaped == 't':
                        value += '\t'
                    else:
                        value += escaped
            elif char == '\n':
                raise SyntaxError(f"Unterminated string at line {self.line}")
            else:
                value += self._advance()

        self._add_token(TokenType.STRING, value)

    def _scan_identifier(self):
        """Scan an identifier or keyword."""
        start = self.pos

        while self.pos < len(self.source):
            char = self.source[self.pos]
            if char.isalnum() or char == '_':
                self._advance()
            elif char == '.':
                # Check for namespaced identifiers like ta.sma, color.red
                next_start = self.pos + 1
                if next_start < len(self.source) and self.source[next_start].isalpha():
                    self._advance()  # Include the dot
                else:
                    break
            else:
                break

        value = self.source[start:self.pos]

        # Check for colors
        if value in self.COLORS or value.startswith('color.'):
            self._add_token(TokenType.COLOR, value)
        # Check for keywords
        elif value in self.KEYWORDS or value.split('.')[0] in self.KEYWORDS:
            if value == 'true':
                self._add_token(TokenType.BOOL, True)
            elif value == 'false':
                self._add_token(TokenType.BOOL, False)
            elif value == 'na':
                self._add_token(TokenType.NA, None)
            else:
                self._add_token(TokenType.KEYWORD, value)
        else:
            self._add_token(TokenType.IDENTIFIER, value)

    def _scan_operator(self):
        """Scan an operator or punctuation."""
        char = self._advance()

        # Two-character operators
        if self.pos < len(self.source):
            two_char = char + self.source[self.pos]

            if two_char == ':=':
                self._advance()
                self._add_token(TokenType.REASSIGN, ':=')
                return
            elif two_char == '=>':
                self._advance()
                self._add_token(TokenType.ARROW, '=>')
                return
            elif two_char == '==':
                self._advance()
                self._add_token(TokenType.EQ, '==')
                return
            elif two_char == '!=':
                self._advance()
                self._add_token(TokenType.NE, '!=')
                return
            elif two_char == '<=':
                self._advance()
                self._add_token(TokenType.LE, '<=')
                return
            elif two_char == '>=':
                self._advance()
                self._add_token(TokenType.GE, '>=')
                return

        # Single character operators
        operators = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.MULTIPLY,
            '/': TokenType.DIVIDE,
            '%': TokenType.MODULO,
            '=': TokenType.ASSIGN,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            ',': TokenType.COMMA,
            '.': TokenType.DOT,
            '?': TokenType.QUESTION,
            ':': TokenType.COLON,
        }

        if char in operators:
            self._add_token(operators[char], char)
        elif char not in ' \t\r':
            raise SyntaxError(f"Unexpected character '{char}' at line {self.line}, column {self.column}")
