'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { WidgetSettingsData, WidgetSettingsUpdate } from '@/types/api';
import {
  MessageSquareCode,
  Copy,
  Check,
  RefreshCw,
  Send,
  Shield,
  Palette,
  Globe,
  Sliders,
  Sparkles,
  Bot,
  User,
  Loader2,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const COLOR_PRESETS = [
  { name: 'Classic Blue', hex: '#2563EB' },
  { name: 'Cyber Yellow', hex: '#FFE600' },
  { name: 'Neo Mint', hex: '#10B981' },
  { name: 'Royal Purple', hex: '#A855F7' },
  { name: 'Coral Red', hex: '#FF5A5A' },
  { name: 'Pitch Black', hex: '#0A0A0A' },
];

export default function WidgetPage() {
  const [settings, setSettings] = useState<WidgetSettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [copied, setCopied] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  // Live preview message state
  const [previewMessages, setPreviewMessages] = useState<
    { speaker: 'bot' | 'visitor'; text: string }[]
  >([]);
  const [visitorInput, setVisitorInput] = useState('');

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient<WidgetSettingsData>('/api/widget/settings');
      setSettings(res);
      setPreviewMessages([
        {
          speaker: 'bot',
          text: res.greeting_message || 'Hi! How can our team help you today?',
        },
      ]);
    } catch (err: any) {
      setError(err.message || 'Failed to load widget configuration');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setSaveSuccess(false);
    setError(null);

    const payload: WidgetSettingsUpdate = {
      is_enabled: settings.is_enabled,
      allowed_origins: settings.allowed_origins,
      primary_color: settings.primary_color,
      greeting_message: settings.greeting_message,
      ask_lead_capture: settings.ask_lead_capture,
      require_lead_name: settings.require_lead_name,
      allow_booking: settings.allow_booking,
      rate_limit_rpm: settings.rate_limit_rpm,
      max_turns_per_session: settings.max_turns_per_session,
    };

    try {
      const updated = await apiClient<WidgetSettingsData>('/api/widget/settings', {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
      setSettings(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to save widget settings');
    } finally {
      setSaving(false);
    }
  };

  const handleRegenerateKey = async () => {
    if (
      !confirm(
        'Regenerating the public key will immediately break any website embedding the current snippet. Do you want to proceed?'
      )
    ) {
      return;
    }
    setRegenerating(true);
    try {
      const res = await apiClient<WidgetSettingsData>('/api/widget/settings/regenerate-key', {
        method: 'POST',
      });
      setSettings(res);
      alert('Public key regenerated successfully! Make sure to update the snippet on your website.');
    } catch (err: any) {
      alert(err.message || 'Failed to regenerate public key');
    } finally {
      setRegenerating(false);
    }
  };

  const snippetCode = settings
    ? `<!-- Callwise AI Receptionist Chat Widget -->
<script
  src="${typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000'}/widget.js"
  data-callwise-key="${settings.public_key}"
  defer
></script>`
    : '';

  const copySnippet = () => {
    navigator.clipboard.writeText(snippetCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const sendPreviewMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!visitorInput.trim()) return;
    const msg = visitorInput.trim();
    setPreviewMessages((prev) => [
      ...prev,
      { speaker: 'visitor', text: msg },
      {
        speaker: 'bot',
        text: `Thanks for asking about that! In live mode, I search ${settings?.greeting_message.includes('Spa') ? 'Serenity Spa' : 'our official'} records and help book appointments directly on your site.`,
      },
    ]);
    setVisitorInput('');
  };

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-black space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-black" />
        <p className="text-xs font-bold uppercase">Loading widget settings...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h1 className="text-2xl font-black uppercase tracking-tight text-black flex items-center">
            <MessageSquareCode className="w-6 h-6 mr-2 text-black" /> Website Chat Widget
          </h1>
          <span className="bg-[#ffe600] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
            Web SDK
          </span>
        </div>
        <p className="text-xs font-semibold text-neutral-600">
          Embed an AI voice/text chat receptionist onto any website with a single script snippet.
        </p>
      </div>

      {/* Embed Snippet Card */}
      <div className="bg-black text-white rounded-2xl p-6 sm:p-7 brutal-border-3 brutal-shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b-2 border-neutral-800">
          <div>
            <h2 className="text-sm font-black uppercase tracking-wider text-white flex items-center">
              <Sparkles className="w-4 h-4 mr-2 text-[#ffe600]" /> Embed Script Snippet
            </h2>
            <p className="text-xs font-semibold text-neutral-400 mt-0.5">
              Paste this snippet right before the closing <code className="text-[#ffe600] font-mono">&lt;/body&gt;</code> tag on your website.
            </p>
          </div>
          <div className="flex items-center space-x-2.5">
            <button
              onClick={copySnippet}
              className="inline-flex items-center px-4 py-2 bg-[#ffe600] hover:bg-[#ffea2e] text-black rounded-xl text-xs font-black uppercase tracking-wider brutal-border brutal-shadow-xs brutal-shadow-hover transition"
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5 mr-1.5" /> Copied!
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5 mr-1.5" /> Copy Snippet
                </>
              )}
            </button>
            <button
              onClick={handleRegenerateKey}
              disabled={regenerating}
              className="inline-flex items-center px-3.5 py-2 bg-neutral-900 hover:bg-neutral-800 text-neutral-300 rounded-xl text-xs font-bold border-2 border-neutral-700 transition"
              title="Regenerate Public Key"
            >
              <RefreshCw className={cn('w-3.5 h-3.5 mr-1.5', regenerating && 'animate-spin')} />
              Regenerate
            </button>
          </div>
        </div>

        <pre className="mt-4 p-4 bg-neutral-950 rounded-xl text-xs font-mono text-[#a3e635] overflow-x-auto border-2 border-neutral-800">
          {snippetCode}
        </pre>
      </div>

      {/* Main Grid: Settings on Left, Live Preview on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Settings (7 cols) */}
        <form onSubmit={handleUpdate} className="lg:col-span-7 space-y-6">
          {saveSuccess && (
            <div className="p-4 bg-[#dcfce7] text-emerald-950 rounded-xl text-xs font-black uppercase border-2 border-black brutal-shadow-xs flex items-center">
              <Check className="w-4 h-4 mr-2 text-emerald-800" /> Widget settings saved successfully!
            </div>
          )}
          {error && (
            <div className="p-4 bg-rose-100 text-rose-950 rounded-xl text-xs font-black uppercase border-2 border-black brutal-shadow-xs">
              {error}
            </div>
          )}

          {/* General Appearance */}
          <div className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-7 brutal-shadow-lg space-y-4">
            <h3 className="text-sm font-black uppercase tracking-tight text-black flex items-center">
              <Palette className="w-4 h-4 mr-2 text-blue-600" /> Branding & Appearance
            </h3>

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-2">
                Primary Brand Color
              </label>
              <div className="flex items-center space-x-3">
                <input
                  type="color"
                  value={settings?.primary_color || '#2563EB'}
                  onChange={(e) =>
                    setSettings((prev) => (prev ? { ...prev, primary_color: e.target.value } : null))
                  }
                  className="w-11 h-11 rounded-xl cursor-pointer brutal-border p-0.5 brutal-shadow-xs"
                />
                <div className="flex flex-wrap gap-2">
                  {COLOR_PRESETS.map((c) => (
                    <button
                      key={c.hex}
                      type="button"
                      onClick={() =>
                        setSettings((prev) => (prev ? { ...prev, primary_color: c.hex } : null))
                      }
                      className={cn(
                        'w-8 h-8 rounded-lg brutal-border transition-transform',
                        settings?.primary_color.toLowerCase() === c.hex.toLowerCase()
                          ? 'scale-110 brutal-shadow-xs ring-2 ring-black'
                          : 'hover:scale-105'
                      )}
                      style={{ backgroundColor: c.hex }}
                      title={c.name}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Greeting Message
              </label>
              <textarea
                rows={2}
                value={settings?.greeting_message || ''}
                onChange={(e) =>
                  setSettings((prev) => (prev ? { ...prev, greeting_message: e.target.value } : null))
                }
                className="brutal-input resize-none"
                placeholder="Hi! How can our wellness team help you today?"
              />
            </div>
          </div>

          {/* Lead Capture Controls */}
          <div className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-7 brutal-shadow-lg space-y-4">
            <h3 className="text-sm font-black uppercase tracking-tight text-black flex items-center">
              <Sliders className="w-4 h-4 mr-2 text-blue-600" /> Lead Capture & Booking
            </h3>

            <div className="space-y-3">
              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.ask_lead_capture ?? true}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, ask_lead_capture: e.target.checked } : null
                    )
                  }
                  className="w-4 h-4 rounded brutal-border accent-black"
                />
                <div>
                  <span className="text-xs font-black uppercase tracking-wider text-black">
                    Enable Lead Capture Prompt
                  </span>
                  <p className="text-xs font-semibold text-neutral-500">
                    Prompt visitors for their email/phone so staff can follow up.
                  </p>
                </div>
              </label>

              <label className="flex items-center space-x-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings?.allow_booking ?? true}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, allow_booking: e.target.checked } : null
                    )
                  }
                  className="w-4 h-4 rounded brutal-border accent-black"
                />
                <div>
                  <span className="text-xs font-black uppercase tracking-wider text-black">
                    Enable Appointment Booking in Chat
                  </span>
                  <p className="text-xs font-semibold text-neutral-500">
                    Permit the agent to check calendar slots and confirm appointments directly.
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* Security & Allowed Origins */}
          <div className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-7 brutal-shadow-lg space-y-4">
            <h3 className="text-sm font-black uppercase tracking-tight text-black flex items-center">
              <Shield className="w-4 h-4 mr-2 text-blue-600" /> Security & Origin Restrictions
            </h3>

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Allowed Origins
              </label>
              <input
                type="text"
                value={settings?.allowed_origins || '*'}
                onChange={(e) =>
                  setSettings((prev) => (prev ? { ...prev, allowed_origins: e.target.value } : null))
                }
                className="brutal-input font-mono"
                placeholder="https://example.com,https://app.example.com"
              />
              <p className="text-[11px] font-mono text-neutral-500 mt-1">
                Comma-separated list of allowed domains, or <code className="text-black font-bold">*</code> to permit embedding anywhere.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                  Rate Limit (Queries / Min)
                </label>
                <input
                  type="number"
                  min={5}
                  max={120}
                  value={settings?.rate_limit_rpm || 30}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev ? { ...prev, rate_limit_rpm: parseInt(e.target.value) || 30 } : null
                    )
                  }
                  className="brutal-input font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                  Max Turns / Session
                </label>
                <input
                  type="number"
                  min={5}
                  max={50}
                  value={settings?.max_turns_per_session || 25}
                  onChange={(e) =>
                    setSettings((prev) =>
                      prev
                        ? { ...prev, max_turns_per_session: parseInt(e.target.value) || 25 }
                        : null
                    )
                  }
                  className="brutal-input font-mono"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Save Changes
            </button>
          </div>
        </form>

        {/* Live Widget Preview (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-black uppercase text-black flex items-center">
              <Globe className="w-4 h-4 mr-2 text-black" /> Interactive Preview
            </h3>
            <span className="text-[10px] font-black uppercase bg-[#a3e635] text-black px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Live Mockup
            </span>
          </div>

          {/* Mocked Widget Frame */}
          <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-xl flex flex-col h-[560px] overflow-hidden">
            {/* Widget Header */}
            <div
              className="p-4 text-white flex items-center justify-between border-b-2 border-black"
              style={{ backgroundColor: settings?.primary_color || '#2563EB' }}
            >
              <div className="flex items-center space-x-2.5">
                <div className="w-9 h-9 rounded-xl bg-white text-black brutal-border brutal-shadow-xs flex items-center justify-center">
                  <Bot className="w-5 h-5 stroke-[2.5]" />
                </div>
                <div>
                  <h4 className="text-sm font-black leading-tight">Reception Assistant</h4>
                  <p className="text-[10px] font-bold text-white/90 uppercase tracking-wider">Online &middot; Instant Reply</p>
                </div>
              </div>
            </div>

            {/* Widget Messages Body */}
            <div className="flex-1 bg-[#fbfaf6] p-4 overflow-y-auto space-y-3 text-xs">
              {settings?.ask_lead_capture && (
                <div className="p-3 bg-[#fef9c3] brutal-border rounded-xl text-black text-[11px] font-bold space-y-0.5 brutal-shadow-xs">
                  <p className="font-black uppercase">👋 Welcome! Want a quick callback?</p>
                  <p className="text-neutral-700">Leave your email or phone below anytime.</p>
                </div>
              )}

              {previewMessages.map((m, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'flex flex-col max-w-[85%] rounded-xl px-4 py-2.5 leading-relaxed font-bold brutal-border brutal-shadow-xs',
                    m.speaker === 'visitor'
                      ? 'ml-auto text-white'
                      : 'mr-auto bg-white text-black'
                  )}
                  style={
                    m.speaker === 'visitor'
                      ? { backgroundColor: settings?.primary_color || '#2563EB' }
                      : {}
                  }
                >
                  {m.text}
                </div>
              ))}
            </div>

            {/* Widget Input Box */}
            <form
              onSubmit={sendPreviewMessage}
              className="p-3 bg-white border-t-2 border-black flex items-center space-x-2"
            >
              <input
                type="text"
                placeholder="Ask about hours, services, booking..."
                value={visitorInput}
                onChange={(e) => setVisitorInput(e.target.value)}
                className="brutal-input flex-1 text-xs"
              />
              <button
                type="submit"
                className="p-2.5 rounded-xl text-white brutal-border brutal-shadow-xs transition hover:opacity-90 flex-shrink-0"
                style={{ backgroundColor: settings?.primary_color || '#2563EB' }}
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
