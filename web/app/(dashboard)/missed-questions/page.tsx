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
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Missed Questions & Knowledge Gaps
          </h2>
          <p className="text-sm text-slate-500">
            Questions callers asked that could not be answered from existing knowledge sources.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-white border border-slate-200 rounded-lg p-0.5 shadow-sm">
            <button
              onClick={() => setViewMode('grouped')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-md text-xs font-semibold transition',
                viewMode === 'grouped'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              )}
            >
              <TrendingUp className="w-3.5 h-3.5 mr-1.5" /> Frequent Gaps
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-md text-xs font-semibold transition',
                viewMode === 'list'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              )}
            >
              <MessageCircleQuestion className="w-3.5 h-3.5 mr-1.5" /> Individual Log
            </button>
          </div>

          <button
            onClick={() => fetchMisses()}
            title="Refresh"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>
        </div>
      </div>

      {/* Tabs and Filters */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-1.5">
          <button
            onClick={() => {
              setStatusFilter('unresolved');
              setPage(1);
            }}
            className={cn(
              'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition',
              statusFilter === 'unresolved'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100'
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
              'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition',
              statusFilter === 'resolved'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100'
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
              'px-3.5 py-1.5 rounded-lg text-xs font-semibold transition',
              statusFilter === 'ignored'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-100'
            )}
          >
            Ignored
          </button>
        </div>

        {viewMode === 'list' && (
          <div className="relative min-w-[260px]">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search question text..."
              className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        )}
      </div>

      {/* Content View */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 text-red-700 text-sm border-b border-red-200">
            {error}
          </div>
        )}

        {loading && (groupedItems.length === 0 && listItems.length === 0) ? (
          <div className="divide-y divide-slate-100">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-64" />
                  <div className="h-3 bg-slate-100 rounded w-32" />
                </div>
                <div className="h-4 bg-slate-200 rounded w-20" />
              </div>
            ))}
          </div>
        ) : (viewMode === 'grouped' ? groupedItems.length === 0 : listItems.length === 0) ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-800">
              {statusFilter === 'unresolved'
                ? 'All caught up! Zero unanswered questions.'
                : `No ${statusFilter} questions found.`}
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              When callers ask questions that cannot be confidently answered by your knowledge base, they are logged here automatically.
            </p>
          </div>
        ) : viewMode === 'grouped' ? (
          /* Grouped Frequency View */
          <div className="divide-y divide-slate-100">
            {groupedItems.map((item, idx) => {
              const missId = item.sample_miss_id_str || item.sample_miss_id || '';
              return (
                <div
                  key={idx}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/60 transition"
                >
                  <div className="flex items-start space-x-3.5 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-amber-50 text-amber-700 border border-amber-200 flex items-center justify-center font-bold text-sm flex-shrink-0">
                      {item.count}x
                    </div>

                    <div className="min-w-0 space-y-1">
                      <p className="text-sm font-bold text-slate-900">
                        "{item.query}"
                      </p>
                      <p className="text-xs text-slate-400">
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
                          className="px-2.5 py-1.5 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg flex items-center transition"
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
                          className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center transition"
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
          <div className="divide-y divide-slate-100">
            {listItems.map((item) => (
              <div
                key={item.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/60 transition"
              >
                <div className="min-w-0 space-y-1">
                  <p className="text-sm font-semibold text-slate-900">"{item.query}"</p>
                  {item.resolved_answer && (
                    <p className="text-xs text-emerald-700 bg-emerald-50 p-2 rounded-lg border border-emerald-200">
                      Resolved Answer: {item.resolved_answer}
                    </p>
                  )}
                  <p className="text-xs text-slate-400">Logged {formatDate(item.created_at)}</p>
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
                    className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm flex items-center transition self-end sm:self-center"
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
          <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
            <p className="text-xs text-slate-500">
              Page <span className="font-semibold text-slate-700">{page}</span> of{' '}
              <span className="font-semibold text-slate-700">{pages}</span>
            </p>

            <div className="flex items-center space-x-2">
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="p-1.5 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                disabled={page >= pages}
                onClick={() => setPage((p) => Math.min(pages, p + 1))}
                className="p-1.5 border border-slate-200 rounded-lg text-slate-600 hover:bg-slate-100 disabled:opacity-40"
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
