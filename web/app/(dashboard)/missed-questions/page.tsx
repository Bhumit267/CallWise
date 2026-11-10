'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { KnowledgeMissGroupItem, KnowledgeMissListItem, PaginatedResponse } from '@/types/api';
import { ResolveMissModal } from '@/components/knowledge/resolve-miss-modal';
import {
  HelpCircle,
  Sparkles,
  RefreshCw,
  Search,
  CheckCircle2,
  Ban,
  Filter,
  Layers,
  ChevronLeft,
  ChevronRight,
  TrendingUp,
  MessageCircleQuestion,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function MissedQuestionsPage() {
  const [viewMode, setViewMode] = useState<'grouped' | 'list'>('grouped');
  const [statusFilter, setStatusFilter] = useState('unresolved');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [groupedItems, setGroupedItems] = useState<KnowledgeMissGroupItem[]>([]);
  const [listItems, setListItems] = useState<KnowledgeMissListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal target
  const [resolveTarget, setResolveTarget] = useState<{
    id: string;
    query: string;
    count: number;
  } | null>(null);

  const fetchMisses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (viewMode === 'grouped') {
        const data = await apiClient<KnowledgeMissGroupItem[]>(
          `/api/knowledge-misses/grouped?status=${statusFilter}&limit=100`
        );
        setGroupedItems(data || []);
      } else {
        const params = new URLSearchParams();
        params.set('status', statusFilter);
        if (search.trim()) params.set('search', search.trim());
        params.set('page', page.toString());
        params.set('page_size', pageSize.toString());

        const res = await apiClient<PaginatedResponse<KnowledgeMissListItem>>(
          `/api/knowledge-misses?${params.toString()}`
        );
        setListItems(res.items || []);
        setTotal(res.total || 0);
        setPages(res.pages || 1);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load missed questions');
    } finally {
      setLoading(false);
    }
  }, [viewMode, statusFilter, search, page, pageSize]);

  useEffect(() => {
    fetchMisses();
  }, [fetchMisses]);

  const handleIgnore = async (missId: string) => {
    try {
      await apiClient(`/api/knowledge-misses/${missId}/ignore`, {
        method: 'POST',
      });
      fetchMisses();
    } catch (err: any) {
      alert(err.message || 'Failed to ignore question');
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString([], {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Missed Questions & Gaps
            </h2>
            <span className="bg-[#ffe600] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Continuous Learning
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Questions callers asked that could not be answered from existing knowledge sources.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-white brutal-border rounded-xl p-1 brutal-shadow-xs">
            <button
              onClick={() => setViewMode('grouped')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition',
                viewMode === 'grouped'
                  ? 'bg-black text-white'
                  : 'text-neutral-700 hover:text-black'
              )}
            >
              <TrendingUp className="w-3.5 h-3.5 mr-1.5 stroke-[2.5]" /> Frequent Gaps
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition',
                viewMode === 'list'
                  ? 'bg-black text-white'
                  : 'text-neutral-700 hover:text-black'
              )}
            >
              <MessageCircleQuestion className="w-3.5 h-3.5 mr-1.5 stroke-[2.5]" /> Log
            </button>
          </div>

          <button
            onClick={() => fetchMisses()}
            title="Refresh"
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>
        </div>
      </div>

      {/* Tabs and Filters */}
      <div className="bg-white p-4 rounded-2xl brutal-border-3 brutal-shadow flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              setStatusFilter('unresolved');
              setPage(1);
            }}
            className={cn(
              'px-3.5 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
              statusFilter === 'unresolved'
                ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200'
            )}
          >
            Unresolved Gaps
          </button>
          <button
            onClick={() => {
              setStatusFilter('resolved');
              setPage(1);
            }}
            className={cn(
              'px-3.5 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
              statusFilter === 'resolved'
                ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200'
            )}
          >
            Resolved
          </button>
          <button
            onClick={() => {
              setStatusFilter('ignored');
              setPage(1);
            }}
            className={cn(
              'px-3.5 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
              statusFilter === 'ignored'
                ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200'
            )}
          >
            Ignored
          </button>
        </div>

        {viewMode === 'list' && (
          <div className="relative min-w-[260px]">
            <Search className="w-4 h-4 text-black absolute left-3.5 top-3" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search question text..."
              className="brutal-input pl-10 text-xs font-bold"
            />
          </div>
        )}
      </div>

      {/* Content View */}
      <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
        {error && (
          <div className="p-4 bg-rose-100 text-rose-950 text-xs font-black uppercase border-b-2 border-black">
            {error}
          </div>
        )}

        {loading && (groupedItems.length === 0 && listItems.length === 0) ? (
          <div className="divide-y-2 divide-black/10">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="space-y-2">
                  <div className="h-4 bg-neutral-200 rounded w-64" />
                  <div className="h-3 bg-neutral-100 rounded w-32" />
                </div>
                <div className="h-4 bg-neutral-200 rounded w-20" />
              </div>
            ))}
          </div>
        ) : (viewMode === 'grouped' ? groupedItems.length === 0 : listItems.length === 0) ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-[#dcfce7] text-emerald-950 brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
              <CheckCircle2 className="w-8 h-8 stroke-[2.5]" />
            </div>
            <h3 className="text-base font-black uppercase text-black">
              {statusFilter === 'unresolved'
                ? 'All caught up! Zero unanswered questions.'
                : `No ${statusFilter} questions found.`}
            </h3>
            <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
              When callers ask questions that cannot be confidently answered by your knowledge base, they are logged here automatically.
            </p>
          </div>
        ) : viewMode === 'grouped' ? (
          /* Grouped Frequency View */
          <div className="divide-y-2 divide-black/10">
            {groupedItems.map((item, idx) => {
              const missId = item.sample_miss_id_str || item.sample_miss_id || '';
              return (
                <div
                  key={idx}
                  className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-amber-50/50 transition-all duration-100"
                >
                  <div className="flex items-start space-x-4 min-w-0">
                    <div className="w-11 h-11 rounded-xl bg-[#fef9c3] text-black brutal-border brutal-shadow-xs flex items-center justify-center font-black text-sm flex-shrink-0">
                      {item.count}x
                    </div>

                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-black text-black">
                        &quot;{item.query}&quot;
                      </p>
                      <p className="text-xs font-mono font-bold text-neutral-500">
                        Last asked {formatDate(item.last_asked_at)} &middot; Frequency: {item.count} caller{item.count !== 1 ? 's' : ''}
                      </p>
                    </div>
                  </div>

                  {/* Action */}
                  <div className="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center">
                    {statusFilter === 'unresolved' && (
                      <>
                        <button
                          onClick={() => handleIgnore(missId)}
                          className="px-2.5 py-1.5 text-xs font-black uppercase text-neutral-700 hover:text-black bg-white brutal-border brutal-shadow-xs rounded-lg flex items-center transition"
                        >
                          <Ban className="w-3.5 h-3.5 mr-1" /> Dismiss
                        </button>

                        <button
                          onClick={() =>
                            setResolveTarget({
                              id: missId,
                              query: item.query,
                              count: item.count,
                            })
                          }
                          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover flex items-center transition"
                        >
                          <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Answer & Train
                        </button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          /* Individual List View */
          <div className="divide-y-2 divide-black/10">
            {listItems.map((item) => (
              <div
                key={item.id}
                className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-amber-50/50 transition-all duration-100"
              >
                <div className="min-w-0 space-y-1.5">
                  <p className="text-sm font-black text-black">&quot;{item.query}&quot;</p>
                  {item.resolved_answer && (
                    <p className="text-xs font-semibold text-emerald-950 bg-[#dcfce7] p-2.5 rounded-xl brutal-border">
                      Resolved Answer: {item.resolved_answer}
                    </p>
                  )}
                  <p className="text-xs font-mono text-neutral-500">Logged {formatDate(item.created_at)}</p>
                </div>

                {statusFilter === 'unresolved' && (
                  <button
                    onClick={() =>
                      setResolveTarget({
                        id: item.id,
                        query: item.query,
                        count: 1,
                      })
                    }
                    className="px-3.5 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover flex items-center transition self-end sm:self-center"
                  >
                    <Sparkles className="w-3.5 h-3.5 mr-1.5" /> Answer
                  </button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Pagination for list view */}
        {viewMode === 'list' && pages > 1 && (
          <div className="px-6 py-4 border-t-2 border-black flex items-center justify-between bg-neutral-50">
            <p className="text-xs font-black uppercase text-neutral-700">
              Page <span className="text-black">{page}</span> of{' '}
              <span className="text-black">{pages}</span>
            </p>

            <div className="flex items-center space-x-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-2 bg-white brutal-border rounded-lg text-black hover:bg-neutral-100 disabled:opacity-30 brutal-shadow-xs"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={page >= pages}
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                className="p-2 bg-white brutal-border rounded-lg text-black hover:bg-neutral-100 disabled:opacity-30 brutal-shadow-xs"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Resolve Modal */}
      {resolveTarget && (
        <ResolveMissModal
          isOpen={Boolean(resolveTarget)}
          onClose={() => setResolveTarget(null)}
          onSuccess={() => fetchMisses()}
          missId={resolveTarget.id}
          query={resolveTarget.query}
          count={resolveTarget.count}
        />
      )}
    </div>
  );
}
