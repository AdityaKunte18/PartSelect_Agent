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
      text: 'Welcome to PartSelect! I can help you verify part fittings or assist with your order. Happy to help!' 
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

  const handleSend = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || isStreaming) return;

    // Add User Message
    const text = inputText.trim();
    const baseId = Date.now();
    const userMsg = { id: baseId, sender: 'user', text };
    const agentMsgId = baseId + 1;
    const agentMsg = { id: agentMsgId, sender: 'agent', text: 'Thinking...' };
    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setMessages((prev) => [...prev, agentMsg]);

    const controller = new AbortController();
    abortRef.current = controller;
    setIsStreaming(true);

    let hasReceivedTokens = false;

    const updateAgentMessage = (deltaText, mode = 'append') => {
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== agentMsgId) return m;
          if (mode === 'set') return { ...m, text: deltaText };
          return { ...m, text: (m.text || '') + deltaText };
        })
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
