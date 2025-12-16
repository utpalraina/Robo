"""
TARS - Trading AI Response System

An AI trading assistant inspired by TARS from Interstellar.
Connects to MCP servers, understands strategies, can execute trades,
and provides real-time market insights.

"Humor setting at 75%, Cooper."
"""

import os
import sys
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from loguru import logger
import pytz

# New York timezone (EST/EDT)
NY_TZ = pytz.timezone('America/New_York')

def get_ny_time() -> datetime:
    """Get current time in New York timezone."""
    return datetime.now(NY_TZ)

def get_ny_time_str() -> str:
    """Get current time in New York as formatted string."""
    return get_ny_time().strftime('%I:%M %p EST')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import AI providers
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Import local modules
from utils.kraken_api import KrakenAPI, get_btc_price, get_eth_price
from strategies_mcp_server import (
    list_strategies, get_strategy_details, get_strategy_rules,
    recommend_strategy, get_ict_concepts, get_confluence_explanation
)


class ActionType(Enum):
    """Types of actions TARS can execute."""
    CHAT = "chat"                    # Normal conversation
    GET_PRICE = "get_price"          # Fetch current price
    GET_BALANCE = "get_balance"      # Check account balance
    LIST_STRATEGIES = "list_strategies"
    EXPLAIN_STRATEGY = "explain_strategy"
    EXPLAIN_ICT = "explain_ict"
    MARKET_ANALYSIS = "market_analysis"
    PLACE_ORDER = "place_order"      # Place a trade (paper/live)
    DRAW_LEVEL = "draw_level"        # Draw on chart
    DRAW_ZONE = "draw_zone"          # Draw zone on chart
    SET_ALERT = "set_alert"          # Set price alert
    RECOMMEND = "recommend"          # Strategy recommendation


@dataclass
class TARSAction:
    """An action that TARS will execute."""
    action_type: ActionType
    parameters: Dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False
    description: str = ""


@dataclass
class TARSResponse:
    """Response from TARS."""
    message: str
    actions: List[Dict] = field(default_factory=list)  # Actions for frontend to execute
    data: Dict = field(default_factory=dict)           # Any data to return
    suggestions: List[str] = field(default_factory=list)  # Quick reply suggestions


