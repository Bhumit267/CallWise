'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, Mail, Shield, Loader2, Send } from 'lucide-react';
import { cn } from '@/lib/utils';

interface InviteMemberModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function InviteMemberModal({
  isOpen,
  onClose,
  onSuccess,
}: InviteMemberModalProps) {
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<'manager' | 'staff' | 'owner'>('staff');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await apiClient('/api/team/invites', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          role,
        }),
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to send invite');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-md bg-white brutal-border-3 brutal-shadow-xl overflow-hidden">
        {/* Header */}
        <div className="h-16 px-6 border-b-3 border-black flex items-center justify-between bg-[#ffe600]">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 bg-black text-[#ffe600] brutal-border flex items-center justify-center">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-black text-black uppercase tracking-tight">Invite Colleague</h3>
              <p className="text-xs font-bold text-slate-800">Team Collaboration Access</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 bg-black text-white brutal-border flex items-center justify-center hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-[#ff5a5a] text-black text-xs font-black brutal-border">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Email Address <span className="text-red-600">*</span>
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="colleague@company.com"
              className="w-full px-3.5 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Role & Permissions
            </label>
            <div className="space-y-2">
              {[
                { id: 'staff', name: 'Staff Member', desc: 'Can view inbox, calls, appointments, and manage follow-ups.' },
                { id: 'manager', name: 'Manager / Admin', desc: 'Can update business settings, operating hours, and manage knowledge.' },
                { id: 'owner', name: 'Business Owner', desc: 'Full tenant control, team invites, role edits, and GDPR deletion.' },
              ].map((r) => (
                <label
                  key={r.id}
                  className={cn(
                    'flex items-start space-x-3 p-3 brutal-border cursor-pointer transition-colors',
                    role === r.id ? 'bg-[#ffe600] text-black' : 'bg-white hover:bg-slate-50'
                  )}
                >
                  <input
                    type="radio"
                    name="role"
                    value={r.id}
                    checked={role === r.id}
                    onChange={() => setRole(r.id as any)}
                    className="w-4 h-4 text-black mt-0.5 accent-black cursor-pointer"
                  />
                  <div>
                    <p className="text-xs font-black uppercase tracking-wider">{r.name}</p>
                    <p className="text-[11px] font-bold text-slate-700">{r.desc}</p>
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-end space-x-3 pt-4 border-t-2 border-black">
            <button
              type="button"
              onClick={onClose}
              className="bg-white text-black font-black uppercase text-xs px-4 py-2.5 brutal-border brutal-shadow-hover"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="bg-[#2563eb] text-white font-black uppercase text-xs px-5 py-2.5 brutal-border brutal-shadow-hover flex items-center disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Send Invitation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
