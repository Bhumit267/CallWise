'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Building2,
  Clock,
  Briefcase,
  Bot,
  Globe,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Plus,
  Trash2,
  AlertCircle,
  Sparkles,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { OnboardingSetupRequest, OnboardingSetupResponse } from '@/types/api';
import { useAuth } from '@/contexts/auth-context';

const STEPS = [
  { id: 1, title: 'Business Profile', icon: Building2 },
  { id: 2, title: 'Hours & Operations', icon: Clock },
  { id: 3, title: 'Service Catalog', icon: Briefcase },
  { id: 4, title: 'Voice Persona', icon: Bot },
  { id: 5, title: 'Website Ingestion', icon: Globe },
];

const DEFAULT_DAYS = [
  { key: 'monday', label: 'Monday', open: '09:00', close: '17:00', closed: false },
  { key: 'tuesday', label: 'Tuesday', open: '09:00', close: '17:00', closed: false },
  { key: 'wednesday', label: 'Wednesday', open: '09:00', close: '17:00', closed: false },
  { key: 'thursday', label: 'Thursday', open: '09:00', close: '17:00', closed: false },
  { key: 'friday', label: 'Friday', open: '09:00', close: '17:00', closed: false },
  { key: 'saturday', label: 'Saturday', open: '10:00', close: '14:00', closed: true },
  { key: 'sunday', label: 'Sunday', open: '10:00', close: '14:00', closed: true },
];

