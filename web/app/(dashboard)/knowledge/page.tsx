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
        return { icon: FileText, color: 'text-purple-950 bg-[#f3e8ff]', label: 'Document File' };
      case 'url':
        return { icon: Globe, color: 'text-blue-950 bg-[#dbeafe]', label: 'Website Crawl' };
      case 'qa_snippet':
        return { icon: MessageSquareQuote, color: 'text-amber-950 bg-[#fef9c3]', label: 'Q&A Snippet' };
      default:
        return { icon: BookOpen, color: 'text-black bg-neutral-100', label: type };
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
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Knowledge Base & RAG Index
            </h2>
            <span className="bg-[#a3e635] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Semantic Search
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Train your AI voice receptionist with website content, company files, and FAQs.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          <button
            onClick={() => fetchSources()}
            title="Refresh sources"
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>

          <button
            onClick={() => setIsAddSnippetOpen(true)}
            className="inline-flex items-center px-3.5 py-2.5 bg-white hover:bg-neutral-100 text-black text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow-xs brutal-shadow-hover"
          >
            <MessageSquareQuote className="w-3.5 h-3.5 mr-1.5 text-black" /> Add Q&amp;A Snippet
          </button>

          <button
            onClick={() => setIsUploadOpen(true)}
            className="inline-flex items-center px-3.5 py-2.5 bg-[#fef9c3] hover:bg-[#fef08a] text-black text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow-xs brutal-shadow-hover"
          >
            <UploadCloud className="w-3.5 h-3.5 mr-1.5 text-black" /> Upload File
          </button>

          <button
            onClick={() => setIsCrawlOpen(true)}
            className="inline-flex items-center px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover"
          >
            <Globe className="w-3.5 h-3.5 mr-1.5" /> Crawl Website
          </button>
        </div>
      </div>

      {/* Stats Summary Card */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow flex items-center space-x-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#dbeafe] text-blue-950 brutal-border brutal-shadow-xs flex items-center justify-center">
            <BookOpen className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <p className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Knowledge Sources</p>
            <p className="text-2xl font-black text-black">{sources.length}</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow flex items-center space-x-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#dcfce7] text-emerald-950 brutal-border brutal-shadow-xs flex items-center justify-center">
            <Layers className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <p className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Indexed Vector Chunks</p>
            <p className="text-2xl font-black text-black">{totalChunks}</p>
          </div>
        </div>

        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow flex items-center space-x-3.5">
          <div className="w-11 h-11 rounded-xl bg-[#f3e8ff] text-purple-950 brutal-border brutal-shadow-xs flex items-center justify-center">
            <Sparkles className="w-5 h-5 stroke-[2.5]" />
          </div>
          <div>
            <p className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Semantic Search Model</p>
            <p className="text-sm font-black text-black font-mono truncate">all-MiniLM-L6-v2</p>
          </div>
        </div>
      </div>

      {/* Filter and Search */}
      <div className="bg-white p-4 rounded-2xl brutal-border-3 brutal-shadow flex items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-black absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter knowledge sources..."
            className="brutal-input pl-10 text-xs font-bold"
          />
        </div>
        <div className="text-xs font-black uppercase text-neutral-700 bg-neutral-100 px-3 py-1.5 rounded-lg brutal-border">
          Showing <span className="text-black">{filteredSources.length}</span> sources
        </div>
      </div>

      {/* Sources Grid / List */}
      <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
        {error && (
          <div className="p-4 bg-rose-100 text-rose-950 text-xs font-black uppercase border-b-2 border-black">
            {error}
          </div>
        )}

        {loading && sources.length === 0 ? (
          <div className="divide-y-2 divide-black/10">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="space-y-2">
                  <div className="h-4 bg-neutral-200 rounded w-48" />
                  <div className="h-3 bg-neutral-100 rounded w-32" />
                </div>
                <div className="h-4 bg-neutral-200 rounded w-16" />
              </div>
            ))}
          </div>
        ) : filteredSources.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-neutral-100 text-black brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
              <BookOpen className="w-7 h-7 stroke-[2.5]" />
            </div>
            <h3 className="text-base font-black uppercase text-black">No knowledge sources yet</h3>
            <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
              {search
                ? `No sources matching "${search}".`
                : 'Add FAQs, upload company documents, or crawl your website to train your AI receptionist.'}
            </p>
          </div>
        ) : (
          <div className="divide-y-2 divide-black/10">
            {filteredSources.map((source) => {
              const badge = getSourceIcon(source.source_type);
              const BadgeIcon = badge.icon;

              return (
                <div
                  key={source.id}
                  className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-amber-50/50 transition-all duration-100"
                >
                  <div className="flex items-start space-x-4 min-w-0">
                    <div
                      className={cn(
                        'w-11 h-11 rounded-xl brutal-border brutal-shadow-xs flex items-center justify-center flex-shrink-0',
                        badge.color
                      )}
                    >
                      <BadgeIcon className="w-5 h-5 stroke-[2.5]" />
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex items-center space-x-2">
                        <h4 className="text-sm font-black text-black truncate">
                          {source.title}
                        </h4>
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-white text-black brutal-border">
                          {badge.label}
                        </span>
                      </div>

                      <p className="text-xs font-mono font-bold text-neutral-600 truncate max-w-xl">
                        {source.source_uri}
                      </p>

                      <div className="flex items-center space-x-2 text-xs pt-0.5">
                        <span className="font-black bg-[#dcfce7] text-emerald-950 px-2 py-0.5 rounded brutal-border text-[10px]">
                          {source.chunk_count} vector chunk{source.chunk_count !== 1 ? 's' : ''}
                        </span>
                        <span className="font-mono text-neutral-500 text-[11px] font-bold">&middot; Added {formatDate(source.created_at)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center">
                    {source.source_type !== 'qa_snippet' && (
                      <button
                        onClick={() => handleReingest(source.id)}
                        title="Re-crawl / Re-ingest"
                        className="px-2.5 py-1 text-xs font-black uppercase text-black bg-white hover:bg-neutral-100 brutal-border brutal-shadow-xs rounded-lg flex items-center"
                      >
                        <RotateCw className="w-3.5 h-3.5 mr-1" /> Re-index
                      </button>
                    )}

                    <button
                      onClick={() => setDeleteTarget(source)}
                      title="Delete source"
                      className="px-2.5 py-1 text-xs font-black uppercase text-rose-700 bg-rose-50 hover:bg-rose-100 brutal-border brutal-shadow-xs rounded-lg flex items-center"
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
