'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, BookOpen, Loader2, MessageSquareQuote } from 'lucide-react';

interface AddSnippetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function AddSnippetModal({
  isOpen,
  onClose,
  onSuccess,
}: AddSnippetModalProps) {
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !content.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await apiClient('/api/knowledge/qa', {
        method: 'POST',
        body: JSON.stringify({
          title: title.trim(),
          content: content.trim(),
        }),
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to add knowledge snippet');
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
              <MessageSquareQuote className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Add Q&A Knowledge Snippet</h3>
              <p className="text-xs text-slate-500">Train your voice receptionist directly</p>
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

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Question or Topic Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. What parking options are available for clients?"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Answer or Guidance Content <span className="text-red-500">*</span>
            </label>
            <textarea
              required
              rows={5}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="e.g. Free validated parking is available in the garage directly behind our office building on 4th Street. Bring your ticket to the front desk."
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 resize-none"
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Content is immediately chunked and embedded into the vector database.
            </p>
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
              Save & Ingest Snippet
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

