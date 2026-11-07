'use client';

import React, { useState } from 'react';
import { apiClient } from '@/lib/api';
import { X, UploadCloud, FileText, CheckCircle2, Loader2, AlertCircle } from 'lucide-react';

interface UploadDocumentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function UploadDocumentModal({
  isOpen,
  onClose,
  onSuccess,
}: UploadDocumentModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, ''));
      }
    }
  };

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
        setError(job.error || 'Ingestion job failed');
      } else {
        // Continue polling
        setTimeout(() => pollJob(id), 1500);
      }
    } catch (err: any) {
      setLoading(false);
      setError(err.message || 'Error tracking ingestion job');
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a file to upload.');
      return;
    }

    setLoading(true);
    setError(null);
    setJobStatus('uploading');

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (title.trim()) {
        formData.append('title', title.trim());
      }

      const res = await apiClient<{ job_id: string; status: string }>(
        `/api/knowledge/upload${title.trim() ? `?title=${encodeURIComponent(title.trim())}` : ''}`,
        {
          method: 'POST',
          body: formData,
        }
      );

      setJobId(res.job_id);
      setJobStatus(res.status);
      pollJob(res.job_id);
    } catch (err: any) {
      setLoading(false);
      setError(err.message || 'Failed to upload document');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-sm p-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden">
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-900">Upload Knowledge File</h3>
              <p className="text-xs text-slate-500">PDF, TXT, or Markdown documents</p>
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
              Select Document (.pdf, .txt, .md, max 10MB) <span className="text-red-500">*</span>
            </label>
            <div className="border-2 border-dashed border-slate-300 rounded-xl p-6 text-center hover:bg-slate-50 transition cursor-pointer relative">
              <input
                type="file"
                required
                accept=".pdf,.txt,.md"
                onChange={handleFileChange}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              />
              <FileText className="w-8 h-8 text-slate-400 mx-auto mb-2" />
              {file ? (
                <p className="text-xs font-semibold text-slate-800 truncate">{file.name}</p>
              ) : (
                <>
                  <p className="text-xs font-semibold text-slate-700">
                    Click to browse or drag file here
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Supports PDF, TXT, Markdown</p>
                </>
              )}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1">
              Knowledge Source Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Employee Handbook & Pricing Sheet"
              className="w-full px-3 py-2 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>

          {jobStatus && (
            <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs">
              <span className="text-slate-600 font-medium">Ingestion Pipeline Status:</span>
              <span className="font-semibold text-blue-600 capitalize flex items-center">
                {jobStatus === 'completed' ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 mr-1" /> Ready
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
              disabled={loading || !file}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg flex items-center shadow disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Upload & Ingest
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
