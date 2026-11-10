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
  Zap,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { OnboardingSetupRequest, OnboardingSetupResponse } from '@/types/api';
import { useAuth } from '@/contexts/auth-context';
import { cn } from '@/lib/utils';

const STEPS = [
  { id: 1, title: 'Profile', icon: Building2 },
  { id: 2, title: 'Hours', icon: Clock },
  { id: 3, title: 'Services', icon: Briefcase },
  { id: 4, title: 'Persona', icon: Bot },
  { id: 5, title: 'Website', icon: Globe },
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
    <div className="min-h-screen bg-[#fbfaf6] py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto space-y-8">
        {/* Header Banner */}
        <div className="bg-white brutal-border-3 brutal-shadow-lg p-6 text-center space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#ffe600] text-black text-xs font-black uppercase tracking-wider brutal-border">
            <Zap className="w-3.5 h-3.5 fill-black" />
            <span>5-Minute Quick Setup</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-black uppercase tracking-tight">
            Launch Your AI Receptionist
          </h1>
          <p className="text-sm font-bold text-slate-700 max-w-xl mx-auto">
            Configure business hours, callable services, and your custom voice persona to start handling 24/7 calls and bookings.
          </p>
        </div>

        {/* Stepper Progress Bar */}
        <div className="bg-white brutal-border-3 brutal-shadow p-4">
          <div className="flex items-center justify-between">
            {STEPS.map((step, idx) => {
              const Icon = step.icon;
              const isPassed = currentStep > step.id;
              const isCurrent = currentStep === step.id;

              return (
                <div key={step.id} className="flex-1 flex items-center">
                  <div className="flex flex-col items-center flex-1">
                    <button
                      type="button"
                      onClick={() => isPassed && setCurrentStep(step.id)}
                      disabled={!isPassed}
                      className={cn(
                        'w-10 h-10 flex items-center justify-center text-xs font-black brutal-border transition-all',
                        isPassed
                          ? 'bg-black text-[#ffe600] cursor-pointer hover:bg-slate-800'
                          : isCurrent
                          ? 'bg-[#ffe600] text-black brutal-shadow-sm scale-110'
                          : 'bg-slate-100 text-slate-400 border-slate-300'
                      )}
                    >
                      {isPassed ? <CheckCircle2 className="w-5 h-5" /> : <Icon className="w-5 h-5" />}
                    </button>
                    <span
                      className={cn(
                        'text-[10px] font-black uppercase tracking-wider mt-2 hidden sm:block',
                        isCurrent ? 'text-black' : isPassed ? 'text-black' : 'text-slate-400'
                      )}
                    >
                      {step.title}
                    </span>
                  </div>
                  {idx < STEPS.length - 1 && (
                    <div
                      className={cn(
                        'h-1 flex-1 transition-colors',
                        currentStep > step.id ? 'bg-black' : 'bg-slate-200'
                      )}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Form Body Card */}
        <div className="bg-white brutal-border-3 brutal-shadow-xl p-6 sm:p-8">
          {error && (
            <div className="mb-6 p-4 bg-[#ff5a5a] text-black brutal-border-3 brutal-shadow-sm flex items-center gap-3">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <span className="font-black text-sm">{error}</span>
            </div>
          )}

          {/* STEP 1: Business Profile */}
          {currentStep === 1 && (
            <div className="space-y-6">
              <div className="border-b-2 border-black pb-3">
                <span className="bg-[#ffe600] px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
                  Step 1 of 5
                </span>
                <h2 className="text-xl font-black text-black uppercase tracking-tight mt-2">
                  Business Identity & Timezone
                </h2>
                <p className="text-xs font-bold text-slate-600">
                  Core identity details used by the AI agent when introducing itself.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                    Business Name *
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. Apex Health Clinic or Summit Legal Group"
                    className="w-full px-4 py-3 bg-[#fbfaf6] brutal-border-3 font-bold text-sm focus:bg-white focus:outline-hidden"
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                      Industry / Category
                    </label>
                    <input
                      type="text"
                      value={formData.business_type}
                      onChange={(e) => setFormData({ ...formData, business_type: e.target.value })}
                      placeholder="e.g. Dental, Law Firm, Salon"
                      className="w-full px-4 py-3 bg-[#fbfaf6] brutal-border-3 font-bold text-sm focus:bg-white focus:outline-hidden"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                      Timezone
                    </label>
                    <select
                      value={formData.timezone}
                      onChange={(e) => setFormData({ ...formData, timezone: e.target.value })}
                      className="w-full px-4 py-3 bg-[#fbfaf6] brutal-border-3 font-black text-sm focus:bg-white focus:outline-hidden"
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
                    <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                      Live Transfer Number
                    </label>
                    <input
                      type="text"
                      value={formData.transfer_number}
                      onChange={(e) => setFormData({ ...formData, transfer_number: e.target.value })}
                      placeholder="+1 (555) 234-5678"
                      className="w-full px-4 py-3 bg-[#fbfaf6] brutal-border-3 font-bold text-sm focus:bg-white focus:outline-hidden"
                    />
                    <p className="text-[11px] font-bold text-slate-500 mt-1">
                      Target number if caller requests human transfer.
                    </p>
                  </div>

                  <div>
                    <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                      Notification Email
                    </label>
                    <input
                      type="email"
                      value={formData.notification_email}
                      onChange={(e) => setFormData({ ...formData, notification_email: e.target.value })}
                      placeholder="frontdesk@mybusiness.com"
                      className="w-full px-4 py-3 bg-[#fbfaf6] brutal-border-3 font-bold text-sm focus:bg-white focus:outline-hidden"
                    />
                    <p className="text-[11px] font-bold text-slate-500 mt-1">
                      Receives urgent call summaries & follow-up alerts.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Operating Hours */}
          {currentStep === 2 && (
            <div className="space-y-6">
              <div className="border-b-2 border-black pb-3">
                <span className="bg-[#ffe600] px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
                  Step 2 of 5
                </span>
                <h2 className="text-xl font-black text-black uppercase tracking-tight mt-2">
                  Operating Hours & Availability
                </h2>
                <p className="text-xs font-bold text-slate-600">
                  The AI uses these windows to inform callers whether you are open or closed right now.
                </p>
              </div>

              <div className="space-y-3">
                {formData.days.map((d, idx) => (
                  <div
                    key={d.key}
                    className={cn(
                      'flex flex-col sm:flex-row sm:items-center justify-between p-3.5 brutal-border-3 gap-3 transition-colors',
                      d.closed ? 'bg-slate-100 opacity-70' : 'bg-[#fbfaf6]'
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <input
                        type="checkbox"
                        checked={!d.closed}
                        onChange={(e) => handleDayChange(idx, 'closed', !e.target.checked)}
                        className="w-5 h-5 brutal-border text-black rounded-none cursor-pointer"
                        id={`day-${d.key}`}
                      />
                      <label htmlFor={`day-${d.key}`} className="text-sm font-black uppercase tracking-wider text-black w-28 cursor-pointer">
                        {d.label}
                      </label>
                    </div>

                    {!d.closed ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="time"
                          value={d.open}
                          onChange={(e) => handleDayChange(idx, 'open', e.target.value)}
                          className="px-3 py-1.5 bg-white brutal-border font-black text-xs"
                        />
                        <span className="text-xs font-black uppercase text-black">to</span>
                        <input
                          type="time"
                          value={d.close}
                          onChange={(e) => handleDayChange(idx, 'close', e.target.value)}
                          className="px-3 py-1.5 bg-white brutal-border font-black text-xs"
                        />
                      </div>
                    ) : (
                      <span className="bg-black text-white px-3 py-1 text-xs font-black uppercase brutal-border">
                        Closed
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* STEP 3: Services Catalog */}
          {currentStep === 3 && (
            <div className="space-y-6">
              <div className="border-b-2 border-black pb-3 flex items-center justify-between">
                <div>
                  <span className="bg-[#ffe600] px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
                    Step 3 of 5
                  </span>
                  <h2 className="text-xl font-black text-black uppercase tracking-tight mt-2">
                    Service Catalog Offerings
                  </h2>
                  <p className="text-xs font-bold text-slate-600">
                    Appointments the AI can book directly into your calendar.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handleAddService}
                  className="bg-[#2563eb] text-white font-black text-xs uppercase px-3 py-2 brutal-border brutal-shadow-hover flex items-center gap-1.5"
                >
                  <Plus className="w-4 h-4" />
                  Add Service
                </button>
              </div>

              <div className="space-y-4">
                {formData.services.map((svc, idx) => (
                  <div
                    key={idx}
                    className="p-4 bg-[#fbfaf6] brutal-border-3 brutal-shadow-sm space-y-3"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <input
                        type="text"
                        placeholder="Service name (e.g. Dental Cleaning, Consultation)"
                        value={svc.name}
                        onChange={(e) => handleServiceChange(idx, 'name', e.target.value)}
                        className="flex-1 px-3 py-2 bg-white brutal-border font-black text-sm"
                      />
                      {formData.services.length > 1 && (
                        <button
                          type="button"
                          onClick={() => handleRemoveService(idx)}
                          className="bg-[#ff5a5a] text-black p-2 brutal-border hover:bg-red-400"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-[11px] font-black uppercase text-black block mb-1">
                          Duration (Mins)
                        </label>
                        <input
                          type="number"
                          min={5}
                          value={svc.duration_minutes}
                          onChange={(e) => handleServiceChange(idx, 'duration_minutes', e.target.value)}
                          className="w-full px-3 py-1.5 bg-white brutal-border font-black text-xs"
                        />
                      </div>
                      <div>
                        <label className="text-[11px] font-black uppercase text-black block mb-1">
                          Price ($ USD)
                        </label>
                        <input
                          type="number"
                          min={0}
                          value={svc.price}
                          onChange={(e) => handleServiceChange(idx, 'price', e.target.value)}
                          className="w-full px-3 py-1.5 bg-white brutal-border font-black text-xs"
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
            <div className="space-y-6">
              <div className="border-b-2 border-black pb-3">
                <span className="bg-[#ffe600] px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
                  Step 4 of 5
                </span>
                <h2 className="text-xl font-black text-black uppercase tracking-tight mt-2">
                  Voice Greeting & Persona
                </h2>
                <p className="text-xs font-bold text-slate-600">
                  Customize the first sentence spoken when callers pick up and the conversational tone.
                </p>
              </div>

              <div className="space-y-5">
                <div>
                  <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                    Greeting Message *
                  </label>
                  <textarea
                    rows={3}
                    value={formData.greeting}
                    onChange={(e) => setFormData({ ...formData, greeting: e.target.value })}
                    placeholder="Hello! Thanks for calling Acme Dental. How can I help you today?"
                    className="w-full px-4 py-3 bg-[#fbfaf6] brutal-border-3 font-bold text-sm focus:bg-white focus:outline-hidden"
                  />
                  <p className="text-[11px] font-bold text-slate-500 mt-1">
                    Spoken automatically within 1.2s of connection.
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-black text-black uppercase tracking-wider mb-2">
                    Personality Tone
                  </label>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {[
                      { id: 'friendly', label: 'Friendly & Warm', desc: 'Cheerfully helpful and conversational' },
                      { id: 'professional', label: 'Professional & Direct', desc: 'Clear, concise, and businesslike' },
                      { id: 'empathetic', label: 'Empathetic & Gentle', desc: 'Patient, calm, ideal for healthcare' },
                    ].map((t) => (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setFormData({ ...formData, tone: t.id })}
                        className={cn(
                          'p-4 brutal-border-3 text-left transition-all',
                          formData.tone === t.id
                            ? 'bg-[#ffe600] text-black brutal-shadow'
                            : 'bg-white hover:bg-slate-50'
                        )}
                      >
                        <div className="font-black text-xs uppercase tracking-wider text-black">{t.label}</div>
                        <div className="text-[11px] font-bold text-slate-700 mt-1.5">{t.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 5: Website Knowledge Ingestion */}
          {currentStep === 5 && (
            <div className="space-y-6">
              <div className="border-b-2 border-black pb-3">
                <span className="bg-[#ffe600] px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
                  Step 5 of 5
                </span>
                <h2 className="text-xl font-black text-black uppercase tracking-tight mt-2">
                  Knowledge Ingestion & Finalize
                </h2>
                <p className="text-xs font-bold text-slate-600">
                  Optional: Provide your website URL to automatically crawl FAQs and clinic background.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-black text-black uppercase tracking-wider mb-1.5">
                    Website URL (Optional)
                  </label>
                  <div className="relative">
                    <Globe className="w-5 h-5 text-black absolute left-3.5 top-3.5" />
                    <input
                      type="url"
                      value={formData.website_url}
                      onChange={(e) => setFormData({ ...formData, website_url: e.target.value })}
                      placeholder="https://www.example.com"
                      className="w-full pl-11 pr-4 py-3 bg-[#fbfaf6] brutal-border-3 font-bold text-sm focus:bg-white focus:outline-hidden"
                    />
                  </div>
                  <p className="text-[11px] font-bold text-slate-500 mt-1">
                    You can also upload PDFs and text snippets anytime from the Knowledge Base.
                  </p>
                </div>

                <div className="p-4 bg-[#fef9c3] brutal-border-3 brutal-shadow-sm text-xs text-black space-y-1">
                  <div className="font-black uppercase tracking-wide flex items-center gap-1.5">
                    <Sparkles className="w-4 h-4 text-black fill-black" />
                    Ready for Live Testing
                  </div>
                  <p className="font-bold">
                    Finishing will save your business profile and launch the interactive Test Agent console so you can converse with your new receptionist immediately.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Navigation Action Buttons */}
          <div className="mt-8 pt-6 border-t-2 border-black flex items-center justify-between">
            {currentStep > 1 ? (
              <button
                type="button"
                onClick={handleBack}
                disabled={loading}
                className="bg-white text-black font-black text-xs uppercase px-5 py-2.5 brutal-border-3 brutal-shadow-hover flex items-center gap-2"
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
                className="bg-[#ffe600] text-black font-black text-xs uppercase px-6 py-2.5 brutal-border-3 brutal-shadow-hover flex items-center gap-2"
              >
                Next Step
                <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSubmit}
                disabled={loading}
                className="bg-[#2563eb] text-white font-black text-xs uppercase px-6 py-3 brutal-border-3 brutal-shadow-hover flex items-center gap-2 disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Initializing Receptionist...
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
