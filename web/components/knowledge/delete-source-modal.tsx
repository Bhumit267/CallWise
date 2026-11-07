'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { AlertTriangle, Loader2 } from 'lucide-react';

interface DeleteSourceModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  sourceId: string;
  title: string;
  chunkCount: number;
}

export function DeleteSourceModal({
  isOpen,
  onClose,
  onSuccess,
  sourceId,
  title,
  chunkCount,
}: DeleteSourceModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);

    try {
      await apiClient(`/api/knowledge/sources/${sourceId}`, {
        method: 'DELETE',
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to delete knowledge source');
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
            <h3 className="text-base font-bold text-slate-900">Delete Knowledge Source?</h3>
            <p className="text-xs text-slate-500 mt-1">
              Are you sure you want to remove{' '}
              <span className="font-semibold text-slate-800">"{title}"</span>?
            </p>
          </div>

          <p className="text-xs text-slate-600 bg-slate-50 p-3 rounded-lg border border-slate-200 text-left">
            This will permanently remove this document and all{' '}
            <span className="font-semibold">{chunkCount}</span> vector embedding chunks from the AI receptionist's search index.
          </p>

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
              Delete Source
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

