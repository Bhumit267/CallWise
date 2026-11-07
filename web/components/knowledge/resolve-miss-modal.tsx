'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, HelpCircle, Sparkles, Loader2, CheckCircle2 } from 'lucide-react';

interface ResolveMissModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  missId: string;
  query: string;
  count?: number;
}

export function ResolveMissModal({
  isOpen,
  onClose,
  onSuccess,
  missId,
  query,
  count = 1,
}: ResolveMissModalProps) {
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!answer.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await apiClient(`/api/knowledge-misses/${missId}/resolve`, {
        method: 'POST',
        body: JSON.stringify({
          answer: answer.trim(),
        }),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to resolve question');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Resolve Knowledge Gap</h3>
              <p className="text-xs text-slate-500">
                Asked {count} time{count !== 1 ? 's' : ''} by callers
              </p>
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

          <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-1">
            <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider flex items-center">
              <HelpCircle className="w-3.5 h-3.5 mr-1 text-slate-400" /> Caller Question
            </span>
            <p className="text-sm font-semibold text-slate-800">"{query}"</p>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Your Answer / Training Guidance <span className="text-red-500">*</span>
            </label>
            <textarea
              required
              rows={4}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="e.g. Yes, we offer emergency appointments on Saturdays between 10am and 2pm. Callers can schedule by pressing 1."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 resize-none"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Providing this answer immediately creates an ingested Q&A vector snippet and marks all {count} matching question instance(s) as resolved.
            </p>
          </div>

          <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-100">
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 rounded-lg font-medium"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading || !answer.trim()}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg flex items-center shadow disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Save & Train Receptionist
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
