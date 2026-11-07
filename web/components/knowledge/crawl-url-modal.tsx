'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, Globe, CheckCircle2, Loader2, ShieldCheck } from 'lucide-react';

interface CrawlUrlModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function CrawlUrlModal({
  isOpen,
  onClose,
  onSuccess,
}: CrawlUrlModalProps) {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  if (!isOpen) return null;

  const pollJob = async (id: string) => {
    try {
      const job = await apiClient(`/api/knowledge/jobs/${id}`);
      setJobStatus(job.status);

      if (job.status === 'completed') {
        setLoading(false);
        onSuccess();
        setTimeout(() => {
          onClose();
        }, 1200);
      } else if (job.status === 'failed') {
        setLoading(false);
        setError(job.error || 'Crawl job failed');
      } else {
        setTimeout(() => pollJob(id), 1500);
      }
    } catch (err: any) {
      setLoading(false);
      setError(err.message || 'Error tracking crawl job');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;

    setLoading(true);
    setError(null);
    setJobStatus('validating');

    try {
      const res = await apiClient<{ job_id: string; status: string }>(
        '/api/knowledge/url',
        {
          method: 'POST',
          body: JSON.stringify({
            url: url.trim(),
            title: title.trim() || undefined,
          }),
        }
      );

      setJobStatus(res.status);
      pollJob(res.job_id);
    } catch (err: any) {
      setLoading(false);
      setError(err.message || 'Failed to queue URL crawl');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center">
              <Globe className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Crawl & Ingest Website</h3>
              <p className="text-xs text-slate-500">Train from company website or FAQ pages</p>
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
              Public Website URL <span className="text-red-500">*</span>
            </label>
            <input
              type="url"
              required
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/about-us"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Knowledge Source Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Company Website - About & Services"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>

          <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-start space-x-2 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
            <span>
              SSRF validation automatically checks target hosts. Private, internal, and localhost IP addresses are blocked for tenant safety.
            </span>
          </div>

          {jobStatus && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
              <span className="text-slate-600 font-medium">Crawl Status:</span>
              <span className="font-semibold text-blue-600 capitalize flex items-center">
                {jobStatus === 'completed' ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mr-1" /> Complete
                  </>
                ) : (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin mr-1 text-blue-600" />{' '}
                    {jobStatus}
                  </>
                )}
              </span>
            </div>
          )}

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
              disabled={loading}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg flex items-center shadow disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Start Website Ingestion
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