export default function OnboardingPage() {
  const router = useRouter();
  const { currentBusiness, refreshAuth } = useAuth();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form State
  const [formData, setFormData] = useState<{
    name: string;
    business_type: string;
    timezone: string;
    transfer_number: string;
    notification_email: string;
    days: typeof DEFAULT_DAYS;
    services: { name: string; duration_minutes: number; price: number; description: string }[];
    greeting: string;
    tone: string;
    website_url: string;
  }>({
    name: currentBusiness?.name || '',
    business_type: currentBusiness?.business_type || 'General Service',
    timezone: currentBusiness?.timezone || 'America/New_York',
    transfer_number: currentBusiness?.transfer_number || '',
    notification_email: currentBusiness?.notification_email || '',
    days: DEFAULT_DAYS,
    services: [
      { name: 'Initial Consultation', duration_minutes: 30, price: 50, description: 'General introductory consultation' },
    ],
    greeting:
      currentBusiness?.greeting ||
      "Hello! Thank you for calling. How can I help you today?",
    tone: currentBusiness?.tone || 'friendly',
    website_url: '',
  });

  const handleDayChange = (index: number, field: string, value: any) => {
    setFormData((prev) => {
      const newDays = [...prev.days];
      newDays[index] = { ...newDays[index], [field]: value };
      return { ...prev, days: newDays };
    });
  };

  const handleAddService = () => {
    setFormData((prev) => ({
      ...prev,
      services: [
        ...prev.services,
        { name: '', duration_minutes: 30, price: 0, description: '' },
      ],
    }));
  };

  const handleRemoveService = (index: number) => {
    setFormData((prev) => ({
      ...prev,
      services: prev.services.filter((_, i) => i !== index),
    }));
  };

  const handleServiceChange = (index: number, field: string, value: any) => {
    setFormData((prev) => {
      const newServices = [...prev.services];
      newServices[index] = { ...newServices[index], [field]: value };
      return { ...prev, services: newServices };
    });
  };

  const handleNext = () => {
    setError(null);
    if (currentStep === 1 && !formData.name.trim()) {
      setError('Business name is required.');
      return;
    }
    if (currentStep === 4 && !formData.greeting.trim()) {
      setError('Greeting message is required.');
      return;
    }
    setCurrentStep((s) => Math.min(s + 1, 5));
  };

  const handleBack = () => {
    setError(null);
    setCurrentStep((s) => Math.max(s - 1, 1));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    // Build structured operating hours
    const hoursObj: Record<string, any> = {};
    formData.days.forEach((d) => {
      hoursObj[d.key] = d.closed
        ? { closed: true }
        : { open: d.open, close: d.close, closed: false };
    });

    const payload: OnboardingSetupRequest = {
      name: formData.name.trim(),
      business_type: formData.business_type.trim(),
      timezone: formData.timezone,
      greeting: formData.greeting.trim(),
      tone: formData.tone,
      hours: hoursObj,
      transfer_number: formData.transfer_number.trim() || null,
      notification_email: formData.notification_email.trim() || null,
      website_url: formData.website_url.trim() || null,
      retention_days: 90,
      services: formData.services
        .filter((s) => s.name.trim().length > 0)
        .map((s) => ({
          name: s.name.trim(),
          duration_minutes: Number(s.duration_minutes) || 30,
          price: Number(s.price) || 0,
          description: s.description.trim() || null,
          is_active: true,
        })),
    };

    try {
      await apiClient<OnboardingSetupResponse>('/api/onboarding/setup', {
        method: 'POST',
        body: JSON.stringify(payload),
      });

      await refreshAuth();
      router.push('/test-agent');
    } catch (err: any) {
      setError(err?.message || 'Failed to complete onboarding setup.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-blue-50 text-blue-700 text-xs font-semibold rounded-full border border-blue-200">
            <Sparkles className="w-3.5 h-3.5" />
            Quick Setup Wizard
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Welcome to Callwise
          </h1>
          <p className="text-sm text-slate-500 max-w-md mx-auto">
            Configure your AI receptionist in 5 quick steps to start answering caller inquiries, booking appointments, and capturing leads.
          </p>
        </div>

        {/* Stepper Progress Bar */}
        <div className="bg-white rounded-xl border border-slate-200 p-4 shadow-xs">
          <div className="flex items-center justify-between">
            {STEPS.map((step, idx) => {
              const Icon = step.icon;
              const isPassed = currentStep > step.id;
              const isCurrent = currentStep === step.id;

              return (
                <div key={step.id} className="flex-1 flex items-center">
                  <div className="flex flex-col items-center flex-1">
                    <div
                      className={`w-9 h-9 rounded-full flex items-center justify-center text-xs font-semibold transition-colors ${
                        isPassed
                          ? 'bg-blue-600 text-white'
                          : isCurrent
                          ? 'bg-blue-100 text-blue-700 border-2 border-blue-600'
                          : 'bg-slate-100 text-slate-400'
                      }`}
                    >
                      {isPassed ? <CheckCircle2 className="w-4 h-4" /> : <Icon className="w-4 h-4" />}
                    </div>
                    <span
                      className={`text-[11px] font-medium mt-1.5 hidden sm:block ${
                        isCurrent ? 'text-blue-600 font-semibold' : 'text-slate-400'
                      }`}
                    >
                      {step.title}
                    </span>
                  </div>
                  {idx < STEPS.length - 1 && (
                    <div
                      className={`h-0.5 flex-1 transition-colors ${
                        currentStep > step.id ? 'bg-blue-600' : 'bg-slate-200'
                      }`}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Form Body Card */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 sm:p-8 shadow-xs">
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* STEP 1: Business Profile */}
          {currentStep === 1 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 1: Business Details</h2>
                <p className="text-xs text-slate-500">Tell us about your business profile and location timezone.</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Business Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. Apex Health Clinic or Summit Legal Group"
                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Industry / Type
                    </label>
                    <input
                      type="text"
                      value={formData.business_type}
                      onChange={(e) => setFormData({ ...formData, business_type: e.target.value })}
                      placeholder="e.g. Dental, Law Firm, Salon"
                      className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Timezone
                    </label>
                    <select
                      value={formData.timezone}
                      onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                      className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden bg-white"
                    >
                      <option value="America/New_York">Eastern Time (US & Canada)</option>
                      <option value="America/Chicago">Central Time (US & Canada)</option>
                      <option value="America/Denver">Mountain Time (US & Canada)</option>
                      <option value="America/Los_Angeles">Pacific Time (US & Canada)</option>
                      <option value="Europe/London">London (GMT/BST)</option>
                      <option value="Asia/Kolkata">India (IST)</option>
                      <option value="UTC">UTC</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Transfer Phone Number
                    </label>
                    <input
                      type="text"
                      value={formData.transfer_number}
                      onChange={(e) => setFormData({ ...formData, transfer_number: e.target.value })}
                      placeholder="+1 (555) 234-5678"
                      className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                      Notification Email
                    </label>
                    <input
                      type="email"
                      value={formData.notification_email}
                      onChange={(e) => setFormData({ ...formData, notification_email: e.target.value })}
                      placeholder="frontdesk@mybusiness.com"
                      className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden"
                    />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Operating Hours */}
          {currentStep === 2 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 2: Business Operating Hours</h2>
                <p className="text-xs text-slate-500">
                  Your voice agent checks these hours to advise callers whether your office is open or closed.
                </p>
              </div>

              <div className="space-y-3">
                {formData.days.map((d, idx) => (
                  <div
                    key={d.key}
                    className="flex flex-col sm:flex-row sm:items-center justify-between p-3 rounded-lg border border-slate-200 gap-3"
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={!d.closed}
                        onChange={(e) => handleDayChange(idx, 'closed', !e.target.checked)}
                        className="rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                        id={`day-${d.key}`}
                      />
                      <label htmlFor={`day-${d.key}`} className="text-sm font-medium text-slate-900 w-24">
                        {d.label}
                      </label>
                    </div>

                    {!d.closed ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="time"
                          value={d.open}
                          onChange={(e) => handleDayChange(idx, 'open', e.target.value)}
                          className="px-2.5 py-1 text-xs border border-slate-200 rounded-md"
                        />
                        <span className="text-xs text-slate-400">to</span>
                        <input
                          type="time"
                          value={d.close}
                          onChange={(e) => handleDayChange(idx, 'close', e.target.value)}
                          className="px-2.5 py-1 text-xs border border-slate-200 rounded-md"
                        />
                      </div>
                    ) : (
                      <span className="text-xs text-slate-400 font-medium">Closed</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STEP 3: Services Catalog */}
          {currentStep === 3 && (
            <div className="space-y-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-bold text-slate-900">Step 3: Service Catalog</h2>
                  <p className="text-xs text-slate-500">
                    Add the services or consultation offerings your callers can book over the phone.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAddService}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Service
                </button>
              </div>

              <div className="space-y-3">
                {formData.services.map((svc, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-lg border border-slate-200 space-y-3 bg-slate-50/50"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <input
                        type="text"
                        placeholder="Service name (e.g., Dental Cleaning)"
                        value={svc.name}
                        onChange={(e) => handleServiceChange(idx, 'name', e.target.value)}
                        className="flex-1 px-3 py-1.5 bg-white border border-slate-200 rounded-md text-sm font-medium"
                      />
                      {formData.services.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveService(idx)}
                          className="text-slate-400 hover:text-red-600 p-1 rounded"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="text-[11px] text-slate-500 block mb-0.5">Duration (mins)</label>
                        <input
                          type="number"
                          min={5}
                          value={svc.duration_minutes}
                          onChange={(e) => handleServiceChange(idx, 'duration_minutes', e.target.value)}
                          className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-md text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] text-slate-500 block mb-0.5">Price ($)</label>
                        <input
                          type="number"
                          min={0}
                          value={svc.price}
                          onChange={(e) => handleServiceChange(idx, 'price', e.target.value)}
                          className="w-full px-3 py-1.5 bg-white border border-slate-200 rounded-md text-xs"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STEP 4: Voice Persona & Greeting */}
          {currentStep === 4 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 4: Voice Persona & Greeting</h2>
                <p className="text-xs text-slate-500">
                  Customize the first words your caller hears and the AI receptionist's tone of voice.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Greeting Message *
                  </label>
                  <textarea
                    rows={3}
                    value={formData.greeting}
                    onChange={(e) => setFormData({ ...formData, greeting: e.target.value })}
                    placeholder="Hello! Thanks for calling Acme Dental. How can I help you today?"
                    className="w-full px-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden"
                  />
                  <p className="text-[11px] text-slate-400 mt-1">
                    Spoken automatically when an inbound phone call connects.
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Personality Tone
                  </label>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { id: 'friendly', label: 'Friendly & Warm', desc: 'Approachable, cheerful, and welcoming' },
                      { id: 'professional', label: 'Professional & Direct', desc: 'Clear, concise, and businesslike' },
                      { id: 'empathetic', label: 'Empathetic & Gentle', desc: 'Calm, patient, ideal for healthcare' },
                    ].map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setFormData({ ...formData, tone: t.id })}
                        className={`p-3 rounded-lg border text-left transition-all ${
                          formData.tone === t.id
                            ? 'border-blue-600 bg-blue-50/50 ring-1 ring-blue-600'
                            : 'border-slate-200 hover:border-slate-300 bg-white'
                        }`}
                      >
                        <div className="font-semibold text-xs text-slate-900">{t.label}</div>
                        <div className="text-[11px] text-slate-500 mt-1">{t.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: Website Knowledge Ingestion */}
          {currentStep === 5 && (
            <div className="space-y-5">
              <div>
                <h2 className="text-lg font-bold text-slate-900">Step 5: Website Knowledge Ingestion</h2>
                <p className="text-xs text-slate-500">
                  Optional: Provide your public business website. Our crawler will automatically extract your FAQs, services, and policies for the receptionist.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1">
                    Website URL (Optional)
                  </label>
                  <div className="relative">
                    <Globe className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
                    <input
                      type="url"
                      value={formData.website_url}
                      onChange={(e) => setFormData({ ...formData, website_url: e.target.value })}
                      placeholder="https://www.example.com"
                      className="w-full pl-10 pr-3.5 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-600 focus:outline-hidden"
                    />
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1">
                    You can also upload PDFs and text snippets later from the Knowledge Base page.
                  </p>
                </div>

                <div className="p-4 bg-blue-50/60 rounded-xl border border-blue-200 text-xs text-blue-900 space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-blue-600" />
                    Ready to Launch
                  </div>
                  <p>
                    Clicking "Finish & Launch Test Agent" will initialize your business configuration and redirect you to the live interactive testing console.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Actions Bar */}
          <div className="mt-8 pt-5 border-t border-slate-100 flex items-center justify-between">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handleBack}
                disabled={loading}
                className="inline-flex items-center gap-1.5 px-4 py-2 border border-slate-200 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                Back
              </button>
            ) : (
              <div />
            )}

            {currentStep < 5 ? (
              <button
                type="button"
                onClick={handleNext}
                className="inline-flex items-center gap-1.5 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors shadow-xs"
              >
                Next Step
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading}
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 transition-colors shadow-xs disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Configuring Business...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-4 h-4" />
                    Finish & Launch Test Agent
                  </>
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

