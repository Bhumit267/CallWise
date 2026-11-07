'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { DocumentSourceItem } from '@/types/api';
import { AddSnippetModal } from '@/components/knowledge/add-snippet-modal';
import { UploadDocumentModal } from '@/components/knowledge/upload-document-modal';
import { CrawlUrlModal } from '@/components/knowledge/crawl-url-modal';
import { DeleteSourceModal } from '@/components/knowledge/delete-source-modal';
import {
  BookOpen,
  PlusCircle,
  UploadCloud,
  Globe,
  RefreshCw,
  Search,
  Trash2,
  FileText,
  MessageSquareQuote,
  Layers,
  Sparkles,
  ExternalLink,
  RotateCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function KnowledgePage() {
  const [sources, setSources] = useState<DocumentSourceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  // Modals
  const [isAddSnippetOpen, setIsAddSnippetOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isCrawlOpen, setIsCrawlOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentSourceItem | null>(null);

  const fetchSources = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient<DocumentSourceItem[]>('/api/knowledge/sources');
      setSources(data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load knowledge sources');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  const handleReingest = async (id: string) => {
    try {
      await apiClient(`/api/knowledge/sources/${id}/reingest`, {
        method: 'POST',
      });
      fetchSources();
    } catch (err: any) {
      alert(err.message || 'Failed to queue re-ingestion');
    }
  };

  const filteredSources = sources.filter((s) => {
    if (!search.trim()) return true;
    const term = search.toLowerCase();
    return s.title.toLowerCase().includes(term) || s.source_uri.toLowerCase().includes(term);
  });

  const getSourceIcon = (type: string) => {
    switch (type) {
      case 'file':
        return { icon: FileText, color: 'text-purple-600 bg-purple-50 border-purple-200', label: 'Document File' };
      case 'url':
        return { icon: Globe, color: 'text-blue-600 bg-blue-50 border-blue-200', label: 'Website Crawl' };
      case 'qa_snippet':
        return { icon: MessageSquareQuote, color: 'text-amber-600 bg-amber-50 border-amber-200', label: 'Q&A Snippet' };
      default:
        return { icon: BookOpen, color: 'text-slate-600 bg-slate-50 border-slate-200', label: type };
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  };

  const totalChunks = sources.reduce((acc, s) => acc + (s.chunk_count || 0), 0);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Knowledge Base & RAG Index
          </h2>
          <p className="text-sm text-slate-500">
            Train your AI voice receptionist with website content, company files, and FAQs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => fetchSources()}
            title="Refresh sources"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>

          <button
            onClick={() => setIsAddSnippetOpen(true)}
            className="inline-flex items-center px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg shadow-sm transition"
          >
            <MessageSquareQuote className="w-3.5 h-3.5 mr-1.5 text-blue-600" /> Add Q&A Snippet
          </button>

          <button
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center px-3.5 py-2 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-semibold rounded-lg shadow-sm transition"
          >
            <UploadCloud className="w-3.5 h-3.5 mr-1.5 text-purple-600" /> Upload File
          </button>

          <button
            onClick={() => setIsCrawlOpen(true)}
            className="inline-flex items-center px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition"
          >
            <Globe className="w-3.5 h-3.5 mr-1.5" /> Crawl Website
          </button>
        </div>
      </div>

      {/* Stats Summary Card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
            <BookOpen className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">Knowledge Sources</p>
            <p className="text-lg font-bold text-slate-900">{sources.length}</p>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">Indexed Vector Chunks</p>
            <p className="text-lg font-bold text-slate-900">{totalChunks}</p>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500">Semantic Search Model</p>
            <p className="text-sm font-bold text-slate-900 truncate">text-embedding-3-small</p>
          </div>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter knowledge sources..."
            className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
        </div>
        <p className="text-xs text-slate-500">
          Showing <span className="font-semibold text-slate-800">{filteredSources.length}</span> sources
        </p>
      </div>

      {/* Sources Grid / List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 text-red-700 text-sm border-b border-red-200">
            {error}
          </div>
        )}

        {loading && sources.length === 0 ? (
          <div className="divide-y divide-slate-100">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-48" />
                  <div className="h-3 bg-slate-100 rounded w-32" />
                </div>
                <div className="h-4 bg-slate-200 rounded w-16" />
              </div>
            ))}
          </div>
        ) : filteredSources.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <BookOpen className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-800">No knowledge sources yet</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {search
                ? `No sources matching "${search}".`
                : 'Add FAQs, upload company documents, or crawl your website to train your AI receptionist.'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredSources.map((source) => {
              const badge = getSourceIcon(source.source_type);
              const BadgeIcon = badge.icon;

              return (
                <div
                  key={source.id}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/60 transition"
                >
                  <div className="flex items-start space-x-3.5 min-w-0">
                    <div
                      className={cn(
                        'w-10 h-10 rounded-xl border flex items-center justify-center flex-shrink-0',
                        badge.color
                      )}
                    >
                      <BadgeIcon className="w-5 h-5" />
                    </div>

                    <div className="min-w-0 space-y-0.5">
                      <div className="flex items-center space-x-2">
                        <h4 className="text-sm font-bold text-slate-900 truncate">
                          {source.title}
                        </h4>
                        <span className="text-[10px] font-semibold uppercase px-2 py-0.2 rounded bg-slate-100 text-slate-600">
                          {badge.label}
                        </span>
                      </div>

                      <p className="text-xs text-slate-400 truncate max-w-xl font-mono">
                        {source.source_uri}
                      </p>

                      <div className="flex items-center space-x-3 text-xs text-slate-500 pt-0.5">
                        <span className="font-semibold text-slate-700">
                          {source.chunk_count} vector chunk{source.chunk_count !== 1 ? 's' : ''}
                        </span>
                        <span>&middot;</span>
                        <span>Added {formatDate(source.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center">
                    {source.source_type !== 'qa_snippet' && (
                      <button
                        onClick={() => handleReingest(source.id)}
                        title="Re-crawl / Re-ingest"
                        className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg text-xs flex items-center"
                      >
                        <RotateCw className="w-3.5 h-3.5 mr-1" /> Re-index
                      </button>
                    )}

                    <button
                      onClick={() => setDeleteTarget(source)}
                      title="Delete source"
                      className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg text-xs flex items-center"
                    >
                      <Trash2 className="w-3.5 h-3.5 mr-1" /> Remove
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Modals */}
      <AddSnippetModal
        isOpen={isAddSnippetOpen}
        onClose={() => setIsAddSnippetOpen(false)}
        onSuccess={() => fetchSources()}
      />

      <UploadDocumentModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => fetchSources()}
      />

      <CrawlUrlModal
        isOpen={isCrawlOpen}
        onClose={() => setIsCrawlOpen(false)}
        onSuccess={() => fetchSources()}
      />

      {deleteTarget && (
        <DeleteSourceModal
          isOpen={Boolean(deleteTarget)}
          onClose={() => setDeleteTarget(null)}
          onSuccess={() => fetchSources()}
          sourceId={deleteTarget.id}
          title={deleteTarget.title}
          chunkCount={deleteTarget.chunk_count}
        />
      )}
    </div>
  );
}
