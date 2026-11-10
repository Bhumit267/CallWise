'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/auth-context';
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
  const { role } = useAuth();
  const isStaff = role?.toLowerCase() === 'staff';

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
      <div className="py-24 flex flex-col items-center justify-center text-black space-y-3">
        <div className="p-6 bg-white brutal-border-3 rounded-2xl brutal-shadow flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-black" />
          <span className="font-black text-sm uppercase">Loading settings...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h2 className="text-2xl font-black uppercase tracking-tight text-black">
            Settings & Receptionist Persona
          </h2>
          <span className="bg-[#ffe600] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
            Live Config
          </span>
        </div>
        <p className="text-xs font-semibold text-neutral-600">
          Configure AI persona, call transfer routing, operating hours, and service catalogs.
        </p>
      </div>

      {/* Tabs */}
      <div className="bg-white p-2 rounded-2xl brutal-border-3 brutal-shadow flex items-center space-x-2 overflow-x-auto">
        {SETTINGS_TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                'flex items-center px-4 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider whitespace-nowrap transition-all duration-100',
                isActive
                  ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs translate-x-[1px]'
                  : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200 border-2 border-transparent hover:border-black'
              )}
            >
              <Icon className="w-4 h-4 mr-2 stroke-[2.5]" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {error && (
        <div className="p-4 bg-rose-100 text-rose-950 text-xs font-black uppercase rounded-xl border-2 border-black brutal-shadow-xs">
          {error}
        </div>
      )}

      {isStaff && (
        <div className="p-4 bg-[#fef9c3] border-2 border-black rounded-2xl text-amber-950 text-xs font-bold flex items-center gap-2.5 brutal-shadow-xs">
          <ShieldCheck className="w-5 h-5 text-amber-800 shrink-0" />
          <span>
            <strong>Read-only settings:</strong> You are viewing business settings as staff. Modifying voice profiles, forwarding numbers, operating hours, and service catalogs requires Manager or Owner privileges.
          </span>
        </div>
      )}

      {/* Tab 1: AI Voice & Greeting */}
      {activeTab === 'profile' && (
        <form onSubmit={handleSaveProfile} className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-8 space-y-6 brutal-shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b-2 border-black pb-5">
            <div>
              <h3 className="text-lg font-black uppercase tracking-tight text-black">AI Personality & Greeting</h3>
              <p className="text-xs font-semibold text-neutral-600">
                Customize how your voice receptionist introduces itself and speaks with callers.
              </p>
            </div>

            <button
              type="submit"
              disabled={savingProfile || isStaff}
              className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition disabled:opacity-50"
            >
              {savingProfile ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : profileSuccess ? (
                <Check className="w-4 h-4 mr-2 text-[#a3e635]" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              {profileSuccess ? 'Settings Saved!' : 'Save Voice Profile'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Business Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="brutal-input"
              />
            </div>

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Business Type
              </label>
              <input
                type="text"
                value={businessType}
                onChange={(e) => setBusinessType(e.target.value)}
                placeholder="e.g. Dental Clinic, Law Firm, HVAC Contractor"
                className="brutal-input"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
              Spoken Inbound Greeting Message
            </label>
            <textarea
              rows={3}
              required
              value={greeting}
              onChange={(e) => setGreeting(e.target.value)}
              className="brutal-input resize-none"
            />
            <p className="text-[11px] font-mono text-neutral-500 mt-1.5">
              Opening sentence spoken by the voice assistant as soon as a caller is connected.
            </p>
          </div>

          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-black mb-2">
              Voice Tone & Persona
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {TONES.map((t) => (
                <div
                  key={t.id}
                  onClick={() => setTone(t.id)}
                  className={cn(
                    'p-4 rounded-xl brutal-border cursor-pointer transition text-left space-y-1',
                    tone === t.id
                      ? 'bg-[#ffe600] text-black brutal-shadow-sm translate-x-[1px]'
                      : 'bg-neutral-50 hover:bg-neutral-100 brutal-shadow-xs'
                  )}
                >
                  <p className="text-xs font-black uppercase">{t.label}</p>
                  <p className="text-[11px] font-semibold text-neutral-700">{t.desc}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 pt-3 border-t-2 border-black/10">
            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Timezone
              </label>
              <input
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                placeholder="e.g. America/New_York or UTC"
                className="brutal-input font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Company Website
              </label>
              <input
                type="url"
                value={websiteUrl}
                onChange={(e) => setWebsiteUrl(e.target.value)}
                placeholder="https://example.com"
                className="brutal-input"
              />
            </div>
          </div>
        </form>
      )}

      {/* Tab 2: Phone Routing & Forwarding */}
      {activeTab === 'routing' && (
        <form onSubmit={handleSaveProfile} className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-8 space-y-6 brutal-shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b-2 border-black pb-5">
            <div>
              <h3 className="text-lg font-black uppercase tracking-tight text-black">Call Transfer & Routing</h3>
              <p className="text-xs font-semibold text-neutral-600">
                Configure live phone forwarding to your human staff or front desk.
              </p>
            </div>

            <button
              type="submit"
              disabled={savingProfile || isStaff}
              className="inline-flex items-center px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition disabled:opacity-50"
            >
              {savingProfile ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : profileSuccess ? (
                <Check className="w-4 h-4 mr-2 text-[#a3e635]" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              {profileSuccess ? 'Routing Saved!' : 'Save Routing'}
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Forwarding / Transfer Number
              </label>
              <input
                type="tel"
                value={transferNumber}
                onChange={(e) => setTransferNumber(e.target.value)}
                placeholder="+1 (555) 123-4567"
                className="brutal-input font-mono"
              />
              <p className="text-[11px] font-semibold text-neutral-500 mt-1">
                Phone number dialed when the caller requests a human or during urgent escalations.
              </p>
            </div>

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Notification Email Address
              </label>
              <input
                type="email"
                value={notificationEmail}
                onChange={(e) => setNotificationEmail(e.target.value)}
                placeholder="reception@company.com"
                className="brutal-input"
              />
              <p className="text-[11px] font-semibold text-neutral-500 mt-1">
                Receives instant email alerts for callback messages and urgent missed transfers.
              </p>
            </div>
          </div>

          <div className="p-5 bg-neutral-100 brutal-border rounded-xl space-y-2 brutal-shadow-xs">
            <h4 className="text-xs font-black uppercase text-black">Warm Transfer Protocol</h4>
            <p className="text-xs font-semibold text-neutral-700 leading-relaxed">
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
        <div className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-8 space-y-6 brutal-shadow-lg">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b-2 border-black pb-5">
            <div>
              <h3 className="text-lg font-black uppercase tracking-tight text-black">Service Offerings & Durations</h3>
              <p className="text-xs font-semibold text-neutral-600">
                Services the AI voice receptionist is authorized to quote and schedule into your calendar.
              </p>
            </div>

            {!isStaff && (
              <button
                onClick={() => {
                  setEditingService(null);
                  setIsServiceModalOpen(true);
                }}
                className="inline-flex items-center px-4 py-2.5 bg-[#10b981] hover:bg-[#059669] text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition"
              >
                <PlusCircle className="w-4 h-4 mr-2" /> Add New Service
              </button>
            )}
          </div>

          {services.length === 0 ? (
            <div className="py-12 text-center text-neutral-500 font-bold text-xs">
              No services defined yet. Click &quot;Add New Service&quot; to configure appointment options.
            </div>
          ) : (
            <div className="divide-y-2 divide-black/10">
              {services.map((svc) => (
                <div
                  key={svc.id}
                  className="py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
                >
                  <div className="min-w-0 space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-black text-sm text-black">{svc.name}</span>
                      {!svc.is_active && (
                        <span className="text-[10px] bg-neutral-200 text-neutral-700 px-2 py-0.5 rounded font-black brutal-border uppercase">
                          Deactivated
                        </span>
                      )}
                    </div>
                    {svc.description && (
                      <p className="text-neutral-600 text-xs font-semibold line-clamp-1">{svc.description}</p>
                    )}
                  </div>

                  <div className="flex items-center space-x-4">
                    <span className="font-mono font-bold bg-neutral-100 px-2.5 py-1 rounded-lg brutal-border text-black">
                      {svc.duration_minutes} mins
                    </span>
                    <span className="font-black text-xs bg-[#dcfce7] text-emerald-950 px-2.5 py-1 rounded-lg brutal-border">
                      {svc.price > 0 ? `$${svc.price}` : 'Free'}
                    </span>

                    {!isStaff && (
                      <div className="flex items-center space-x-2">
                        <button
                          onClick={() => {
                            setEditingService(svc);
                            setIsServiceModalOpen(true);
                          }}
                          className="p-1.5 bg-white brutal-border rounded-lg text-neutral-700 hover:text-black brutal-shadow-xs"
                          title="Edit"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => setDeleteTarget(svc)}
                          className="p-1.5 bg-rose-50 brutal-border rounded-lg text-rose-700 hover:text-rose-900 brutal-shadow-xs"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 5: AI & Integrations */}
      {activeTab === 'providers' && settingsData && (
        <div className="bg-white rounded-2xl brutal-border-3 p-6 sm:p-8 space-y-6 brutal-shadow-lg">
          <div>
            <h3 className="text-lg font-black uppercase tracking-tight text-black">Active AI Models & Integrations</h3>
            <p className="text-xs font-semibold text-neutral-600">
              Underlying real-time infrastructure powering your voice receptionist.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="p-5 bg-neutral-50 brutal-border rounded-2xl space-y-1 brutal-shadow-xs">
              <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">LLM Provider</span>
              <p className="text-sm font-black text-black capitalize">
                {settingsData.providers.llm_provider || 'groq (llama-3.1-8b-instant)'}
              </p>
              <p className="text-[11px] font-semibold text-neutral-600">Sub-second streaming dialog synthesis</p>
            </div>

            <div className="p-5 bg-neutral-50 brutal-border rounded-2xl space-y-1 brutal-shadow-xs">
              <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">TTS Voice Engine</span>
              <p className="text-sm font-black text-black capitalize">
                {settingsData.providers.tts_provider || 'cartesia / deepgram'}
              </p>
              <p className="text-[11px] font-semibold text-neutral-600">Natural conversational speech playback</p>
            </div>

            <div className="p-5 bg-neutral-50 brutal-border rounded-2xl space-y-1 brutal-shadow-xs">
              <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">STT Speech Engine</span>
              <p className="text-sm font-black text-black capitalize">
                {settingsData.providers.stt_provider || 'deepgram (nova-2)'}
              </p>
              <p className="text-[11px] font-semibold text-neutral-600">Real-time caller speech transcription</p>
            </div>

            <div className="p-5 bg-neutral-50 brutal-border rounded-2xl space-y-1 brutal-shadow-xs">
              <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Embedding Model</span>
              <p className="text-sm font-black text-black capitalize">
                {settingsData.providers.embedding_provider || 'all-MiniLM-L6-v2'}
              </p>
              <p className="text-[11px] font-semibold text-neutral-600">Vector search & knowledge retrieval</p>
            </div>

            <div className="p-5 bg-neutral-50 brutal-border rounded-2xl space-y-1 brutal-shadow-xs">
              <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Email Notifications</span>
              <p className="text-sm font-black text-emerald-700">
                {settingsData.providers.email_notifications_enabled ? 'Active / Configured' : 'Development Console Mode'}
              </p>
              <p className="text-[11px] font-semibold text-neutral-600">Team invites and callback alerts</p>
            </div>

            <div className="p-5 bg-neutral-50 brutal-border rounded-2xl space-y-1 brutal-shadow-xs">
              <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Google Calendar</span>
              <p className="text-sm font-black text-blue-700">
                {settingsData.providers.google_calendar_enabled ? 'Connected & Synced' : 'Local Database Sync'}
              </p>
              <p className="text-[11px] font-semibold text-neutral-600">Two-way real-time appointment sync</p>
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
