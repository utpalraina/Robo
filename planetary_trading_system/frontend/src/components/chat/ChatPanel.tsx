'use client';

import { useState, useRef, useEffect } from 'react';

interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export default function ChatPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = input.trim();
    setInput('');
    setError(null);
    setLoading(true);

    const newMessages = [...messages, { role: 'user' as const, content: userMessage }];
    setMessages(newMessages);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          history: messages
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Failed to get response');
      }

      setMessages([...newMessages, { role: 'assistant' as const, content: data.response }]);
    } catch (err: any) {
      setError(err.message);
      setMessages(messages); // Revert on error
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
  };

  if (!isOpen) {
    return (
      <button
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 w-14 h-14 bg-gradient-to-r from-purple-600 to-blue-600 rounded-full shadow-lg flex items-center justify-center text-white text-2xl hover:scale-110 transition-transform z-50"
        title="Ask Claude about Gann/Jenkins methodology"
      >
        💬
      </button>
    );
  }

  return (
    <div
      className={`fixed right-6 shadow-2xl rounded-lg overflow-hidden z-50 transition-all duration-300 ${
        isMinimized
          ? 'bottom-6 w-80 h-12'
          : 'bottom-6 w-96 h-[32rem]'
      }`}
      style={{
        background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)',
        border: '1px solid rgba(139, 92, 246, 0.3)'
      }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer"
        style={{ background: 'linear-gradient(90deg, #7c3aed 0%, #3b82f6 100%)' }}
        onClick={() => setIsMinimized(!isMinimized)}
      >
        <div className="flex items-center gap-2 text-white">
          <span className="text-xl">🤖</span>
          <span className="font-semibold">Ask Claude</span>
          <span className="text-xs opacity-75">Gann/Jenkins Expert</span>
        </div>
        <div className="flex items-center gap-2">
          {!isMinimized && (
            <button
              onClick={(e) => { e.stopPropagation(); clearChat(); }}
              className="text-white/70 hover:text-white text-sm px-2"
              title="Clear chat"
            >
              🗑️
            </button>
          )}
          <button
            onClick={(e) => { e.stopPropagation(); setIsMinimized(!isMinimized); }}
            className="text-white/70 hover:text-white"
          >
            {isMinimized ? '▲' : '▼'}
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); setIsOpen(false); }}
            className="text-white/70 hover:text-white ml-1"
          >
            ✕
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* Messages */}
          <div className="h-80 overflow-y-auto p-4 space-y-3" style={{ background: 'rgba(0,0,0,0.2)' }}>
            {messages.length === 0 && (
              <div className="text-center text-gray-400 py-6">
                <div className="text-3xl mb-2">💬</div>
                <p className="text-sm mb-3">Ask about Gann/Jenkins methodology</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {['Zero Aries?', 'Price → Degree?', 'Confluence?'].map((q) => (
                    <button
                      key={q}
                      onClick={() => setInput(q)}
                      className="px-2 py-1 text-xs bg-purple-600/30 hover:bg-purple-600/50 rounded-full border border-purple-500/30"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-3 rounded-lg text-sm ${
                  msg.role === 'user'
                    ? 'bg-purple-600 text-white'
                    : 'bg-gray-700/50 text-gray-100 border border-gray-600/50'
                }`}>
                  {msg.role === 'assistant' && (
                    <div className="text-xs text-purple-400 mb-1">🤖 Claude</div>
                  )}
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              </div>
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-700/50 border border-gray-600/50 p-3 rounded-lg">
                  <div className="text-xs text-purple-400 mb-1">🤖 Claude</div>
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                    <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                    <div className="w-2 h-2 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Error */}
          {error && (
            <div className="px-4 py-2 bg-red-500/20 text-red-400 text-xs">
              {error}
            </div>
          )}

          {/* Input */}
          <div className="p-3 border-t border-gray-700/50">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && sendMessage()}
                placeholder="Ask about trading methodology..."
                disabled={loading}
                className="flex-1 px-3 py-2 bg-gray-800/50 border border-gray-600/50 rounded-lg text-white text-sm focus:outline-none focus:border-purple-500 disabled:opacity-50 placeholder-gray-500"
              />
              <button
                onClick={sendMessage}
                disabled={!input.trim() || loading}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg text-white text-sm font-medium transition-colors"
              >
                {loading ? '...' : 'Send'}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
