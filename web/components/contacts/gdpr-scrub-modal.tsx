'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { AlertTriangle, Loader2 } from 'lucide-react';

interface GdprScrubModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  contactId: string;
  contactName?: string | null;
  phone: string;
}

export function GdprScrubModal({
  isOpen,
  onClose,
  onSuccess,
  contactId,
  contactName,
  phone,
}: GdprScrubModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);

    try {
      await apiClient(`/api/contacts/${contactId}/scrub`, {
        method: 'POST',
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to scrub contact data');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="p-6 text-center space-y-4">
          <div className="w-12 h-12 rounded-full bg-red-100 text-red-600 flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6" />
          </div>

          <div>
            <h3 className="text-base font-bold text-slate-900">
              Permanently Scrub Contact (GDPR / CCPA)?
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              This action cannot be undone. All personally identifiable information (PII) including name, phone number, and conversation linkages will be permanently scrubbed.
            </p>
          </div>

          <div className="p-3 bg-red-50 text-red-800 rounded-lg border border-red-200 text-xs text-left">
            <p className="font-semibold mb-1">Target Contact:</p>
            <p>Name: {contactName || 'Unregistered'}</p>
            <p>Phone: {phone}</p>
          </div>

          {error && (
            <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200 text-left">
              {error}
            </div>
          )}

          <div className="flex items-center justify-center space-x-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 rounded-lg font-medium"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={loading}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg flex items-center shadow disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Yes, Permanently Scrub
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

