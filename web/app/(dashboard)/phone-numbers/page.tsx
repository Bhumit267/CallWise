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
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center">
            <PhoneCall className="w-6 h-6 mr-2.5 text-blue-600" /> Phone Numbers
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Manage your inbound phone numbers and LiveKit SIP telephony routing.
          </p>
        </div>
        <button
          onClick={() => {
            setFormError(null);
            setIsModalOpen(true);
          }}
          className="inline-flex items-center px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
        >
          <Plus className="w-4 h-4 mr-2" /> Add Phone Number
        </button>
      </div>

      {/* Numbers List Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-800">Assigned Inbound Numbers</h2>
          <span className="text-xs text-slate-400 font-medium">
            {numbers.length} {numbers.length === 1 ? 'Number' : 'Numbers'} Configured
          </span>
        </div>

        {loading ? (
          <div className="py-16 flex flex-col items-center justify-center text-slate-400 space-y-3">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
            <p className="text-sm">Loading phone numbers...</p>
          </div>
        ) : error ? (
          <div className="p-6">
            <div className="p-4 bg-red-50 text-red-700 rounded-lg text-sm border border-red-200">
              {error}
            </div>
          </div>
        ) : numbers.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <Radio className="w-10 h-10 text-slate-300 mx-auto" />
            <h3 className="text-sm font-semibold text-slate-700">No phone numbers assigned</h3>
            <p className="text-xs text-slate-400 max-w-sm mx-auto">
              Add your first E.164 telephone number (e.g., +15551234567) to start receiving calls via LiveKit SIP.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/80 text-slate-500 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Phone Number</th>
                  <th className="px-6 py-3.5">Label</th>
                  <th className="px-6 py-3.5">Provider</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {numbers.map((n) => (
                  <tr key={n.id} className="hover:bg-slate-50/50 transition">
                    <td className="px-6 py-4 font-mono font-medium text-slate-900">
                      {n.e164_number}
                    </td>
                    <td className="px-6 py-4 text-slate-700 font-medium">{n.label}</td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 uppercase">
                        {n.provider}
                      </span>
                    </td>
                    <td className="px-6 py-4">
                      <button
                        onClick={() => handleToggleActive(n)}
                        className={cn(
                          'inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold transition',
                          n.is_active
                            ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100'
                            : 'bg-slate-100 text-slate-500 border border-slate-200 hover:bg-slate-200'
                        )}
                      >
                        {n.is_active ? (
                          <>
                            <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-600" /> Active
                          </>
                        ) : (
                          <>
                            <XCircle className="w-3.5 h-3.5 mr-1 text-slate-400" /> Inactive
                          </>
                        )}
                      </button>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        onClick={() => handleDelete(n.id, n.e164_number)}
                        className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-red-50 transition"
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
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center font-bold">
            1
          </div>
          <h3 className="font-bold text-slate-900 text-sm">LiveKit Cloud Telephony</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Purchase a US phone number directly inside your LiveKit Cloud dashboard under SIP trunks. Set the inbound dispatch rule to route to your Callwise SIP URI.
          </p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center font-bold">
            2
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Bring-Your-Own Twilio Trunk</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Use a Twilio trial or production number. Create an Elastic SIP Trunk in Twilio pointing to your LiveKit SIP domain with username/password authentication.
          </p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center font-bold">
            3
          </div>
          <h3 className="font-bold text-slate-900 text-sm">Free Softphone Testing</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Test inbound calls for $0 using a free desktop SIP client (like Linphone, MicroSIP or Zoiper) pointing directly to your LiveKit SIP dispatcher.
          </p>
        </div>
      </div>

      {/* Add Number Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Add Inbound Phone Number</h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg text-xs border border-red-200">
                  {formError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  E.164 Phone Number
                </label>
                <input
                  type="text"
                  required
                  placeholder="+15551234567"
                  value={formData.e164_number}
                  onChange={(e) => setFormData({ ...formData, e164_number: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <p className="text-[11px] text-slate-400 mt-1">
                  Must include country code (e.g. +1 for US/Canada).
                </p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Label / Description
                </label>
                <input
                  type="text"
                  required
                  placeholder="Main Office Line"
                  value={formData.label}
                  onChange={(e) => setFormData({ ...formData, label: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
                  Provider
                </label>
                <select
                  value={formData.provider}
                  onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
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
                  className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                />
                <label htmlFor="is_active_checkbox" className="text-xs font-medium text-slate-700">
                  Immediately route incoming calls to this business
                </label>
              </div>

              <div className="pt-4 border-t border-slate-100 flex items-center justify-end space-x-3">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-slate-200 hover:bg-slate-50 text-slate-700 text-sm font-semibold rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition flex items-center"
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
