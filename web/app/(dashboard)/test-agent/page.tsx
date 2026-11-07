'use client';

import React, { useState, useRef, useEffect } from 'react';
import {
  Bot,
  User,
  Send,
  Loader2,
  Sparkles,
  PhoneCall,
  Volume2,
  VolumeX,
  RotateCcw,
  Clock,
  ShieldAlert,
  Info,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { TestAgentResponse } from '@/types/api';
import { useAuth } from '@/contexts/auth-context';

interface ChatMessage {
  id: string;
  sender: 'user' | 'agent';
  text: string;
  timestamp: Date;
  latency_ms?: number;
}

export default function TestAgentPage() {
  const { currentBusiness } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [callId, setCallId] = useState<string | null>(null);
  const [soundEnabled, setSoundEnabled] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize with agent greeting
  useEffect(() => {
    if (messages.length === 0) {
      const greetingText =
        currentBusiness?.greeting ||
        "Hello! Thanks for calling. How can I help you today?";
      setMessages([
        {
          id: 'initial-greeting',
          sender: 'agent',
          text: greetingText,
          timestamp: new Date(),
        },
      ]);
    }
  }, [currentBusiness]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const speakText = (text: string) => {
    if (!soundEnabled || typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    try {
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.pitch = 1.0;
      window.speechSynthesis.speak(utterance);
    } catch {
      // SpeechSynthesis may be blocked or unsupported in non-standard browsers
    }
  };

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsgText = input.trim();
    setInput('');

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: userMsgText,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const res = await apiClient<TestAgentResponse>('/api/onboarding/test-agent', {
        method: 'POST',
        body: JSON.stringify({
          message: userMsgText,
          call_id: callId,
        }),
      });

      if (!callId && res.call_id) {
        setCallId(res.call_id);
      }

      const agentMessage: ChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: res.reply,
        timestamp: new Date(),
        latency_ms: res.latency_ms,
      };

      setMessages((prev) => [...prev, agentMessage]);
      speakText(res.reply);
    } catch (err: any) {
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'agent',
        text: `Error connecting to receptionist agent: ${err?.message || 'Request failed'}`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  const handleResetSession = () => {
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setCallId(null);
    setMessages([
      {
        id: `initial-greeting-${Date.now()}`,
        sender: 'agent',
        text:
          currentBusiness?.greeting ||
          "Hello! Thanks for calling. How can I help you today?",
        timestamp: new Date(),
      },
    ]);
  };

  return (
    <div className="h-[calc(100vh-8rem)] flex flex-col space-y-4 max-w-5xl mx-auto">
      {/* Top Banner & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
              <Bot className="w-5 h-5 text-blue-600" />
              Interactive Test Agent Console
            </h2>
            <span className="px-2 py-0.5 text-[11px] font-semibold rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200">
              Live Test Sandbox
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Simulate caller inquiries in real-time. The agent uses your current knowledge base, services, and operating hours.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* TTS Audio toggle */}
          <button
            type="button"
            onClick={() => {
              if (soundEnabled && typeof window !== 'undefined' && 'speechSynthesis' in window) {
                window.speechSynthesis.cancel();
              }
              setSoundEnabled(!soundEnabled);
            }}
            className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
              soundEnabled
                ? 'bg-blue-50 text-blue-700 border-blue-200'
                : 'bg-slate-50 text-slate-600 border-slate-200 hover:bg-slate-100'
            }`}
            title="Read responses aloud with Web Speech API"
          >
            {soundEnabled ? (
              <>
                <Volume2 className="w-3.5 h-3.5 text-blue-600 animate-pulse" />
                Speech Audio ON
              </>
            ) : (
              <>
                <VolumeX className="w-3.5 h-3.5 text-slate-400" />
                Speech Audio OFF
              </>
            )}
          </button>

          {/* Reset Conversation */}
          <button
            type="button"
            onClick={handleResetSession}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 transition-colors"
            title="Clear history and start fresh call session"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Call
          </button>
        </div>
      </div>

      {/* Main Conversation Window */}
      <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-xs flex flex-col overflow-hidden">
        {/* Messages Feed */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          <div className="flex justify-center">
            <span className="text-[11px] text-slate-400 bg-slate-100 px-3 py-1 rounded-full flex items-center gap-1.5">
              <PhoneCall className="w-3 h-3 text-slate-400" />
              Call session started {callId ? `(ID: ${callId.slice(0, 8)})` : ''}
            </span>
          </div>

          {messages.map((m) => {
            const isAgent = m.sender === 'agent';
            return (
              <div
                key={m.id}
                className={`flex items-start gap-3 ${isAgent ? '' : 'flex-row-reverse'}`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
                    isAgent
                      ? 'bg-blue-600 text-white shadow-xs'
                      : 'bg-slate-700 text-white'
                  }`}
                >
                  {isAgent ? <Bot className="w-4 h-4" /> : <User className="w-4 h-4" />}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-2xs ${
                    isAgent
                      ? 'bg-slate-50 border border-slate-200/80 text-slate-800 rounded-tl-xs'
                      : 'bg-blue-600 text-white rounded-tr-xs'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.text}</p>
                  <div
                    className={`mt-1.5 flex items-center gap-2 text-[10px] ${
                      isAgent ? 'text-slate-400' : 'text-blue-200 justify-end'
                    }`}
                  >
                    <span>
                      {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {m.latency_ms !== undefined && (
                      <span className="inline-flex items-center gap-0.5 bg-blue-50 text-blue-700 px-1.5 py-0.2 rounded border border-blue-100">
                        <Clock className="w-2.5 h-2.5" />
                        {m.latency_ms} ms
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {loading && (
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="bg-slate-50 border border-slate-200/80 rounded-2xl rounded-tl-xs px-4 py-3 text-sm text-slate-500 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                <span>Receptionist is thinking...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-3 sm:p-4 border-t border-slate-100 bg-slate-50/50">
          <form onSubmit={handleSend} className="flex items-center gap-2">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type caller inquiry (e.g., 'What are your hours?' or 'Can I book an appointment?')..."
              disabled={loading}
              className="flex-1 px-4 py-2.5 bg-white border border-slate-200 rounded-xl text-sm focus:outline-hidden focus:ring-2 focus:ring-blue-600 focus:border-transparent transition-all placeholder:text-slate-400 disabled:bg-slate-100"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-xl font-medium text-sm transition-colors shadow-xs flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">Send</span>
            </button>
          </form>
          <div className="flex items-center justify-between text-[11px] text-slate-400 mt-2 px-1">
            <span className="flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-amber-500" />
              Tip: Test booking flow, knowledge search, and transfer queries.
            </span>
            <span>Press Enter to send</span>
          </div>
        </div>
      </div>
    </div>
  );
}
