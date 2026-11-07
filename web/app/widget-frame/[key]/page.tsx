'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import {
  Send,
  Bot,
  User,
  X,
  Loader2,
  Calendar,
  CheckCircle2,
  AlertCircle,
  Clock,
} from 'lucide-react';

interface WidgetConfig {
  business_id: string;
  business_name: string;
  primary_color: string;
  greeting_message: string;
  ask_lead_capture: boolean;
  require_lead_name: boolean;
  allow_booking: boolean;
}

interface ChatMessage {
  id: string;
  speaker: 'agent' | 'visitor';
  text: string;
  latency_ms?: number;
  timestamp: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function WidgetFramePage() {
  const params = useParams();
  const publicKey = typeof params?.key === 'string' ? params.key : '';

  const [config, setConfig] = useState<WidgetConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);

  // Chat session state
  const [callId, setCallId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  // Lead capture state
  const [leadCaptured, setLeadCaptured] = useState(false);
  const [showLeadForm, setShowLeadForm] = useState(false);
  const [leadName, setLeadName] = useState('');
  const [leadEmail, setLeadEmail] = useState('');
  const [leadPhone, setLeadPhone] = useState('');
  const [submittingLead, setSubmittingLead] = useState(false);
  const [leadSuccessMsg, setLeadSuccessMsg] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  // Load public widget configuration
  useEffect(() => {
    if (!publicKey) return;

    async function loadConfig() {
      try {
        setLoading(true);
        setConfigError(null);
        const res = await fetch(`${API_BASE}/api/widget/config/${encodeURIComponent(publicKey)}`);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || 'Widget configuration not found');
        }
        const data: WidgetConfig = await res.json();
        setConfig(data);
        setMessages([
          {
            id: 'init-msg',
            speaker: 'agent',
            text: data.greeting_message || `Welcome to ${data.business_name}! How may I help you?`,
            timestamp: new Date().toISOString(),
          },
        ]);

        // Post theme color to parent window to sync bubble launcher color
        if (window.parent && window.parent !== window) {
          window.parent.postMessage(
            { type: 'CALLWISE_SET_THEME_COLOR', color: data.primary_color },
            '*'
          );
        }
      } catch (err: any) {
        setConfigError(err.message || 'Failed to initialize chat widget.');
      } finally {
        setLoading(false);
      }
    }

    loadConfig();
  }, [publicKey]);

  // Send message
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || sending || !publicKey) return;

    const visitorMsg = inputText.trim();
    setInputText('');
    setChatError(null);

    const tempId = `vis_${Date.now()}`;
    const newMsg: ChatMessage = {
      id: tempId,
      speaker: 'visitor',
      text: visitorMsg,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, newMsg]);
    setSending(true);

    try {
      const res = await fetch(`${API_BASE}/api/widget/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          public_key: publicKey,
          message: visitorMsg,
          call_id: callId || undefined,
          visitor_name: leadName || undefined,
          visitor_email: leadEmail || undefined,
          visitor_phone: leadPhone || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (res.status === 429) {
          throw new Error(errData.detail || 'Rate limit reached. Please wait a moment.');
        }
        throw new Error(errData.detail || 'Failed to send message.');
      }

      const data = await res.json();
      if (data.call_id && !callId) {
        setCallId(data.call_id);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `agt_${Date.now()}`,
          speaker: 'agent',
          text: data.reply,
          latency_ms: data.latency_ms,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err: any) {
      setChatError(err.message);
    } finally {
      setSending(false);
    }
  };

  // Submit Lead Capture
  const handleLeadSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!leadEmail && !leadPhone) || submittingLead || !publicKey) return;

    setSubmittingLead(true);
    try {
      const res = await fetch(`${API_BASE}/api/widget/lead`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          public_key: publicKey,
          call_id: callId || undefined,
          name: leadName || undefined,
          email: leadEmail || undefined,
          phone: leadPhone || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to submit details');
      }

      setLeadCaptured(true);
      setShowLeadForm(false);
      setLeadSuccessMsg('Thank you! Our staff has received your details.');
    } catch (err: any) {
      alert(err.message || 'Failed to save contact info.');
    } finally {
      setSubmittingLead(false);
    }
  };

  const handleClose = () => {
    if (window.parent && window.parent !== window) {
      window.parent.postMessage({ type: 'CALLWISE_CLOSE_WIDGET' }, '*');
    }
  };

  const primaryColor = config?.primary_color || '#2563EB';

  if (loading) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-slate-50 text-slate-400 space-y-2">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        <span className="text-xs">Connecting to receptionist...</span>
      </div>
    );
  }

  if (configError || !config) {
    return (
      <div className="h-screen flex flex-col items-center justify-center p-6 text-center bg-slate-50">
        <AlertCircle className="w-8 h-8 text-red-500 mb-2" />
        <h3 className="text-sm font-bold text-slate-800">Widget Unavailable</h3>
        <p className="text-xs text-slate-500 mt-1 max-w-xs">{configError}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-slate-50 overflow-hidden font-sans select-none">
      {/* Widget Header */}
      <div
        className="px-4 py-3 text-white flex items-center justify-between shadow-sm flex-shrink-0"
        style={{ backgroundColor: primaryColor }}
      >
        <div className="flex items-center space-x-2.5 min-w-0">
          <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center flex-shrink-0 backdrop-blur-sm">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div className="truncate">
            <h1 className="text-sm font-bold truncate leading-tight">{config.business_name}</h1>
            <div className="flex items-center space-x-1 mt-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-pulse" />
              <span className="text-[10px] text-white/90">AI Voice & Chat Receptionist</span>
            </div>
          </div>
        </div>

        <button
          onClick={handleClose}
          className="p-1 rounded-full text-white/80 hover:text-white hover:bg-white/10 transition"
          aria-label="Close widget"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 p-3.5 overflow-y-auto space-y-3 text-xs">
        {/* Optional Lead Capture Banner / Inline Form */}
        {config.ask_lead_capture && !leadCaptured && (
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs space-y-2">
            {!showLeadForm ? (
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-semibold text-slate-800 text-[11px]">
                    👋 Want us to follow up with you?
                  </p>
                  <p className="text-[10px] text-slate-500">
                    Leave your contact info for quick staff assistance.
                  </p>
                </div>
                <button
                  onClick={() => setShowLeadForm(true)}
                  className="px-2.5 py-1 text-[11px] font-semibold text-white rounded-md transition shadow-xs"
                  style={{ backgroundColor: primaryColor }}
                >
                  Contact Me
                </button>
              </div>
            ) : (
              <form onSubmit={handleLeadSubmit} className="space-y-2 pt-1">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-700 text-[11px]">Quick Contact Details</span>
                  <button
                    type="button"
                    onClick={() => setShowLeadForm(false)}
                    className="text-slate-400 hover:text-slate-600 text-xs"
                  >
                    ✕
                  </button>
                </div>
                <input
                  type="text"
                  placeholder="Your Name (Optional)"
                  value={leadName}
                  onChange={(e) => setLeadName(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <input
                  type="email"
                  placeholder="Email Address"
                  value={leadEmail}
                  onChange={(e) => setLeadEmail(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <input
                  type="tel"
                  placeholder="Phone Number (e.g. +15551234567)"
                  value={leadPhone}
                  onChange={(e) => setLeadPhone(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs border border-slate-200 rounded focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
                <div className="flex justify-end space-x-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setShowLeadForm(false)}
                    className="px-2 py-1 text-[11px] text-slate-500 hover:bg-slate-100 rounded"
                  >
                    Skip
                  </button>
                  <button
                    type="submit"
                    disabled={submittingLead || (!leadEmail && !leadPhone)}
                    className="px-3 py-1 text-[11px] font-semibold text-white rounded transition disabled:opacity-50"
                    style={{ backgroundColor: primaryColor }}
                  >
                    {submittingLead ? 'Saving...' : 'Submit Info'}
                  </button>
                </div>
              </form>
            )}
          </div>
        )}

        {leadSuccessMsg && (
          <div className="p-2 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-lg text-[11px] flex items-center">
            <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-emerald-600" />
            {leadSuccessMsg}
          </div>
        )}

        {/* Message Turns */}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex flex-col max-w-[85%] ${
              m.speaker === 'visitor' ? 'ml-auto items-end' : 'mr-auto items-start'
            }`}
          >
            <div
              className={`px-3.5 py-2 rounded-2xl leading-relaxed text-xs break-words shadow-2xs ${
                m.speaker === 'visitor'
                  ? 'text-white rounded-br-xs'
                  : 'bg-white text-slate-800 border border-slate-200/80 rounded-bl-xs'
              }`}
              style={m.speaker === 'visitor' ? { backgroundColor: primaryColor } : {}}
            >
              {m.text}
            </div>
            {m.latency_ms && (
              <span className="text-[9px] text-slate-400 mt-0.5 flex items-center px-1 font-mono">
                <Clock className="w-2.5 h-2.5 mr-1" />
                {Math.round(m.latency_ms)}ms
              </span>
            )}
          </div>
        ))}

        {sending && (
          <div className="flex items-center space-x-1.5 bg-white border border-slate-200 rounded-2xl px-3.5 py-2 w-16 shadow-2xs">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0.2s]" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce [animation-delay:0.4s]" />
          </div>
        )}

        {chatError && (
          <div className="p-2 bg-red-50 text-red-700 border border-red-200 rounded-lg text-[11px] flex items-center">
            <AlertCircle className="w-3.5 h-3.5 mr-1.5 flex-shrink-0" />
            {chatError}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Chat Input Bar */}
      <form
        onSubmit={handleSendMessage}
        className="p-2.5 bg-white border-t border-slate-200 flex items-center space-x-2 flex-shrink-0"
      >
        <input
          type="text"
          placeholder="Ask a question or request a booking..."
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          disabled={sending}
          maxLength={1000}
          className="flex-1 px-3 py-2 text-xs border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100"
        />
        <button
          type="submit"
          disabled={sending || !inputText.trim()}
          className="p-2 text-white rounded-xl transition disabled:opacity-40 hover:opacity-90 flex-shrink-0"
          style={{ backgroundColor: primaryColor }}
          aria-label="Send message"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}
