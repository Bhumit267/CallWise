'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { BusinessSettingsResponse, ServiceItem } from '@/types/api';
import { ServiceModal } from '@/components/settings/service-modal';
import { DeleteServiceModal } from '@/components/settings/delete-service-modal';
import { OperatingHoursEditor } from '@/components/settings/operating-hours-editor';
import {
  Settings,
  Bot,
  PhoneCall,
  Clock,
  Calendar,
  Layers,
  Save,
  Loader2,
  Check,
  PlusCircle,
  Edit2,
  Trash2,
  Cpu,
  Mail,
  ShieldCheck,
  Globe,
  Radio,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const SETTINGS_TABS = [
  { id: 'profile', label: 'AI Voice & Greeting', icon: Bot },
  { id: 'routing', label: 'Phone Routing & Forwarding', icon: PhoneCall },
  { id: 'hours', label: 'Operating Hours', icon: Clock },
  { id: 'services', label: 'Service Catalog', icon: Calendar },
  { id: 'providers', label: 'AI & Integrations', icon: Cpu },
];

const TONES = [
  { id: 'professional and friendly', label: 'Professional & Friendly', desc: 'Courteous, warm, clear, and reassuring' },
  { id: 'warm and empathetic', label: 'Warm & Empathetic', desc: 'Patient and understanding, great for clinics & care' },
  { id: 'direct and concise', label: 'Direct & Concise', desc: 'Fast, efficient, and action-oriented for busy trades' },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');
  const [settingsData, setSettingsData] = useState<BusinessSettingsResponse | null>(null);
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileSuccess, setProfileSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Profile Form State
  const [name, setName] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [greeting, setGreeting] = useState('');
  const [tone, setTone] = useState('professional and friendly');
  const [timezone, setTimezone] = useState('UTC');
  const [transferNumber, setTransferNumber] = useState('');
  const [notificationEmail, setNotificationEmail] = useState('');
  const [retentionDays, setRetentionDays] = useState(90);
  const [websiteUrl, setWebsiteUrl] = useState('');

  // Service Modals
  const [isServiceModalOpen, setIsServiceModalOpen] = useState(false);
  const [editingService, setEditingService] = useState<ServiceItem | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ServiceItem | null>(null);

  const fetchSettings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [settingsRes, servicesRes] = await Promise.all([
        apiClient<BusinessSettingsResponse>('/api/settings'),
        apiClient<ServiceItem[]>('/api/settings/services'),
      ]);

      setSettingsData(settingsRes);
      setServices(servicesRes || []);

      // Populate form fields
      setName(settingsRes.name || '');
      setBusinessType(settingsRes.business_type || '');
      setGreeting(settingsRes.greeting || '');
      setTone(settingsRes.tone || 'professional and friendly');
      setTimezone(settingsRes.timezone || 'UTC');
      setTransferNumber(settingsRes.transfer_number || '');
      setNotificationEmail(settingsRes.notification_email || '');
      setRetentionDays(settingsRes.retention_days || 90);
      setWebsiteUrl(settingsRes.website_url || '');
    } catch (err: any) {
      setError(err.message || 'Failed to load business settings');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSettings();
  }, [fetchSettings]);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setError(null);
    setProfileSuccess(false);

    try {
      await apiClient('/api/settings/profile', {
        method: 'PUT',
        body: JSON.stringify({
          name: name.trim() || undefined,
          business_type: businessType.trim() || undefined,
          greeting: greeting.trim() || undefined,
          tone: tone.trim() || undefined,
          timezone: timezone.trim() || undefined,
          transfer_number: transferNumber.trim() || null,
          notification_email: notificationEmail.trim() || null,
          retention_days: Number(retentionDays) || 90,
          website_url: websiteUrl.trim() || null,
        }),
      });

      setProfileSuccess(true);
      fetchSettings();
      setTimeout(() => setProfileSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to save settings');
    } finally {
      setSavingProfile(false);
    }
  };

  if (loading && !settingsData) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400 space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <p className="text-sm">Loading business profile & configuration...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">
          Business & Voice Receptionist Settings
        </h2>
        <p className="text-sm text-slate-500">
          Configure AI persona, call transfer routing, operating hours, and service catalogs.
        </p>
      </div>

      {/* Tabs */}
      <div className="bg-white p-2 rounded-xl border border-slate-200 shadow-sm flex items-center space-x-1 overflow-x-auto">
        {SETTINGS_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center px-4 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition',
                isActive
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
              )}
            >
              <Icon className="w-4 h-4 mr-2" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="p-4 bg-red-50 text-red-700 text-sm rounded-xl border border-red-200">
          {error}
        </div>
      )}

      {/* Tab 1: AI Voice & Greeting */}
      {activeTab === 'profile' && (
        <form onSubmit={handleSaveProfile} className="bg-white rounded-xl border border-slate-200 p-6 space-y-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">AI Personality & Greeting</h3>
              <p className="text-xs text-slate-500">
                Customize how your voice receptionist introduces itself and speaks with callers.
              </p>
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
            >
              {savingProfile ? (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              ) : profileSuccess ? (
                <Check className="w-4 h-4 mr-1.5 text-emerald-300" />
              ) : (
                <Save className="w-4 h-4 mr-1.5" />
              )}
              {profileSuccess ? 'Settings Saved!' : 'Save Voice Profile'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Business Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Business Type</label>
              <input
                type="text"
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                placeholder="e.g. Dental Clinic, Law Firm, HVAC Contractor"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Spoken Inbound Greeting Message
            </label>
            <textarea
              rows={3}
              required
              value={greeting}
              onChange={(e) => setGreeting(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 resize-none"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              This is the opening sentence spoken by the voice assistant as soon as a call is answered.
            </p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-2">Voice Tone & Persona</label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {TONES.map((t) => (
                <div
                  key={t.id}
                  onClick={() => setTone(t.id)}
                  className={cn(
                    'p-3 rounded-xl border cursor-pointer transition text-left space-y-1',
                    tone === t.id
                      ? 'border-blue-600 bg-blue-50/60 ring-1 ring-blue-600'
                      : 'border-slate-200 hover:border-slate-300 bg-slate-50/50'
                  )}
                >
                  <p className="text-xs font-bold text-slate-900">{t.label}</p>
                  <p className="text-[11px] text-slate-500">{t.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-slate-100">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Timezone</label>
              <input
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="e.g. America/New_York or UTC"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">Company Website</label>
              <input
                type="url"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                placeholder="https://example.com"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>
        </form>
      )}

      {/* Tab 2: Phone Routing & Forwarding */}
      {activeTab === 'routing' && (
        <form onSubmit={handleSaveProfile} className="bg-white rounded-xl border border-slate-200 p-6 space-y-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Call Transfer & Routing</h3>
              <p className="text-xs text-slate-500">
                Configure live phone forwarding to your human staff or front desk.
              </p>
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
            >
              {savingProfile ? (
                <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
              ) : profileSuccess ? (
                <Check className="w-4 h-4 mr-1.5 text-emerald-300" />
              ) : (
                <Save className="w-4 h-4 mr-1.5" />
              )}
              {profileSuccess ? 'Routing Saved!' : 'Save Routing'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Forwarding / Transfer Number
              </label>
              <input
                type="tel"
                value={transferNumber}
                onChange={(e) => setTransferNumber(e.target.value)}
                placeholder="+1 (555) 123-4567"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Phone number dialed when the caller requests a human or during urgent escalations.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Notification Email Address
              </label>
              <input
                type="email"
                value={notificationEmail}
                onChange={(e) => setNotificationEmail(e.target.value)}
                placeholder="reception@company.com"
                className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
              <p className="text-[11px] text-slate-400 mt-1">
                Receives instant email alerts for callback messages and urgent missed transfers.
              </p>
            </div>
          </div>

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-2">
            <h4 className="text-xs font-bold text-slate-800">Warm Transfer Protocol</h4>
            <p className="text-xs text-slate-500 leading-relaxed">
              When a caller asks to speak with staff, the AI checks operating hours first. If open and within business hours, the call is transferred to the forwarding number. If the line is busy or unanswered, Callwise smoothly falls back to recording a callback message.
            </p>
          </div>
        </form>
      )}

      {/* Tab 3: Operating Hours */}
      {activeTab === 'hours' && (
        <OperatingHoursEditor
          initialHours={settingsData?.hours}
          onSaved={() => fetchSettings()}
        />
      )}

      {/* Tab 4: Service Catalog */}
      {activeTab === 'services' && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
            <div>
              <h3 className="text-base font-bold text-slate-900">Service Offerings & Durations</h3>
              <p className="text-xs text-slate-500">
                Services the AI voice receptionist is authorized to quote and schedule into your calendar.
              </p>
            </div>

            <button
              onClick={() => {
                setEditingService(null);
                setIsServiceModalOpen(true);
              }}
              className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition"
            >
              <PlusCircle className="w-4 h-4 mr-1.5" /> Add New Service
            </button>
          </div>

          {services.length === 0 ? (
            <div className="py-12 text-center text-slate-400 text-xs">
              No services defined yet. Click "Add New Service" to configure appointment options.
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {services.map((svc) => (
                <div
                  key={svc.id}
                  className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="min-w-0 space-y-0.5">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-slate-900">{svc.name}</span>
                      {!svc.is_active && (
                        <span className="text-[10px] bg-slate-200 text-slate-600 px-1.5 py-0.2 rounded font-semibold">
                          Deactivated
                        </span>
                      )}
                    </div>
                    {svc.description && (
                      <p className="text-slate-500 text-[11px] line-clamp-1">{svc.description}</p>
                    )}
                  </div>

                  <div className="flex items-center space-x-6 text-slate-600">
                    <span className="font-semibold text-slate-800">{svc.duration_minutes} mins</span>
                    <span className="font-semibold text-emerald-700">
                      {svc.price > 0 ? `$${svc.price}` : 'Free'}
                    </span>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => {
                          setEditingService(svc);
                          setIsServiceModalOpen(true);
                        }}
                        className="p-1 text-slate-400 hover:text-slate-800 rounded"
                        title="Edit"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setDeleteTarget(svc)}
                        className="p-1 text-red-400 hover:text-red-700 rounded"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: AI & Integrations */}
      {activeTab === 'providers' && settingsData && (
        <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6 shadow-sm">
          <div>
            <h3 className="text-base font-bold text-slate-900">Active AI Models & Integrations</h3>
            <p className="text-xs text-slate-500">
              Underlying real-time infrastructure powering your voice receptionist.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">LLM Provider</span>
              <p className="text-sm font-bold text-slate-900 capitalize">
                {settingsData.providers.llm_provider || 'openai (gpt-4o-mini)'}
              </p>
              <p className="text-[11px] text-slate-500">Sub-second streaming dialog synthesis</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">TTS Voice Engine</span>
              <p className="text-sm font-bold text-slate-900 capitalize">
                {settingsData.providers.tts_provider || 'cartesia (ultra-low latency)'}
              </p>
              <p className="text-[11px] text-slate-500">Natural conversational speech playback</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">STT Speech Engine</span>
              <p className="text-sm font-bold text-slate-900 capitalize">
                {settingsData.providers.stt_provider || 'deepgram (nova-2)'}
              </p>
              <p className="text-[11px] text-slate-500">Real-time caller speech transcription</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Embedding Model</span>
              <p className="text-sm font-bold text-slate-900 capitalize">
                {settingsData.providers.embedding_provider || 'text-embedding-3-small'}
              </p>
              <p className="text-[11px] text-slate-500">Vector search & knowledge retrieval</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Email Notifications</span>
              <p className="text-sm font-bold text-emerald-700">
                {settingsData.providers.email_notifications_enabled ? 'Active / Configured' : 'Development Console Mode'}
              </p>
              <p className="text-[11px] text-slate-500">Team invites and callback message alerts</p>
            </div>

            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase">Google Calendar</span>
              <p className="text-sm font-bold text-blue-700">
                {settingsData.providers.google_calendar_enabled ? 'Connected & Synced' : 'Local Database Sync'}
              </p>
              <p className="text-[11px] text-slate-500">Two-way real-time appointment sync</p>
            </div>
          </div>
        </div>
      )}

      {/* Service Modals */}
      <ServiceModal
        isOpen={isServiceModalOpen}
        onClose={() => setIsServiceModalOpen(false)}
        onSuccess={() => fetchSettings()}
        service={editingService}
      />

      {deleteTarget && (
        <DeleteServiceModal
          isOpen={Boolean(deleteTarget)}
          onClose={() => setDeleteTarget(null)}
          onSuccess={() => fetchSettings()}
          serviceId={deleteTarget.id}
          serviceName={deleteTarget.name}
        />
      )}
    </div>
  );
}
