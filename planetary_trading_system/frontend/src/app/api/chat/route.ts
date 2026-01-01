import { NextRequest, NextResponse } from 'next/server';
import Anthropic from '@anthropic-ai/sdk';

const SYSTEM_PROMPT = `You are an expert assistant specializing in Gann and Jenkins astrological trading methodology. You help traders understand:

1. **Zero Aries Concept**: March 20 (Vernal Equinox) = 0°, Sun moves ~1°/day through the zodiac
2. **Price-to-Degree Conversion**: Converting prices to zodiac degrees using asset-specific harmonics
   - Gold: ÷36 ($10 increments)
   - Bitcoin: ÷100
   - SPY: ÷1 (direct)
   - Formula: degree = (price / divisor) % 360
3. **Anniversary Dates**: The calendar date when Sun transits a price's degree (March 20 + degree days)
4. **Sensitivity Windows**: Major turns tend to occur near anniversary dates, but require additional confirmation
5. **Confluence Factors**: Sun-Price alignment, lunar phases, Mercury retrograde, eclipses, cardinal ingresses
6. **Seasonal Dates**: Every 15° from March 20 (equinoxes, solstices, fixed cross points)

Key principles from W.D. Gann and Michael Jenkins:
- "When price and time are squared, a change in trend is likely"
- Price levels have zodiac equivalents that become sensitive when Sun transits that degree
- Major highs/lows often occur on or near seasonal dates
- Multiple confluence factors = higher probability trade

Be concise but thorough. Use examples when helpful. Focus on practical trading applications.`;

export async function POST(request: NextRequest) {
  try {
    const { message, history } = await request.json();

    const apiKey = process.env.ANTHROPIC_API_KEY;
    if (!apiKey) {
      return NextResponse.json(
        { error: 'ANTHROPIC_API_KEY not configured. Add it to your .env.local file.' },
        { status: 500 }
      );
    }

    const client = new Anthropic({ apiKey });

    // Build messages array from history
    const messages: { role: 'user' | 'assistant'; content: string }[] = [];

    if (history && Array.isArray(history)) {
      for (const msg of history) {
        messages.push({
          role: msg.role as 'user' | 'assistant',
          content: msg.content
        });
      }
    }

    // Add the new user message
    messages.push({ role: 'user', content: message });

    const response = await client.messages.create({
      model: 'claude-sonnet-4-20250514',
      max_tokens: 1024,
      system: SYSTEM_PROMPT,
      messages: messages
    });

    const assistantMessage = response.content[0].type === 'text'
      ? response.content[0].text
      : '';

    return NextResponse.json({ response: assistantMessage });
  } catch (error: any) {
    console.error('Claude API error:', error);
    return NextResponse.json(
      { error: error.message || 'Failed to get response from Claude' },
      { status: 500 }
    );
  }
}
