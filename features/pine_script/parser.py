"""Pine Script parser - builds AST from tokens."""

from typing import List, Dict, Any, Optional
from .lexer import Token, TokenType
from loguru import logger


class PineParser:
    """Parser for Pine Script - builds Abstract Syntax Tree.

    This parser supports a subset of Pine Script v5 syntax and is designed
    to be forgiving with unsupported constructs.
    """

    def __init__(self):
        self.tokens: List[Token] = []
        self.pos = 0
        self.current: Optional[Token] = None
        self.errors: List[str] = []

    def parse(self, tokens: List[Token]) -> Dict[str, Any]:
        """Parse tokens into AST."""
        # Filter out comments and newlines for easier parsing
        self.tokens = [t for t in tokens if t.type not in (TokenType.COMMENT, TokenType.NEWLINE)]
        self.pos = 0
        self.current = self.tokens[0] if self.tokens else None
        self.errors = []

        ast = {
            'version': None,
            'indicator': None,
            'imports': [],
            'inputs': [],
            'variables': [],
            'statements': [],
            'plots': [],
            'hlines': [],
            'fills': [],
            'errors': []
        }

        while not self._is_at_end():
            try:
                statement = self._parse_statement()
                if statement:
                    self._categorize_statement(ast, statement)
            except SyntaxError as e:
                self.errors.append(str(e))
                # Try to recover by skipping to next statement
                self._skip_to_next_statement()
            except Exception as e:
                self.errors.append(f"Unexpected error: {e}")
                self._skip_to_next_statement()

        ast['errors'] = self.errors
        return ast

    def _skip_to_next_statement(self):
        """Skip tokens until we find something that looks like a statement start."""
        statement_starters = {'var', 'varip', 'if', 'for', 'while', 'switch',
                            'indicator', 'strategy', 'import', 'export',
                            'plot', 'hline', 'fill', 'bgcolor'}

        while not self._is_at_end():
            # Check if current token starts a new statement
            if self._check(TokenType.KEYWORD) and self.current.value in statement_starters:
                return
            if self._check(TokenType.IDENTIFIER):
                # Check if this is an assignment
                next_tok = self._peek()
                if next_tok and next_tok.type in (TokenType.ASSIGN, TokenType.REASSIGN):
                    return
            self._advance()

    def _categorize_statement(self, ast: Dict, statement: Dict):
        """Categorize a statement into the appropriate AST section."""
        stmt_type = statement.get('type')

        if stmt_type == 'version':
            ast['version'] = statement.get('value')
        elif stmt_type == 'indicator':
            ast['indicator'] = statement
        elif stmt_type == 'import':
            ast['imports'].append(statement)
        elif stmt_type == 'input':
            ast['inputs'].append(statement)
        elif stmt_type == 'assignment':
            ast['variables'].append(statement)
        elif stmt_type == 'plot':
            ast['plots'].append(statement)
        elif stmt_type == 'hline':
            ast['hlines'].append(statement)
        elif stmt_type == 'fill':
            ast['fills'].append(statement)
        else:
            ast['statements'].append(statement)

    def _advance(self) -> Token:
        """Advance to next token."""
        token = self.current
        self.pos += 1
        self.current = self.tokens[self.pos] if self.pos < len(self.tokens) else None
        return token

    def _peek(self, offset: int = 1) -> Optional[Token]:
        """Peek at upcoming token."""
        pos = self.pos + offset
        return self.tokens[pos] if pos < len(self.tokens) else None

    def _is_at_end(self) -> bool:
        """Check if at end of tokens."""
        return self.current is None or self.current.type == TokenType.EOF

    def _check(self, *types: TokenType) -> bool:
        """Check if current token is one of the given types."""
        return self.current and self.current.type in types

    def _check_keyword(self, *keywords: str) -> bool:
        """Check if current token is a keyword with one of the given values."""
        return self._check(TokenType.KEYWORD) and self.current.value in keywords

    def _match(self, *types: TokenType) -> bool:
        """Match and consume if current token is one of the given types."""
        if self._check(*types):
            self._advance()
            return True
        return False

    def _expect(self, token_type: TokenType, message: str) -> Token:
        """Expect and consume a specific token type."""
        if not self._check(token_type):
            raise SyntaxError(f"{message} at line {self.current.line if self.current else '?'}")
        return self._advance()

    def _parse_statement(self) -> Optional[Dict]:
        """Parse a single statement."""
        if self._is_at_end():
            return None

        # Version directive
        if self._check(TokenType.VERSION):
            token = self._advance()
            return {'type': 'version', 'value': token.value}

        # Import statements
        if self._check_keyword('import'):
            return self._parse_import()

        # Indicator/strategy declaration
        if self._check_keyword('indicator', 'strategy'):
            return self._parse_indicator_declaration()

        # Variable declarations with 'var' or 'varip'
        if self._check_keyword('var', 'varip'):
            return self._parse_var_declaration()

        # Input declarations (when 'input' is used standalone)
        if self._check_keyword('input'):
            return self._parse_input()

        # Function calls (plot, hline, etc.)
        if self._check_keyword('plot', 'plotshape', 'plotchar', 'hline', 'fill', 'bgcolor', 'barcolor'):
            return self._parse_plot_function()

        # If statement
        if self._check_keyword('if'):
            return self._parse_if_statement()

        # For loop
        if self._check_keyword('for'):
            return self._parse_for_loop()

        # While loop
        if self._check_keyword('while'):
            return self._parse_while_loop()

        # Switch statement
        if self._check_keyword('switch'):
            return self._parse_switch_statement()

        # Tuple unpacking: [a, b] = expression
        if self._check(TokenType.LBRACKET):
            return self._parse_tuple_unpacking()

        # Assignment or expression
        if self._check(TokenType.IDENTIFIER):
            return self._parse_assignment_or_expression()

        # Skip unknown tokens
        self._advance()
        return None

    def _parse_import(self) -> Dict:
        """Parse import statement: import Library/Name/version as alias"""
        self._advance()  # Skip 'import'

        # Collect the library path (e.g., PineCoders/VisibleChart/4)
        path_parts = []
        while not self._is_at_end():
            if self._check(TokenType.IDENTIFIER, TokenType.KEYWORD):
                path_parts.append(self._advance().value)
            elif self._match(TokenType.DIVIDE):
                path_parts.append('/')
            elif self._check(TokenType.NUMBER):
                path_parts.append(str(int(self._advance().value)))
            else:
                break

        path = ''.join(path_parts)
        alias = None

        # Check for 'as alias'
        if self._check_keyword('as'):
            self._advance()
            if self._check(TokenType.IDENTIFIER):
                alias = self._advance().value

        return {
            'type': 'import',
            'path': path,
            'alias': alias
        }

    def _parse_indicator_declaration(self) -> Dict:
        """Parse indicator() or strategy() declaration."""
        func_name = self._advance().value  # 'indicator' or 'strategy'
        self._expect(TokenType.LPAREN, "Expected '(' after indicator")

        # Parse arguments
        args = self._parse_function_args()

        self._expect(TokenType.RPAREN, "Expected ')' after indicator arguments")

        # Extract key properties
        name = args[0] if args and not isinstance(args[0], tuple) else "Unnamed"
        if isinstance(name, dict):
            name = name.get('value', 'Unnamed')

        kwargs = {}
        for arg in args:
            if isinstance(arg, tuple):
                kwargs[arg[0]] = arg[1]

        return {
            'type': 'indicator',
            'func': func_name,
            'name': name,
            'overlay': kwargs.get('overlay', True),
            'shorttitle': kwargs.get('shorttitle', name),
            'args': args
        }

    def _parse_var_declaration(self) -> Dict:
        """Parse var/varip declaration with optional type annotation."""
        modifier = self._advance().value  # 'var' or 'varip'

        # Check for type annotation: var int name, var float[] name, var line name
        var_type = None
        is_array = False

        # Check if next token is a type keyword
        if self._check_keyword('int', 'float', 'bool', 'string', 'color', 'line', 'label', 'box', 'table', 'array'):
            var_type = self._advance().value

            # Check for array type: type[]
            if self._match(TokenType.LBRACKET):
                is_array = True
                self._expect(TokenType.RBRACKET, "Expected ']' after '['")

        # Variable name
        if not self._check(TokenType.IDENTIFIER):
            # Try to handle as expression if no identifier
            self.errors.append(f"Expected variable name at line {self.current.line if self.current else '?'}")
            return None

        name = self._advance().value

        # Assignment
        if not self._match(TokenType.ASSIGN):
            # Variable declaration without initialization
            return {
                'type': 'assignment',
                'modifier': modifier,
                'var_type': var_type,
                'is_array': is_array,
                'name': name,
                'value': {'type': 'na'}
            }

        value = self._parse_expression()

        return {
            'type': 'assignment',
            'modifier': modifier,
            'var_type': var_type,
            'is_array': is_array,
            'name': name,
            'value': value
        }

    def _parse_tuple_unpacking(self) -> Dict:
        """Parse tuple unpacking: [a, b, c] = expression"""
        self._advance()  # Skip '['

        names = []
        while not self._check(TokenType.RBRACKET) and not self._is_at_end():
            if self._check(TokenType.IDENTIFIER):
                names.append(self._advance().value)
            if not self._match(TokenType.COMMA):
                break

        self._expect(TokenType.RBRACKET, "Expected ']' in tuple unpacking")
        self._expect(TokenType.ASSIGN, "Expected '=' after tuple")

        value = self._parse_expression()

        return {
            'type': 'tuple_unpacking',
            'names': names,
            'value': value
        }

    def _parse_if_statement(self) -> Dict:
        """Parse if statement (simplified - just skip for now)."""
        self._advance()  # Skip 'if'

        # Parse condition
        condition = self._parse_expression()

        # Skip the body (we don't fully support control flow yet)
        # This is a simplified version
        return {
            'type': 'if',
            'condition': condition,
            'body': [],
            'else_body': []
        }

    def _parse_for_loop(self) -> Dict:
        """Parse for loop (simplified)."""
        self._advance()  # Skip 'for'
        return {'type': 'for', 'body': []}

    def _parse_while_loop(self) -> Dict:
        """Parse while loop (simplified)."""
        self._advance()  # Skip 'while'
        return {'type': 'while', 'body': []}

    def _parse_switch_statement(self) -> Dict:
        """Parse switch statement (simplified)."""
        self._advance()  # Skip 'switch'

        # Skip until we're past the switch
        paren_depth = 0
        while not self._is_at_end():
            if self._match(TokenType.LPAREN):
                paren_depth += 1
            elif self._match(TokenType.RPAREN):
                paren_depth -= 1
                if paren_depth < 0:
                    break
            else:
                self._advance()

        return {'type': 'switch', 'cases': []}

    def _parse_input(self) -> Dict:
        """Parse input.int(), input.float(), etc."""
        self._advance()  # Skip 'input'

        # Handle input.type() syntax
        if self._match(TokenType.DOT):
            if self._check(TokenType.IDENTIFIER, TokenType.KEYWORD):
                input_type = self._advance().value
            else:
                input_type = 'float'
        else:
            input_type = 'float'  # default

        self._expect(TokenType.LPAREN, "Expected '(' after input type")
        args = self._parse_function_args()
        self._expect(TokenType.RPAREN, "Expected ')' after input arguments")

        # Parse default value and title from args
        default_value = args[0] if args and not isinstance(args[0], tuple) else None
        if isinstance(default_value, dict):
            default_value = default_value.get('value')

        title = None
        minval = None
        maxval = None
        options = None
        group = None

        # Extract keyword arguments
        for arg in args:
            if isinstance(arg, tuple):
                key, val = arg
                if isinstance(val, dict):
                    val = val.get('value')
                if key == 'title':
                    title = val
                elif key == 'minval':
                    minval = val
                elif key == 'maxval':
                    maxval = val
                elif key == 'options':
                    options = val
                elif key == 'group':
                    group = val

        # Handle second positional argument as title
        if title is None and len(args) > 1 and not isinstance(args[1], tuple):
            title = args[1].get('value') if isinstance(args[1], dict) else args[1]

        return {
            'type': 'input',
            'input_type': input_type,
            'default': default_value,
            'title': title,
            'minval': minval,
            'maxval': maxval,
            'options': options,
            'group': group
        }

    def _parse_plot_function(self) -> Dict:
        """Parse plot(), hline(), fill(), etc."""
        func_name = self._advance().value

        self._expect(TokenType.LPAREN, f"Expected '(' after {func_name}")
        args = self._parse_function_args()
        self._expect(TokenType.RPAREN, f"Expected ')' after {func_name} arguments")

        # Extract common properties
        result = {
            'type': func_name,
            'args': args
        }

        # Handle specific function types
        if func_name == 'plot':
            result['series'] = args[0] if args else None
            result['title'] = self._get_kwarg(args, 'title', args[1] if len(args) > 1 and isinstance(args[1], str) else None)
            result['color'] = self._get_kwarg(args, 'color', 'color.blue')
            result['linewidth'] = self._get_kwarg(args, 'linewidth', 2)
            result['style'] = self._get_kwarg(args, 'style', 'plot.style_line')

        elif func_name == 'hline':
            result['price'] = args[0] if args else 0
            result['title'] = self._get_kwarg(args, 'title', '')
            result['color'] = self._get_kwarg(args, 'color', 'color.gray')
            result['linestyle'] = self._get_kwarg(args, 'linestyle', 'hline.style_dashed')

        elif func_name == 'plotshape':
            result['series'] = args[0] if args else None
            result['title'] = self._get_kwarg(args, 'title', '')
            result['location'] = self._get_kwarg(args, 'location', 'location.belowbar')
            result['color'] = self._get_kwarg(args, 'color', 'color.green')
            result['style'] = self._get_kwarg(args, 'style', 'shape.triangleup')
            result['size'] = self._get_kwarg(args, 'size', 'size.auto')

        elif func_name == 'fill':
            result['plot1'] = args[0] if args else None
            result['plot2'] = args[1] if len(args) > 1 else None
            result['color'] = self._get_kwarg(args, 'color', 'color.blue')

        return result

    def _get_kwarg(self, args: List, key: str, default: Any = None) -> Any:
        """Extract keyword argument from args list."""
        for arg in args:
            if isinstance(arg, tuple) and arg[0] == key:
                val = arg[1]
                if isinstance(val, dict):
                    return val.get('value', val)
                return val
        return default

    def _parse_assignment_or_expression(self) -> Dict:
        """Parse assignment or standalone expression."""
        name = self._advance().value

        # Check for assignment
        if self._match(TokenType.ASSIGN):
            value = self._parse_expression()
            return {
                'type': 'assignment',
                'name': name,
                'value': value
            }
        elif self._match(TokenType.REASSIGN):
            value = self._parse_expression()
            return {
                'type': 'reassignment',
                'name': name,
                'value': value
            }
        else:
            # Standalone expression (likely a function call result we need to track)
            # Put the identifier back and parse as expression
            self.pos -= 1
            self.current = self.tokens[self.pos]
            return {
                'type': 'expression',
                'value': self._parse_expression()
            }

    def _parse_expression(self) -> Any:
        """Parse an expression."""
        return self._parse_ternary()

    def _parse_ternary(self) -> Any:
        """Parse ternary expression: cond ? true_val : false_val"""
        expr = self._parse_or()

        if self._match(TokenType.QUESTION):
            true_val = self._parse_expression()
            self._expect(TokenType.COLON, "Expected ':' in ternary expression")
            false_val = self._parse_expression()
            return {
                'type': 'ternary',
                'condition': expr,
                'true_value': true_val,
                'false_value': false_val
            }

        return expr

    def _parse_or(self) -> Any:
        """Parse logical OR."""
        left = self._parse_and()

        while self._check_keyword('or'):
            self._advance()
            right = self._parse_and()
            left = {'type': 'binary', 'op': 'or', 'left': left, 'right': right}

        return left

    def _parse_and(self) -> Any:
        """Parse logical AND."""
        left = self._parse_comparison()

        while self._check_keyword('and'):
            self._advance()
            right = self._parse_comparison()
            left = {'type': 'binary', 'op': 'and', 'left': left, 'right': right}

        return left

    def _parse_comparison(self) -> Any:
        """Parse comparison operators."""
        left = self._parse_additive()

        while self._check(TokenType.EQ, TokenType.NE, TokenType.LT, TokenType.GT, TokenType.LE, TokenType.GE):
            op = self._advance().value
            right = self._parse_additive()
            left = {'type': 'binary', 'op': op, 'left': left, 'right': right}

        return left

    def _parse_additive(self) -> Any:
        """Parse addition/subtraction."""
        left = self._parse_multiplicative()

        while self._check(TokenType.PLUS, TokenType.MINUS):
            op = self._advance().value
            right = self._parse_multiplicative()
            left = {'type': 'binary', 'op': op, 'left': left, 'right': right}

        return left

    def _parse_multiplicative(self) -> Any:
        """Parse multiplication/division."""
        left = self._parse_unary()

        while self._check(TokenType.MULTIPLY, TokenType.DIVIDE, TokenType.MODULO):
            op = self._advance().value
            right = self._parse_unary()
            left = {'type': 'binary', 'op': op, 'left': left, 'right': right}

        return left

    def _parse_unary(self) -> Any:
        """Parse unary operators."""
        if self._match(TokenType.MINUS):
            return {'type': 'unary', 'op': '-', 'operand': self._parse_unary()}
        if self._check_keyword('not'):
            self._advance()
            return {'type': 'unary', 'op': 'not', 'operand': self._parse_unary()}
        return self._parse_postfix()

    def _parse_postfix(self) -> Any:
        """Parse postfix expressions (array access, function calls)."""
        expr = self._parse_primary()

        while True:
            if self._match(TokenType.LBRACKET):
                # Array/series access: expr[index]
                index = self._parse_expression()
                self._expect(TokenType.RBRACKET, "Expected ']' after array index")
                expr = {'type': 'array_access', 'array': expr, 'index': index}
            elif self._match(TokenType.DOT):
                # Property access or method call: expr.property or expr.method()
                if self._check(TokenType.IDENTIFIER, TokenType.KEYWORD):
                    prop = self._advance().value
                    expr = {'type': 'property_access', 'object': expr, 'property': prop}
                else:
                    break
            elif self._match(TokenType.LPAREN):
                # Function call: expr(args)
                args = self._parse_function_args()
                self._expect(TokenType.RPAREN, "Expected ')' after function arguments")
                expr = {'type': 'call', 'callee': expr, 'args': args}
            else:
                break

        return expr

    def _parse_primary(self) -> Any:
        """Parse primary expressions."""
        # Parenthesized expression
        if self._match(TokenType.LPAREN):
            expr = self._parse_expression()
            self._expect(TokenType.RPAREN, "Expected ')' after expression")
            return expr

        # Array literal or tuple: [a, b, c]
        if self._match(TokenType.LBRACKET):
            elements = []
            while not self._check(TokenType.RBRACKET) and not self._is_at_end():
                elements.append(self._parse_expression())
                if not self._match(TokenType.COMMA):
                    break
            self._expect(TokenType.RBRACKET, "Expected ']' after array elements")
            return {'type': 'array', 'elements': elements}

        # Literals
        if self._check(TokenType.NUMBER):
            return {'type': 'number', 'value': self._advance().value}

        if self._check(TokenType.STRING):
            return {'type': 'string', 'value': self._advance().value}

        if self._check(TokenType.BOOL):
            return {'type': 'bool', 'value': self._advance().value}

        if self._check(TokenType.NA):
            self._advance()
            return {'type': 'na'}

        if self._check(TokenType.COLOR):
            return {'type': 'color', 'value': self._advance().value}

        # Identifiers and namespaced calls (ta.sma, input.int, etc.)
        if self._check(TokenType.IDENTIFIER, TokenType.KEYWORD):
            name = self._advance().value
            return {'type': 'identifier', 'name': name}

        # If we get here, skip the problematic token and return na
        if self.current:
            self.errors.append(f"Unexpected token: {self.current} at line {self.current.line}")
            self._advance()
        return {'type': 'na'}

    def _parse_function_args(self) -> List:
        """Parse function arguments."""
        args = []

        while not self._check(TokenType.RPAREN) and not self._is_at_end():
            # Check for keyword argument: name=value
            if self._check(TokenType.IDENTIFIER, TokenType.KEYWORD):
                next_tok = self._peek()
                if next_tok and next_tok.type == TokenType.ASSIGN:
                    key = self._advance().value
                    self._advance()  # Skip '='
                    value = self._parse_expression()
                    args.append((key, value))
                else:
                    args.append(self._parse_expression())
            else:
                args.append(self._parse_expression())

            if not self._match(TokenType.COMMA):
                break

        return args
