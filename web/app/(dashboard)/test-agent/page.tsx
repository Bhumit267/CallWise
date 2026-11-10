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
    <div className="h-[calc(100vh-8.5rem)] flex flex-col space-y-4 max-w-5xl mx-auto">
      {/* Top Banner & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 sm:p-5 rounded-2xl brutal-border-3 brutal-shadow">
        <div>
          <div className="flex items-center gap-2 mb-0.5">
            <h2 className="text-xl font-black uppercase tracking-tight text-black flex items-center gap-2">
              <Bot className="w-6 h-6 text-black" />
              Interactive Test Agent
            </h2>
            <span className="px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wider rounded bg-[#a3e635] text-black brutal-border brutal-shadow-xs">
              Live Sandbox
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Simulate caller inquiries in real-time using current knowledge base, catalog, and operating hours.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          {/* TTS Audio toggle */}
          <button
            type="button"
            onClick={() => {
              if (soundEnabled && typeof window !== 'undefined' && 'speechSynthesis' in window) {
                window.speechSynthesis.cancel();
              }
              setSoundEnabled(!soundEnabled);
            }}
            className={`inline-flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-black uppercase tracking-wider brutal-border transition-all ${
              soundEnabled
                ? 'bg-[#dbeafe] text-blue-950 brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
            }`}
            title="Read responses aloud with Web Speech API"
          >
            {soundEnabled ? (
              <>
                <Volume2 className="w-4 h-4 text-blue-700 animate-pulse" />
                Speech Audio ON
              </>
            ) : (
              <>
                <VolumeX className="w-4 h-4 text-neutral-500" />
                Speech Audio OFF
              </>
            )}
          </button>

          {/* Reset Conversation */}
          <button
            type="button"
            onClick={handleResetSession}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-black uppercase tracking-wider brutal-border bg-white hover:bg-neutral-100 text-black brutal-shadow-xs"
            title="Clear history and start fresh call session"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Call
          </button>
        </div>
      </div>

      {/* Main Conversation Window */}
      <div className="flex-1 bg-white rounded-2xl brutal-border-3 brutal-shadow-lg flex flex-col overflow-hidden">
        {/* Messages Feed */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
          <div className="flex justify-center">
            <span className="text-[10px] font-mono font-bold text-black bg-[#fef9c3] px-3 py-1 rounded-lg brutal-border brutal-shadow-xs flex items-center gap-1.5">
              <PhoneCall className="w-3 h-3 text-black" />
              Call session started {callId ? `(ID: ${callId.slice(0, 8)})` : ''}
            </span>
          </div>

          {messages.map((m) => {
            const isAgent = m.sender === 'agent';
            return (
              <div
                key={m.id}
                className={`flex items-start gap-3.5 ${isAgent ? '' : 'flex-row-reverse'}`}
              >
                {/* Avatar */}
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 brutal-border brutal-shadow-xs ${
                    isAgent
                      ? 'bg-[#ffe600] text-black'
                      : 'bg-blue-600 text-white'
                  }`}
                >
                  {isAgent ? <Bot className="w-5 h-5 stroke-[2.5]" /> : <User className="w-5 h-5 stroke-[2.5]" />}
                </div>

                {/* Message Bubble */}
                <div
                  className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed brutal-border brutal-shadow-xs ${
                    isAgent
                      ? 'bg-[#fbfaf6] text-black rounded-tl-xs'
                      : 'bg-blue-600 text-white rounded-tr-xs'
                  }`}
                >
                  <p className="whitespace-pre-wrap font-bold">{m.text}</p>
                  <div
                    className={`mt-2 flex items-center gap-2 text-[10px] font-mono ${
                      isAgent ? 'text-neutral-500' : 'text-blue-100 justify-end'
                    }`}
                  >
                    <span className="font-bold">
                      {m.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                    {m.latency_ms !== undefined && (
                      <span className="inline-flex items-center gap-0.5 bg-[#dcfce7] text-emerald-950 px-1.5 py-0.5 rounded brutal-border font-bold">
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
            <div className="flex items-start gap-3.5">
              <div className="w-9 h-9 rounded-xl bg-[#ffe600] text-black flex items-center justify-center shrink-0 brutal-border brutal-shadow-xs">
                <Bot className="w-5 h-5 stroke-[2.5]" />
              </div>
              <div className="bg-[#fbfaf6] brutal-border rounded-2xl rounded-tl-xs px-4 py-3 text-sm font-bold text-black flex items-center gap-2 brutal-shadow-xs">
                <Loader2 className="w-4 h-4 animate-spin text-black" />
                <span>Receptionist is thinking...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t-2 border-black bg-neutral-50">
          <form onSubmit={handleSend} className="flex items-center gap-2.5">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type caller inquiry (e.g. 'What are your hours?' or 'Can I schedule a cleaning?')..."
              disabled={loading}
              className="brutal-input flex-1 text-sm font-bold"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="px-5 py-3 bg-black hover:bg-neutral-800 disabled:opacity-40 text-white rounded-xl font-black text-xs uppercase tracking-wider brutal-border brutal-shadow-xs brutal-shadow-hover flex items-center gap-2"
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
              <span className="hidden sm:inline">Send</span>
            </button>
          </form>
          <div className="flex items-center justify-between text-[11px] font-mono font-bold text-neutral-500 mt-2 px-1">
            <span className="flex items-center gap-1 text-neutral-700">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              Instant simulated streaming dialog
            </span>
            <span>Press Enter to send</span>
          </div>
        </div>
      </div>
    </div>
  );
}
