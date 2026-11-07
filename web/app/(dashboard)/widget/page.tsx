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
  { name: 'Emerald', hex: '#10B981' },
  { name: 'Royal Purple', hex: '#9333EA' },
  { name: 'Indigo', hex: '#4F46E5' },
  { name: 'Amber', hex: '#D97706' },
  { name: 'Slate', hex: '#334155' },
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
      <div className="p-16 flex flex-col items-center justify-center text-slate-400 space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <p className="text-sm">Loading widget settings...</p>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900 flex items-center">
          <MessageSquareCode className="w-6 h-6 mr-2.5 text-blue-600" /> Website Chat Widget
        </h1>
        <p className="text-sm text-slate-500 mt-1">
          Embed an AI voice/text chat receptionist onto any website with a single script snippet.
        </p>
      </div>

      {/* Embed Snippet Card */}
      <div className="bg-slate-900 text-slate-100 rounded-xl p-6 shadow-md border border-slate-800">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-800">
          <div>
            <h2 className="text-sm font-bold text-white flex items-center">
              <Sparkles className="w-4 h-4 mr-2 text-blue-400" /> Embed Script
            </h2>
            <p className="text-xs text-slate-400 mt-0.5">
              Paste this snippet right before the closing <code className="text-blue-300">&lt;/body&gt;</code> tag on your website.
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={copySnippet}
              className="inline-flex items-center px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-sm transition"
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
              className="inline-flex items-center px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium border border-slate-700 transition"
              title="Regenerate Public Key"
            >
              <RefreshCw className={cn('w-3.5 h-3.5 mr-1.5', regenerating && 'animate-spin')} />
              Regenerate
            </button>
          </div>
        </div>

        <pre className="mt-4 p-4 bg-slate-950 rounded-lg text-xs font-mono text-blue-300 overflow-x-auto border border-slate-800/80">
          {snippetCode}
        </pre>
      </div>

      {/* Main Grid: Settings on Left, Live Preview on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Form Settings (7 cols) */}
        <form onSubmit={handleUpdate} className="lg:col-span-7 space-y-6">
          {saveSuccess && (
            <div className="p-4 bg-emerald-50 text-emerald-800 rounded-xl text-sm font-medium border border-emerald-200 flex items-center">
              <Check className="w-4 h-4 mr-2 text-emerald-600" /> Widget settings saved successfully!
            </div>
          )}
          {error && (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
              {error}
            </div>
          )}

          {/* General Appearance */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center">
              <Palette className="w-4 h-4 mr-2 text-blue-600" /> Branding & Appearance
            </h3>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-2">
                Primary Brand Color
              </label>
              <div className="flex items-center space-x-3">
                <input
                  type="color"
                  value={settings?.primary_color || '#2563EB'}
                  onChange={(e) =>
                    setSettings((prev) => (prev ? { ...prev, primary_color: e.target.value } : null))
                  }
                  className="w-10 h-10 rounded-lg cursor-pointer border border-slate-200 p-0.5"
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
                        'w-7 h-7 rounded-full border-2 transition',
                        settings?.primary_color.toLowerCase() === c.hex.toLowerCase()
                          ? 'border-slate-900 scale-110 shadow-sm'
                          : 'border-transparent hover:scale-105'
                      )}
                      style={{ backgroundColor: c.hex }}
                      title={c.name}
                    />
                  ))}
                </div>
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Greeting Message
              </label>
              <textarea
                rows={2}
                value={settings?.greeting_message || ''}
                onChange={(e) =>
                  setSettings((prev) => (prev ? { ...prev, greeting_message: e.target.value } : null))
                }
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Hi! How can our wellness team help you today?"
              />
            </div>
          </div>

          {/* Lead Capture Controls */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center">
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
                  className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                />
                <div>
                  <span className="text-sm font-medium text-slate-800">
                    Enable Lead Capture Prompt
                  </span>
                  <p className="text-xs text-slate-400">
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
                  className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                />
                <div>
                  <span className="text-sm font-medium text-slate-800">
                    Enable Appointment Booking in Chat
                  </span>
                  <p className="text-xs text-slate-400">
                    Permit the agent to check calendar slots and confirm appointments directly.
                  </p>
                </div>
              </label>
            </div>
          </div>

          {/* Security & Allowed Origins */}
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-slate-900 flex items-center">
              <Shield className="w-4 h-4 mr-2 text-blue-600" /> Security & Origin Restrictions
            </h3>

            <div>
              <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                Allowed Origins
              </label>
              <input
                type="text"
                value={settings?.allowed_origins || '*'}
                onChange={(e) =>
                  setSettings((prev) => (prev ? { ...prev, allowed_origins: e.target.value } : null))
                }
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="https://example.com,https://app.example.com"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Comma-separated list of allowed domains, or <code className="text-slate-600">*</code> to permit embedding anywhere.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
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
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
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
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
            >
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Save Changes
            </button>
          </div>
        </form>

        {/* Live Widget Preview (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-900 flex items-center">
              <Globe className="w-4 h-4 mr-2 text-slate-500" /> Interactive Preview
            </h3>
            <span className="text-[11px] font-semibold text-slate-400 uppercase">
              Live Mockup
            </span>
          </div>

          {/* Mocked Widget Frame */}
          <div className="bg-slate-100 rounded-2xl p-4 border border-slate-300 shadow-inner flex flex-col h-[560px]">
            {/* Widget Header */}
            <div
              className="p-4 rounded-t-xl text-white flex items-center justify-between shadow-sm transition-colors duration-300"
              style={{ backgroundColor: settings?.primary_color || '#2563EB' }}
            >
              <div className="flex items-center space-x-2.5">
                <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center backdrop-blur-sm">
                  <Bot className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-bold leading-tight">Reception Assistant</h4>
                  <p className="text-[10px] text-white/80">Online • Typically replies instantly</p>
                </div>
              </div>
            </div>

            {/* Widget Messages Body */}
            <div className="flex-1 bg-white p-4 overflow-y-auto space-y-3 text-xs">
              {settings?.ask_lead_capture && (
                <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg text-slate-600 text-[11px] space-y-1">
                  <p className="font-semibold text-slate-700">👋 Welcome! Want a quick callback?</p>
                  <p className="text-slate-500">Leave your email or phone below anytime.</p>
                </div>
              )}

              {previewMessages.map((m, idx) => (
                <div
                  key={idx}
                  className={cn(
                    'flex flex-col max-w-[85%] rounded-xl px-3.5 py-2 leading-relaxed',
                    m.speaker === 'visitor'
                      ? 'ml-auto text-white'
                      : 'mr-auto bg-slate-100 text-slate-800'
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
              className="p-2 bg-white rounded-b-xl border-t border-slate-100 flex items-center space-x-2"
            >
              <input
                type="text"
                placeholder="Ask about hours, services, booking..."
                value={visitorInput}
                onChange={(e) => setVisitorInput(e.target.value)}
                className="flex-1 px-3 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-blue-500"
              />
              <button
                type="submit"
                className="p-1.5 rounded-lg text-white transition hover:opacity-90"
                style={{ backgroundColor: settings?.primary_color || '#2563EB' }}
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
