'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, Shield, Loader2 } from 'lucide-react';

interface EditRoleModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  userId: string;
  userName: string;
  currentRole: string;
}

export function EditRoleModal({
  isOpen,
  onClose,
  onSuccess,
  userId,
  userName,
  currentRole,
}: EditRoleModalProps) {
  const [role, setRole] = useState(currentRole);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await apiClient(`/api/team/members/${userId}`, {
        method: 'PATCH',
        body: JSON.stringify({ role }),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to update member role');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center">
              <Shield className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Change Member Role</h3>
              <p className="text-xs text-slate-500">{userName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/60"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200">
              {error}
            </div>
          )}

          <div className="space-y-2">
            {[
              { id: 'staff', name: 'Staff Member', desc: 'Can view inbox, calls, appointments, and manage follow-ups.' },
              { id: 'manager', name: 'Manager / Admin', desc: 'Can update business settings, operating hours, and manage knowledge.' },
              { id: 'owner', name: 'Business Owner', desc: 'Full tenant control, team invites, role edits, and GDPR deletion.' },
            ].map((r) => (
              <label
                key={r.id}
                className="flex items-start space-x-3 p-3 rounded-xl border border-slate-200 hover:bg-slate-50 cursor-pointer"
              >
                <input
                  type="radio"
                  name="edit-role"
                  value={r.id}
                  checked={role === r.id}
                  onChange={() => setRole(r.id)}
                  className="w-4 h-4 text-blue-600 mt-0.5"
                />
                <div>
                  <p className="text-xs font-bold text-slate-900">{r.name}</p>
                  <p className="text-[11px] text-slate-500">{r.desc}</p>
                </div>
              </label>
            ))}
          </div>

          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 rounded-lg font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg flex items-center shadow disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Save Role
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

