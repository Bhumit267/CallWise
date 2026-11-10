'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, BookOpen, Loader2, MessageSquareQuote, Sparkles } from 'lucide-react';

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg bg-white brutal-border-3 brutal-shadow-xl overflow-hidden">
        {/* Header */}
        <div className="h-16 px-6 border-b-3 border-black flex items-center justify-between bg-[#ffe600]">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 bg-black text-[#ffe600] brutal-border flex items-center justify-center">
              <MessageSquareQuote className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-black text-black uppercase tracking-tight">Add Q&A Snippet</h3>
              <p className="text-xs font-bold text-slate-800">Direct Receptionist Knowledge Training</p>
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
              Question or Topic Title <span className="text-red-600">*</span>
            </label>
            <input
              type="text"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. What parking options are available for clients?"
              className="w-full px-3.5 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
            />
          </div>

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Answer or Guidance Content <span className="text-red-600">*</span>
            </label>
            <textarea
              required
              rows={5}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="e.g. Free validated parking is available in the garage directly behind our office building on 4th Street. Bring your ticket to the front desk."
              className="w-full px-3.5 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden resize-none"
            />
            <p className="text-[11px] font-bold text-slate-500 mt-1">
              Immediately chunked and embedded with vector search for sub-second retrieval.
            </p>
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
              Save & Ingest Snippet
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
