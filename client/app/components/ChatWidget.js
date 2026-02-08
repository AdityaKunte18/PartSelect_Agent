'use client';
import React, { useState, useRef, useEffect } from 'react';
import { MessageSquare, X, Send } from 'lucide-react';

export default function ChatWidget() {
  
  const [isOpen, setIsOpen] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef(null);
  const [sessionId] = useState(() => {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return `web_${Date.now()}_${Math.random().toString(16).slice(2)}`;
  });
  const [userId] = useState(() => {
    if (typeof window === 'undefined') return 'web_user';
    const existing = window.localStorage.getItem('ps_user_id');
    if (existing) return existing;
    const freshId =
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID()
        : `user_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    window.localStorage.setItem('ps_user_id', freshId);
    return freshId;
  });
  
  const [messages, setMessages] = useState([
    { 
      id: 1, 
      sender: 'agent', 
      text: 'Welcome to PartSelect! I can help you verify part fittings or assist with your order. Happy to help!',
      ui: null,
    }
  ]);

  const [inputText, setInputText] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isOpen]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const extractTextFromEvent = (data) => {
    if (!data) return null;
    if (data === '[DONE]') return { done: true };

    let parsed;
    try {
      parsed = JSON.parse(data);
    } catch {
      return { text: data, mode: 'append' };
    }

    const isPartial = parsed.partial === true;

    const partsToText = (parts) => {
      if (!Array.isArray(parts)) return '';
      return parts
        .map((p) => (typeof p === 'string' ? p : p?.text))
        .filter(Boolean)
        .join('');
    };

    if (parsed.error) {
      return { text: parsed.error, mode: 'set', isError: true };
    }
    if (parsed.errorMessage) {
      return { text: parsed.errorMessage, mode: 'set', isError: true };
    }

    if (parsed.delta) {
      if (typeof parsed.delta === 'string') return { text: parsed.delta, mode: 'append' };
      if (typeof parsed.delta.text === 'string') return { text: parsed.delta.text, mode: 'append' };
      const deltaParts = partsToText(parsed.delta.parts);
      if (deltaParts) return { text: deltaParts, mode: 'append' };
    }

    if (parsed.message) {
      if (typeof parsed.message.content === 'string') return { text: parsed.message.content, mode: isPartial ? 'append' : 'set' };
      const messageParts = partsToText(parsed.message.parts);
      if (messageParts) return { text: messageParts, mode: isPartial ? 'append' : 'set' };
    }

    if (parsed.content) {
      if (typeof parsed.content === 'string') return { text: parsed.content, mode: isPartial ? 'append' : 'set' };
      const contentParts = partsToText(parsed.content.parts);
      if (contentParts) return { text: contentParts, mode: isPartial ? 'append' : 'set' };
    }

    if (typeof parsed.text === 'string') return { text: parsed.text, mode: isPartial ? 'append' : 'set' };
    const rootParts = partsToText(parsed.parts);
    if (rootParts) return { text: rootParts, mode: isPartial ? 'append' : 'set' };

    return null;
  };

  const formatCents = (cents) => {
    if (typeof cents !== 'number') return null;
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(cents / 100);
  };

  const renderUi = (ui) => {
    if (!ui || typeof ui !== 'object') return null;

    if (ui.type === 'product_list') {
      const items = Array.isArray(ui.items) ? ui.items : [];
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">{ui.title || 'Parts'}</div>
          <div className="mt-1 space-y-1">
            {items.slice(0, 10).map((item) => (
              <div key={item.part_number} className="flex justify-between gap-2">
                <span className="font-medium">{item.part_number}</span>
                <span className="flex-1 text-right">{item.name}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (ui.type === 'product_detail') {
      const p = ui.product || {};
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">Part Details</div>
          <div className="mt-1">
            <div><span className="font-medium">Part:</span> {p.part_number}</div>
            <div><span className="font-medium">Name:</span> {p.name}</div>
            <div><span className="font-medium">Category:</span> {p.category}</div>
          </div>
        </div>
      );
    }

    if (ui.type === 'compatibility') {
      const compatible = !!ui.compatible;
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">Compatibility</div>
          <div className="mt-1">
            <div><span className="font-medium">Part:</span> {ui.part_number}</div>
            <div><span className="font-medium">Model:</span> {ui.model_number}</div>
            <div className={`mt-1 inline-flex rounded px-2 py-0.5 text-[11px] ${compatible ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
              {compatible ? 'Compatible' : 'Not compatible'}
            </div>
          </div>
        </div>
      );
    }

    if (ui.type === 'cart') {
      const items = Array.isArray(ui.items) ? ui.items : [];
      const totalQty = items.reduce((sum, it) => sum + (Number(it.quantity) || 0), 0);
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">Cart Summary</div>
          <div className="mt-1">Total items: {totalQty}</div>
          <div className="mt-1 space-y-1">
            {items.map((item) => (
              <div key={item.part_number} className="flex justify-between gap-2">
                <span className="font-medium">{item.part_number}</span>
                <span className="flex-1 text-right">Qty {item.quantity}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (ui.type === 'installation_guides') {
      const guides = Array.isArray(ui.guides) ? ui.guides : [];
      const first = guides[0];
      if (!first) return null;
      const steps = Array.isArray(first.steps) ? first.steps : [];
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">{first.title}</div>
          <div className="mt-1 space-y-1">
            {steps.slice(0, 4).map((step, idx) => (
              <div key={`${idx}-${String(step).slice(0, 8)}`}>
                {idx + 1}. {step}
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (ui.type === 'shipping') {
      const options = Array.isArray(ui.options) ? ui.options : [];
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">Shipping Options</div>
          <div className="mt-1 space-y-1">
            {options.map((opt) => (
              <div key={opt.service} className="flex justify-between gap-2">
                <span className="font-medium">{opt.service}</span>
                <span>{opt.eta_days} days</span>
                <span>{formatCents(opt.cost_cents) || '—'}</span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (ui.type === 'checkout') {
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">Checkout Ready</div>
          {ui.checkout_url ? (
            <a href={ui.checkout_url} className="mt-1 inline-block text-blue-600 underline" target="_blank" rel="noreferrer">
              Open checkout
            </a>
          ) : (
            <div className="mt-1">Checkout link unavailable.</div>
          )}
        </div>
      );
    }

    if (ui.type === 'order_history') {
      const orders = Array.isArray(ui.orders) ? ui.orders : [];
      return (
        <div className="mt-2 rounded-md border border-gray-200 bg-white p-2 text-xs text-gray-700">
          <div className="font-semibold">Order History</div>
          <div className="mt-1 space-y-1">
            {orders.slice(0, 5).map((order) => (
              <div key={order.id} className="rounded border border-gray-100 p-1">
                <div>Order {String(order.id).slice(0, 8)} • {order.status}</div>
                {(order.items || []).slice(0, 3).map((item) => (
                  <div key={`${order.id}-${item.part_number}`}>
                    {item.part_number} × {item.quantity}
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      );
    }

    return null;
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || isStreaming) return;

    // Add User Message
    const text = inputText.trim();
    const baseId = Date.now();
    const userMsg = { id: baseId, sender: 'user', text };
    const agentMsgId = baseId + 1;
    const agentMsg = { id: agentMsgId, sender: 'agent', text: 'Thinking...', ui: null };
    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setMessages((prev) => [...prev, agentMsg]);

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    let hasReceivedTokens = false;

    let ignoreStreamedText = false;

    const updateAgentMessage = (deltaText, mode = 'append') => {
      if (ignoreStreamedText && mode === 'append') return;
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== agentMsgId) return m;
          if (mode === 'set') return { ...m, text: deltaText };
          return { ...m, text: (m.text || '') + deltaText };
        })
      );
    };

    const updateAgentUi = (uiPayload) => {
      if (!uiPayload) return;
      if (uiPayload.replace_text) {
        ignoreStreamedText = true;
        updateAgentMessage(uiPayload.replace_text, 'set');
      }
      setMessages((prev) =>
        prev.map((m) => (m.id === agentMsgId ? { ...m, ui: uiPayload } : m))
      );
    };

    try {
      const res = await fetch('http://127.0.0.1:8001/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          user_id: userId,
          session_id: sessionId,
          reset: false,
        }),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        throw new Error(`Streaming request failed (${res.status})`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let pendingEventType = null;

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const rawLine of lines) {
          const line = rawLine.trim();
          if (!line) {
            pendingEventType = null;
            continue;
          }

          if (line.startsWith('event:')) {
            pendingEventType = line.slice(6).trim() || null;
            continue;
          }

          if (!line.startsWith('data:')) continue;
          const data = line.slice(5).trim();
          if (!data) continue;

          if (pendingEventType === 'error') {
            updateAgentMessage(data, 'set');
            hasReceivedTokens = true;
            continue;
          }

          let parsedJson = null;
          try {
            parsedJson = JSON.parse(data);
          } catch {
            parsedJson = null;
          }
          if (parsedJson?.actions?.stateDelta?.ui) {
            updateAgentUi(parsedJson.actions.stateDelta.ui);
          }

          const parsed = extractTextFromEvent(data);
          if (!parsed || parsed.done) continue;
          if (!parsed.text) continue;

          let mode = parsed.mode || 'append';
          if (!hasReceivedTokens && parsed.text) {
            mode = 'set';
          }

          updateAgentMessage(parsed.text, mode);
          hasReceivedTokens = true;
        }
      }
    } catch (err) {
      updateAgentMessage('Sorry, I ran into a connection problem. Please try again.', 'set');
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
      if (!hasReceivedTokens) {
        updateAgentMessage('Sorry, I could not generate a response.', 'set');
      }
    }
  };

  return (
    <div className="fixed bottom-17 right-2 z-50 flex flex-col items-end font-sans">
      
      {isOpen && (
        <div className="bg-white rounded-t-lg rounded-b-none shadow-2xl w-80 sm:w-96 mb-4 flex flex-col overflow-hidden border border-gray-200 h-[500px]">
          
          <div className="bg-[#347878] text-white p-4 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-300 rounded-full animate-pulse"></div>
              <h3 className="font-bold text-lg">PartSelect Agent</h3>
            </div>
            <button onClick={() => setIsOpen(false)} className="hover:bg-white/20 p-1 rounded">
              <X size={18} />
            </button>
          </div>

          
          <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
            {messages.map((msg) => (
              <div 
                key={msg.id} 
                className={`mb-4 flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div 
                  className={`max-w-[80%] rounded-lg p-3 text-sm shadow-sm ${
                    msg.sender === 'user' 
                      ? 'bg-[#347878] text-white rounded-br-none' 
                      : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
                  }`}
                >
                  {msg.text}
                  {msg.sender === 'agent' && msg.ui ? renderUi(msg.ui) : null}
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <form onSubmit={handleSend} className="p-3 bg-white border-t border-gray-200 flex gap-2">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Enter Model # or Order ID..."
              className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:border-[#347878]"
              disabled={isStreaming}
            />
            
            <button 
              type="submit" 
              className="bg-[#FFCC00] text-black p-2 rounded-md hover:bg-yellow-400 transition-colors font-bold disabled:opacity-60 disabled:cursor-not-allowed"
              disabled={isStreaming}
            >
              <Send size={18} />
            </button>
          </form>
          
          <div className="bg-gray-100 p-2 text-center text-[10px] text-gray-500">
            Automated Assistant
          </div>
        </div>
      )}

      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`${isOpen ? 'bg-gray-600 text-white' : 'bg-[#FFCC00] text-black'} shadow-xl rounded-full p-4 font-bold transition-transform hover:scale-105 flex items-center gap-2 border-2 border-white`}
      >
        {isOpen ? <X size={24} /> : <MessageSquare size={24} />}
        {!isOpen && <span className="pr-1">Chat Help</span>}
      </button>
    </div>
);
}