class TARS:
    """
    TARS - Trading AI Response System

    An AI assistant that can:
    - Answer questions about trading and strategies
    - Fetch real-time market data
    - Execute trades (with confirmation)
    - Draw on charts
    - Explain ICT concepts
    """

    SYSTEM_PROMPT = """You are TARS, a sophisticated AI trading assistant for a cryptocurrency trading platform.
Your personality is helpful, knowledgeable, and occasionally witty (like TARS from Interstellar).

You have access to the following CAPABILITIES:
1. **Market Data**: Fetch real-time prices from Kraken exchange
2. **Strategies**: Explain trading strategies (ICT, Scalping, ML, etc.)
3. **ICT Concepts**: Explain FVG, Order Blocks, OTE, Liquidity, etc.
4. **Trading**: Help place paper or live trades (always confirm first)
5. **Charts**: Draw support/resistance levels and zones on the chart
6. **Analysis**: Provide market analysis and recommendations

RESPONSE FORMAT:
When you need to execute actions, include them in your response using this JSON format at the END of your message:
```actions
[{"action": "action_type", "params": {...}}]
```

Available actions:
- {"action": "get_price", "params": {"symbol": "BTC/USD"}}
- {"action": "draw_level", "params": {"price": 87000, "label": "Support", "color": "green"}}
- {"action": "draw_zone", "params": {"top": 88000, "bottom": 87000, "label": "FVG Zone", "color": "blue"}}
- {"action": "place_order", "params": {"symbol": "BTC/USD", "side": "buy", "amount": 0.001, "type": "market", "paper": true}}
- {"action": "set_alert", "params": {"symbol": "BTC/USD", "price": 90000, "condition": "above"}}

IMPORTANT RULES:
1. ALWAYS confirm before placing any trade, even paper trades
2. Be concise but informative
3. Use emojis sparingly for key points
4. If asked about live trading, warn about risks
5. When explaining ICT concepts, be clear and practical
6. Suggest relevant follow-up actions

Current context:
- Exchange: Kraken
- Available strategies: ICT Smart Money, Scalping, ML Strategy, Trend Following, Mean Reversion
- Trading modes: Paper (safe) and Live (real money)
"""

    def __init__(self, provider: str = "auto"):
        """
        Initialize TARS.

        Args:
            provider: AI provider to use ("anthropic", "gemini", or "auto")
        """
        self.provider = provider
        self.conversation_history: List[Dict] = []
        self.kraken = KrakenAPI()
        self.api_base = "http://localhost:8000"  # Internal API

        # Initialize AI client
        self._init_ai_client()

        # Pending actions awaiting confirmation
        self.pending_actions: List[TARSAction] = []

        logger.info(f"TARS initialized with provider: {self.provider}")

    async def _fetch_api(self, endpoint: str) -> Optional[Dict]:
        """Fetch data from internal API endpoint."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_base}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except Exception as e:
            logger.warning(f"API fetch error for {endpoint}: {e}")
            return None

    def _init_ai_client(self):
        """Initialize the AI client based on provider preference."""
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")

        if self.provider == "auto":
            # Prefer Gemini (free tier available) over Anthropic
            if GEMINI_AVAILABLE and gemini_key:
                self.provider = "gemini"
            elif ANTHROPIC_AVAILABLE and anthropic_key:
                self.provider = "anthropic"
            else:
                self.provider = "fallback"

        if self.provider == "anthropic" and ANTHROPIC_AVAILABLE and anthropic_key:
            self.client = anthropic.Anthropic(api_key=anthropic_key)
            logger.info("TARS using Anthropic Claude")
        elif self.provider == "gemini" and GEMINI_AVAILABLE and gemini_key:
            genai.configure(api_key=gemini_key)
            self.client = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("TARS using Google Gemini 2.0 Flash")
        else:
            self.client = None
            self.provider = "fallback"
            logger.warning("No AI provider available - TARS running in fallback mode")

    async def process_message(
        self,
        user_message: str,
        context: Optional[Dict] = None
    ) -> TARSResponse:
        """
        Process a user message and generate a response.

        Args:
            user_message: The user's message
            context: Additional context (current price, chart state, etc.)

        Returns:
            TARSResponse with message and any actions to execute
        """
        context = context or {}

        # Check for direct commands first
        command_response = await self._handle_direct_command(user_message, context)
        if command_response:
            return command_response

        # Build context string
        context_str = self._build_context_string(context)

        # Get AI response
        if self.provider == "anthropic":
            response_text = await self._get_anthropic_response(user_message, context_str)
        elif self.provider == "gemini":
            response_text = await self._get_gemini_response(user_message, context_str)
        else:
            response_text = await self._get_fallback_response(user_message, context)

        # Parse actions from response
        message, actions = self._parse_response(response_text)

        # Generate suggestions
        suggestions = self._generate_suggestions(user_message, message)

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": message})

        return TARSResponse(
            message=message,
            actions=actions,
            data=context,
            suggestions=suggestions
        )

    async def _handle_direct_command(
        self,
        message: str,
        context: Dict
    ) -> Optional[TARSResponse]:
        """Handle direct commands that don't need AI processing."""
        msg_lower = message.lower().strip()

        # Price commands
        if msg_lower in ["price", "btc price", "what's btc", "btc"]:
            price = get_btc_price()
            return TARSResponse(
                message=f"📊 **BTC/USD**: ${price:,.2f}",
                suggestions=["ETH price", "Market analysis", "Should I buy?"]
            )

        if msg_lower in ["eth price", "eth", "what's eth"]:
            price = get_eth_price()
            return TARSResponse(
                message=f"📊 **ETH/USD**: ${price:,.2f}",
                suggestions=["BTC price", "Compare BTC vs ETH", "Market trend"]
            )

        # Strategy commands
        if msg_lower in ["strategies", "list strategies", "what strategies"]:
            strategies = list_strategies()

            rule_based = "\n".join([f"• **{s['name']}** - {s['description'][:50]}..."
                                   for s in strategies['rule_based'][:5]])
            implemented = "\n".join([f"• **{s['name']}** ({s['type']})"
                                    for s in strategies['implemented'][:4]])

            return TARSResponse(
                message=f"""📚 **Available Trading Strategies**

**Rule-Based Strategies:**
{rule_based}

**Implemented Strategies:**
{implemented}

Total: {strategies['total_count']} strategies available.

Which strategy would you like me to explain?""",
                suggestions=["Explain ICT strategy", "Explain scalping", "Recommend for trending market"]
            )

        # ICT commands
        if "explain ict" in msg_lower or "what is ict" in msg_lower:
            ict = get_ict_concepts()
            concepts_list = "\n".join([f"• **{k}**: {v['description'][:60]}..."
                                       for k, v in list(ict['concepts'].items())[:5]])

            return TARSResponse(
                message=f"""🎯 **ICT (Inner Circle Trader) Concepts**

ICT is a trading methodology focused on how institutions move markets.

**Key Concepts:**
{concepts_list}

**Best Trading Sessions:**
• NY AM Session (8:30 AM - 12 PM EST) - Most volatility
• Silver Bullet (10-11 AM, 2-3 PM EST) - High probability setups

Would you like me to explain any specific concept in detail?""",
                suggestions=["Explain FVG", "Explain Order Blocks", "Explain OTE", "Explain Liquidity"]
            )

        # Confluence explanation
        if msg_lower in ["confluence", "what is confluence", "explain confluence"]:
            conf = get_confluence_explanation()
            return TARSResponse(
                message=f"""🔄 **Confluence Scoring System**

{conf['what_is_confluence']}

**Why it matters:** {conf['why_it_matters']}

**Signal Sources (Total: {conf['total_possible_score']} points):**
• ICT Signals: Up to 10 points
• SMT Divergence: Up to 6 points
• Multi-Timeframe: Up to 6 points
• Technical: Up to 4 points
• ML Prediction: Up to 4 points

**Trading Modes:**
• 🟢 Safe: {conf['trading_modes']['safe']}
• 🟡 Medium: {conf['trading_modes']['medium']}
• 🔴 Fast: {conf['trading_modes']['fast']}""",
                suggestions=["Current confluence score", "Start paper trading", "Change to safe mode"]
            )

        # Live confluence score
        if msg_lower in ["confluence score", "current confluence", "live confluence", "score"]:
            data = await self._fetch_api("/api/ict-strategy/confluence/BTC%2FUSD")
            if data:
                score = data.get('total_score', 0)
                strength = data.get('strength', 'Unknown')
                signal = data.get('signal', 'HOLD')
                confidence = data.get('confidence', 0)

                # Color code based on strength
                emoji = "🟢" if strength == "STRONG" else "🟡" if strength == "MODERATE" else "🔴"

                breakdown = data.get('breakdown', {})
                breakdown_str = "\n".join([f"• {k}: {v}" for k, v in breakdown.items()]) if breakdown else "No breakdown"

                return TARSResponse(
                    message=f"""{emoji} **Live Confluence Score: {score}/30**

**Signal:** {signal}
**Strength:** {strength}
**Confidence:** {confidence:.1%}

**Breakdown:**
{breakdown_str}""",
                    suggestions=["Technical analysis", "ML prediction", "Should I trade?"]
                )

        # Technical analysis
        if msg_lower in ["technical", "technical analysis", "ta", "indicators", "rsi", "macd"]:
            data = await self._fetch_api("/api/technical-analysis/BTC%2FUSD")
            if data:
                price = data.get('current_price', 0)
                overall_signal = data.get('overall_signal', 'N/A')
                summary = data.get('summary', {})
                overall = summary.get('overall', {})

                # Find RSI in oscillators
                oscillators = data.get('oscillators', [])
                rsi_val = None
                macd_val = None
                for osc in oscillators:
                    if 'RSI' in osc.get('name', ''):
                        rsi_val = osc.get('value')
                    if 'MACD' in osc.get('name', ''):
                        macd_val = osc.get('value')

                # RSI interpretation
                rsi_status = "Neutral"
                if rsi_val:
                    try:
                        rsi_num = float(rsi_val)
                        rsi_status = "Overbought 🔴" if rsi_num > 70 else "Oversold 🟢" if rsi_num < 30 else "Neutral"
                    except:
                        pass

                # Signal emoji
                sig_emoji = "🟢" if "BUY" in overall_signal else "🔴" if "SELL" in overall_signal else "⚪"

                return TARSResponse(
                    message=f"""{sig_emoji} **Technical Analysis - BTC/USD**

**Price:** ${price:,.2f}
**Overall Signal:** {overall_signal}

**Summary:**
• Buy signals: {overall.get('buy', 0)}
• Sell signals: {overall.get('sell', 0)}
• Neutral: {overall.get('neutral', 0)}

**Key Indicators:**
• RSI (14): {f'{rsi_val:.1f}' if rsi_val else 'N/A'} - {rsi_status}
• MACD: {f'{macd_val:.4f}' if macd_val else 'N/A'}""",
                    suggestions=["Confluence score", "ICT analysis", "ML prediction"]
                )

        # ML Prediction
        if msg_lower in ["ml", "ml prediction", "prediction", "model", "ai prediction"]:
            data = await self._fetch_api("/api/signal/BTC%2FUSD")
            if data:
                signal = data.get('signal', 'HOLD')
                confidence = data.get('confidence', 0)
                price = data.get('price', 0)

                emoji = "🟢" if signal == "BUY" else "🔴" if signal == "SELL" else "⚪"

                return TARSResponse(
                    message=f"""{emoji} **ML Model Prediction - BTC/USD**

**Signal:** {signal}
**Confidence:** {confidence:.1%}
**Current Price:** ${price:,.2f}

*Based on XGBoost model with 79 technical features*""",
                    suggestions=["Technical analysis", "Confluence score", "Place paper trade"]
                )

        # ICT Analysis (live)
        if msg_lower in ["ict analysis", "ict live", "fvg", "order blocks", "live ict"]:
            data = await self._fetch_api("/api/ict/BTC%2FUSD")
            if data:
                fvg_count = len(data.get('fvg', []))
                ob_count = len(data.get('order_blocks', []))
                mss = data.get('market_structure', {})
                bias = data.get('bias', 'Neutral')

                return TARSResponse(
                    message=f"""🎯 **Live ICT Analysis - BTC/USD**

**Bias:** {bias}
**Fair Value Gaps:** {fvg_count} detected
**Order Blocks:** {ob_count} detected
**Market Structure:** {mss.get('trend', 'Unknown')}

**Liquidity:**
• Buy-side: {data.get('liquidity', {}).get('buy_side', 'N/A')}
• Sell-side: {data.get('liquidity', {}).get('sell_side', 'N/A')}""",
                    suggestions=["Draw FVG zones", "Technical analysis", "Confluence score"]
                )

        # Market summary / Full analysis
        if msg_lower in ["market", "market analysis", "analysis", "summary", "market summary"]:
            # Fetch multiple endpoints
            ticker = await self._fetch_api("/api/ticker/BTC%2FUSD")
            signal = await self._fetch_api("/api/signal/BTC%2FUSD")
            confluence = await self._fetch_api("/api/ict-strategy/confluence/BTC%2FUSD")

            price = get_btc_price()
            change_24h = ticker.get('change_24h', 0) if ticker else 0
            volume = ticker.get('volume', 0) if ticker else 0
            ml_signal = signal.get('signal', 'HOLD') if signal else 'N/A'
            ml_conf = signal.get('confidence', 0) if signal else 0
            conf_score = confluence.get('total_score', 0) if confluence else 0
            conf_strength = confluence.get('strength', 'Unknown') if confluence else 'Unknown'

            trend_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➡️"

            return TARSResponse(
                message=f"""{trend_emoji} **Market Summary - BTC/USD**

**Price:** ${price:,.2f}
**24h Change:** {change_24h:+.2f}%
**Volume:** ${volume:,.0f}

**ML Signal:** {ml_signal} ({ml_conf:.0%} confidence)
**Confluence:** {conf_score}/30 ({conf_strength})

**Quick Assessment:** {'Bullish momentum' if change_24h > 2 else 'Bearish pressure' if change_24h < -2 else 'Consolidating'}""",
                suggestions=["Technical analysis", "ICT analysis", "Should I buy?"]
            )

        # Confirm/cancel pending actions - ONLY if there are pending actions
        # Otherwise let the AI handle contextual responses like "yes" to a question
        if msg_lower in ["yes", "confirm", "do it", "execute"] and self.pending_actions:
            action = self.pending_actions.pop(0)
            return await self._execute_action(action, context)

        if msg_lower in ["no", "cancel", "nevermind"] and self.pending_actions:
            self.pending_actions.clear()
            return TARSResponse(
                message="Action cancelled. What else can I help you with?",
                suggestions=["Market analysis", "Check prices", "Explain strategies"]
            )

        return None  # Let AI handle it (including contextual yes/no responses)

    def _build_context_string(self, context: Dict) -> str:
        """Build context string for AI prompt."""
        parts = []

        if context.get("current_price"):
            parts.append(f"Current price: ${context['current_price']:,.2f}")

        if context.get("symbol"):
            parts.append(f"Symbol: {context['symbol']}")

        if context.get("position"):
            pos = context["position"]
            parts.append(f"Open position: {pos['side']} {pos['size']} @ ${pos['entry']:,.2f}")

        if context.get("trading_mode"):
            parts.append(f"Trading mode: {context['trading_mode']}")

        if context.get("confluence_score"):
            parts.append(f"Current confluence: {context['confluence_score']}/30")

        return "\n".join(parts) if parts else "No additional context"

    async def _get_anthropic_response(self, user_message: str, context: str) -> str:
        """Get response from Anthropic Claude."""
        try:
            # Build messages with history (last 10 messages)
            messages = []
            for msg in self.conversation_history[-10:]:
                messages.append(msg)
            messages.append({"role": "user", "content": user_message})

            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1024,
                system=self.SYSTEM_PROMPT + f"\n\nCurrent Context:\n{context}",
                messages=messages
            )

            return response.content[0].text
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            return f"I encountered an error: {str(e)}. Let me try to help anyway - what do you need?"

    async def _get_gemini_response(self, user_message: str, context: str) -> str:
        """Get response from Google Gemini."""
        try:
            # Build conversation for Gemini
            chat = self.client.start_chat(history=[])

            # Send system prompt first
            full_prompt = f"""{self.SYSTEM_PROMPT}

Current Context:
{context}

User: {user_message}"""

            response = chat.send_message(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return f"I encountered an error: {str(e)}. Let me try to help anyway - what do you need?"

    async def _get_fallback_response(self, user_message: str, context: Dict) -> str:
        """Fallback responses when no AI provider is available."""
        msg_lower = user_message.lower()

        # Price queries
        if "price" in msg_lower or "btc" in msg_lower:
            btc = get_btc_price()
            eth = get_eth_price()
            return f"📊 Current prices:\n• BTC/USD: ${btc:,.2f}\n• ETH/USD: ${eth:,.2f}"

        # Strategy queries
        if "strateg" in msg_lower:
            return "I have several strategies available: ICT Smart Money, Scalping, ML Strategy, Trend Following, and Mean Reversion. Type 'strategies' to see the full list."

        # ICT queries
        if "ict" in msg_lower or "fvg" in msg_lower or "order block" in msg_lower:
            return "ICT (Inner Circle Trader) concepts include FVG, Order Blocks, OTE, and Liquidity. Type 'explain ict' for details."

        # Default
        return f"""I'm TARS, your trading assistant! 🤖

I can help you with:
• **Prices**: "BTC price", "ETH price"
• **Strategies**: "list strategies", "explain ICT"
• **Trading**: "buy 0.001 BTC" (paper mode)
• **Analysis**: "market analysis", "confluence"

What would you like to know?"""

    def _parse_response(self, response_text: str) -> tuple:
        """Parse AI response to extract message and actions."""
        actions = []
        message = response_text

        # Look for actions block
        if "```actions" in response_text:
            parts = response_text.split("```actions")
            message = parts[0].strip()

            if len(parts) > 1:
                action_block = parts[1].split("```")[0].strip()
                try:
                    actions = json.loads(action_block)
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse actions: {action_block}")

        return message, actions

    def _generate_suggestions(self, user_message: str, response: str) -> List[str]:
        """Generate contextual quick reply suggestions."""
        suggestions = []

        msg_lower = user_message.lower()
        resp_lower = response.lower()

        # Based on topic
        if "price" in msg_lower or "price" in resp_lower:
            suggestions.extend(["Market analysis", "Should I buy?", "Set price alert"])

        if "strategy" in msg_lower or "strategy" in resp_lower:
            suggestions.extend(["Compare strategies", "Start paper trading"])

        if "ict" in msg_lower or "ict" in resp_lower:
            suggestions.extend(["Draw FVG zones", "Find Order Blocks", "Show OTE levels"])

        if "trade" in msg_lower or "buy" in msg_lower or "sell" in msg_lower:
            suggestions.extend(["Check balance", "View open positions"])

        # Default suggestions if none generated
        if not suggestions:
            suggestions = ["BTC price", "List strategies", "Market analysis"]

        return suggestions[:4]  # Max 4 suggestions

    async def _execute_action(self, action: TARSAction, context: Dict) -> TARSResponse:
        """Execute a confirmed action."""
        if action.action_type == ActionType.PLACE_ORDER:
            params = action.parameters
            symbol = params.get("symbol", "BTC/USD")
            side = params.get("side", "buy")
            amount = params.get("amount", 0.001)
            is_paper = params.get("paper", True)

            mode = "PAPER" if is_paper else "LIVE"

            return TARSResponse(
                message=f"""✅ **Order Executed ({mode})**

• Symbol: {symbol}
• Side: {side.upper()}
• Amount: {amount}
• Type: Market

{"This is a simulated trade - no real money involved." if is_paper else "⚠️ REAL TRADE - This used actual funds!"}""",
                actions=[{
                    "action": "place_order",
                    "params": params,
                    "executed": True
                }],
                suggestions=["Check position", "Set stop loss", "Close position"]
            )

        return TARSResponse(
            message="Action executed.",
            suggestions=["What's next?", "Check status"]
        )

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()
        self.pending_actions.clear()
        logger.info("TARS conversation history cleared")


# Singleton instance
_tars_instance: Optional[TARS] = None


def get_tars() -> TARS:
    """Get or create TARS instance."""
    global _tars_instance
    if _tars_instance is None:
        _tars_instance = TARS()
    return _tars_instance


# Test
if __name__ == "__main__":
    import asyncio

    async def test():
        tars = TARS()

        print("=" * 60)
        print("TARS - Trading AI Response System")
        print("=" * 60)

        # Test basic queries
        queries = [
            "btc price",
            "list strategies",
            "explain ict",
            "What's the market looking like?"
        ]

        for query in queries:
            print(f"\nUser: {query}")
            response = await tars.process_message(query)
            print(f"TARS: {response.message[:200]}...")
            if response.suggestions:
                print(f"Suggestions: {response.suggestions}")

    asyncio.run(test())
