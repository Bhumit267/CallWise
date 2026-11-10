'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { PhoneNumberItem, PhoneNumberCreate } from '@/types/api';
import {
  PhoneCall,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  HelpCircle,
  Loader2,
  Radio,
  Server,
  ShieldCheck,
  Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function PhoneNumbersPage() {
  const [numbers, setNumbers] = useState<PhoneNumberItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal state
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState<PhoneNumberCreate>({
    e164_number: '',
    provider: 'livekit',
    label: 'Main Inbound',
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const fetchNumbers = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient<PhoneNumberItem[]>('/api/phone-numbers');
      setNumbers(res || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load phone numbers');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNumbers();
  }, [fetchNumbers]);

  const handleToggleActive = async (num: PhoneNumberItem) => {
    try {
      await apiClient(`/api/phone-numbers/${num.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: !num.is_active }),
      });
      setNumbers((prev) =>
        prev.map((n) => (n.id === num.id ? { ...n, is_active: !n.is_active } : n))
      );
    } catch (err: any) {
      alert(err.message || 'Failed to update phone number status');
    }
  };

  const handleDelete = async (id: string, e164: string) => {
    if (!confirm(`Are you sure you want to remove ${e164}? Incoming calls to this number will no longer be routed to your business.`)) {
      return;
    }
    try {
      await apiClient(`/api/phone-numbers/${id}`, { method: 'DELETE' });
      setNumbers((prev) => prev.filter((n) => n.id !== id));
    } catch (err: any) {
      alert(err.message || 'Failed to delete phone number');
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setFormError(null);
    try {
      const created = await apiClient<PhoneNumberItem>('/api/phone-numbers', {
        method: 'POST',
        body: JSON.stringify(formData),
      });
      setNumbers((prev) => [...prev, created]);
      setIsModalOpen(false);
      setFormData({
        e164_number: '',
        provider: 'livekit',
        label: 'Main Inbound',
        is_active: true,
      });
    } catch (err: any) {
      setFormError(err.message || 'Failed to add phone number');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-black uppercase tracking-tight text-black flex items-center">
              <PhoneCall className="w-6 h-6 mr-2 text-black" /> Phone Numbers & SIP
            </h1>
            <span className="bg-[#a3e635] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Telephony
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Manage your inbound phone numbers and LiveKit SIP telephony routing.
          </p>
        </div>
        <button
          onClick={() => {
            setFormError(null);
            setIsModalOpen(true);
          }}
          className="inline-flex items-center px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition"
        >
          <Plus className="w-4 h-4 mr-2" /> Add Phone Number
        </button>
      </div>

      {/* Numbers List Table */}
      <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
        <div className="px-6 py-4 border-b-2 border-black flex items-center justify-between bg-neutral-50">
          <h2 className="text-sm font-black uppercase text-black">Assigned Inbound Numbers</h2>
          <span className="text-xs font-mono font-bold text-neutral-600 bg-white px-2 py-0.5 rounded brutal-border">
            {numbers.length} {numbers.length === 1 ? 'Number' : 'Numbers'}
          </span>
        </div>

        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center text-black space-y-3">
            <Loader2 className="w-8 h-8 animate-spin text-black" />
            <p className="text-xs font-bold uppercase">Loading phone numbers...</p>
          </div>
        ) : error ? (
          <div className="p-6">
            <div className="p-4 bg-rose-100 text-rose-950 rounded-xl text-xs font-black uppercase border-2 border-black">
              {error}
            </div>
          </div>
        ) : numbers.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-[#dbeafe] text-black brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
              <Radio className="w-7 h-7 stroke-[2.5]" />
            </div>
            <h3 className="text-base font-black uppercase text-black">No phone numbers assigned</h3>
            <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
              Add your first E.164 telephone number (e.g. +15551234567) to start receiving calls via LiveKit SIP.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-neutral-100 text-black border-b-2 border-black text-xs font-black uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Phone Number</th>
                  <th className="px-6 py-3.5">Label</th>
                  <th className="px-6 py-3.5">Provider</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y-2 divide-black/10">
                {numbers.map((n) => (
                  <tr key={n.id} className="hover:bg-amber-50/40 transition-colors">
                    <td className="px-6 py-4 font-mono font-black text-black">
                      {n.e164_number}
                    </td>
                    <td className="px-6 py-4 text-black font-bold">{n.label}</td>
                    <td className="px-6 py-4">
                      <span className="brutal-badge bg-[#dbeafe] text-blue-950">
                        {n.provider}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleToggleActive(n)}
                        className={cn(
                          'inline-flex items-center px-3 py-1 rounded-lg text-xs font-black uppercase tracking-wider brutal-border transition-all',
                          n.is_active
                            ? 'bg-[#dcfce7] text-emerald-950 brutal-shadow-xs'
                            : 'bg-neutral-100 text-neutral-500'
                        )}
                      >
                        {n.is_active ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-700" /> Active
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3.5 h-3.5 mr-1 text-neutral-400" /> Inactive
                          </>
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(n.id, n.e164_number)}
                        className="p-1.5 text-neutral-500 hover:text-rose-600 rounded-lg hover:bg-rose-50 transition"
                        title="Delete phone number"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Telephony Setup Guide Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg space-y-3">
          <div className="w-9 h-9 rounded-xl bg-[#ffe600] text-black brutal-border brutal-shadow-xs flex items-center justify-center font-black">
            1
          </div>
          <h3 className="font-black text-black text-sm uppercase">LiveKit Cloud SIP</h3>
          <p className="text-xs font-semibold text-neutral-600 leading-relaxed">
            Purchase a US phone number directly inside your LiveKit Cloud dashboard under SIP trunks. Set the inbound dispatch rule to route to your Callwise worker.
          </p>
        </div>

        <div className="bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg space-y-3">
          <div className="w-9 h-9 rounded-xl bg-[#f3e8ff] text-black brutal-border brutal-shadow-xs flex items-center justify-center font-black">
            2
          </div>
          <h3 className="font-black text-black text-sm uppercase">Bring-Your-Own Twilio</h3>
          <p className="text-xs font-semibold text-neutral-600 leading-relaxed">
            Use any existing Twilio number. Create an Elastic SIP Trunk pointing to your LiveKit SIP domain with username/password authentication credentials.
          </p>
        </div>

        <div className="bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg space-y-3">
          <div className="w-9 h-9 rounded-xl bg-[#dcfce7] text-black brutal-border brutal-shadow-xs flex items-center justify-center font-black">
            3
          </div>
          <h3 className="font-black text-black text-sm uppercase">Free Softphone Testing</h3>
          <p className="text-xs font-semibold text-neutral-600 leading-relaxed">
            Test inbound calls for $0 using a free desktop SIP client (like Linphone, MicroSIP or Zoiper) pointing directly to your LiveKit SIP dispatcher URI.
          </p>
        </div>
      </div>

      {/* Add Number Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b-2 border-black flex items-center justify-between bg-neutral-50">
              <h3 className="text-base font-black uppercase text-black">Add Inbound Phone Number</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-black font-black text-lg hover:text-neutral-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-100 text-rose-950 rounded-xl text-xs font-black uppercase border-2 border-black brutal-shadow-xs">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                  E.164 Phone Number
                </label>
                <input
                  type="text"
                  required
                  placeholder="+15551234567"
                  value={formData.e164_number}
                  onChange={(e) => setFormData({ ...formData, e164_number: e.target.value })}
                  className="brutal-input font-mono"
                />
                <p className="text-[11px] font-mono text-neutral-500 mt-1">
                  Must include country code (e.g. +1 for US/Canada).
                </p>
              </div>

              <div>
                <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                  Label / Description
                </label>
                <input
                  type="text"
                  required
                  placeholder="Main Office Line"
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  className="brutal-input"
                />
              </div>

              <div>
                <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                  Provider
                </label>
                <select
                  value={formData.provider}
                  onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                  className="brutal-input cursor-pointer"
                >
                  <option value="livekit">LiveKit Inbound SIP</option>
                  <option value="twilio">Twilio SIP Trunk</option>
                  <option value="sip">Generic SIP Trunk / Softphone</option>
                </select>
              </div>

              <div className="flex items-center space-x-2 pt-2">
                <input
                  type="checkbox"
                  id="is_active_checkbox"
                  checked={formData.is_active}
                  onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                  className="w-4 h-4 rounded brutal-border accent-black"
                />
                <label htmlFor="is_active_checkbox" className="text-xs font-black text-black">
                  Immediately route incoming calls to this business
                </label>
              </div>

              <div className="pt-4 border-t-2 border-black flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 bg-white brutal-border rounded-xl text-xs font-black uppercase text-black hover:bg-neutral-100 brutal-shadow-xs"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover flex items-center"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                  Save Phone Number
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
