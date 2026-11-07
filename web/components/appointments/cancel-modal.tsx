'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, AlertTriangle, Loader2 } from 'lucide-react';

interface CancelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  appointmentId: string;
  customerName: string;
  serviceName?: string;
  startAt?: string;
}

export function CancelModal({
  isOpen,
  onClose,
  onSuccess,
  appointmentId,
  customerName,
  serviceName,
  startAt,
}: CancelModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);

    try {
      await apiClient(`/api/appointments/${appointmentId}/cancel`, {
        method: 'POST',
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to cancel appointment');
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
            <h3 className="text-base font-bold text-slate-900">Cancel Appointment?</h3>
            <p className="text-xs text-slate-500 mt-1">
              Are you sure you want to cancel the appointment for{' '}
              <span className="font-semibold text-slate-800">{customerName}</span>?
            </p>
          </div>

          {(serviceName || startAt) && (
            <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-xs text-slate-600 text-left space-y-1">
              {serviceName && (
                <p>
                  Service: <span className="font-medium text-slate-800">{serviceName}</span>
                </p>
              )}
              {startAt && (
                <p>
                  Time: <span className="font-medium text-slate-800">{new Date(startAt).toLocaleString()}</span>
                </p>
              )}
            </div>
          )}

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
              Nevermind
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={loading}
              className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-semibold rounded-lg flex items-center shadow disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Yes, Cancel Booking
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

