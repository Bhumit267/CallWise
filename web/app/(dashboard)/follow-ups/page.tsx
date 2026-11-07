'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { FollowUpListItem, PaginatedResponse } from '@/types/api';
import { CreateFollowUpModal } from '@/components/inbox/create-follow-up-modal';
import {
  Clock,
  CheckCircle2,
  AlertCircle,
  Search,
  PlusCircle,
  RefreshCw,
  Calendar,
  User,
  ChevronLeft,
  ChevronRight,
  MoreVertical,
  Check,
  RotateCcw,
  BellOff,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function FollowUpsPage() {
  const [activeTab, setActiveTab] = useState<'open' | 'done' | 'snoozed'>('open');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [items, setItems] = useState<FollowUpListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);

  const fetchFollowUps = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('status', activeTab);
      if (search.trim()) params.set('search', search.trim());
      params.set('page', page.toString());
      params.set('page_size', pageSize.toString());

      const res = await apiClient<PaginatedResponse<FollowUpListItem>>(
        `/api/follow-ups?${params.toString()}`
      );
      setItems(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
    } catch (err: any) {
      setError(err.message || 'Failed to load follow-up tasks');
    } finally {
      setLoading(false);
    }
  }, [activeTab, search, page, pageSize]);

  useEffect(() => {
    fetchFollowUps();
  }, [fetchFollowUps]);

  const updateTaskStatus = async (
    id: string,
    status: 'open' | 'done' | 'snoozed',
    snoozedUntil?: string
  ) => {
    try {
      await apiClient(`/api/follow-ups/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({
          status,
          snoozed_until: snoozedUntil,
        }),
      });
      fetchFollowUps();
    } catch (err: any) {
      alert(err.message || 'Failed to update task');
    }
  };

  const handleSnooze = (id: string, days: number) => {
    const d = new Date();
    d.setDate(d.getDate() + days);
    updateTaskStatus(id, 'snoozed', d.toISOString());
  };

  const formatDate = (isoString?: string | null) => {
    if (!isoString) return null;
    const d = new Date(isoString);
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
            Follow-up Tasks & Action Items
          </h2>
          <p className="text-sm text-slate-500">
            Promises, customer callbacks, and staff action items created by the receptionist.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchFollowUps()}
            title="Refresh"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>

          <button
            onClick={() => setIsNewTaskOpen(true)}
            className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
          >
            <PlusCircle className="w-4 h-4 mr-2" /> Create Task
          </button>
        </div>
      </div>

      {/* Tabs and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          {/* Status Tabs */}
          <div className="flex items-center space-x-1">
            <button
              onClick={() => {
                setActiveTab('open');
                setPage(1);
              }}
              className={cn(
                'px-4 py-1.5 rounded-lg text-xs font-semibold transition',
                activeTab === 'open'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100'
              )}
            >
              Open Tasks
            </button>
            <button
              onClick={() => {
                setActiveTab('done');
                setPage(1);
              }}
              className={cn(
                'px-4 py-1.5 rounded-lg text-xs font-semibold transition',
                activeTab === 'done'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100'
              )}
            >
              Completed
            </button>
            <button
              onClick={() => {
                setActiveTab('snoozed');
                setPage(1);
              }}
              className={cn(
                'px-4 py-1.5 rounded-lg text-xs font-semibold transition',
                activeTab === 'snoozed'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-600 hover:bg-slate-100'
              )}
            >
              Snoozed
            </button>
          </div>

          {/* Search */}
          <div className="relative min-w-[260px]">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search tasks..."
              className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
            />
          </div>
        </div>
      </div>

      {/* Task List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 text-red-700 text-sm border-b border-red-200">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="divide-y divide-slate-100">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-48" />
                  <div className="h-3 bg-slate-100 rounded w-32" />
                </div>
                <div className="h-4 bg-slate-200 rounded w-16" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <CheckCircle2 className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-800">
              {activeTab === 'open'
                ? 'All clear! No open tasks.'
                : `No ${activeTab} tasks found.`}
            </h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Callbacks and follow-up requests scheduled during customer calls will be organized here.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((task) => (
              <div
                key={task.id}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/60 transition"
              >
                <div className="flex items-start space-x-3.5 min-w-0">
                  <button
                    onClick={() =>
                      updateTaskStatus(task.id, task.status === 'done' ? 'open' : 'done')
                    }
                    className={cn(
                      'w-5 h-5 mt-0.5 rounded border flex items-center justify-center flex-shrink-0 transition',
                      task.status === 'done'
                        ? 'bg-emerald-600 border-emerald-600 text-white'
                        : 'border-slate-300 hover:border-emerald-500 text-transparent'
                    )}
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>

                  <div className="min-w-0 space-y-1">
                    <p
                      className={cn(
                        'text-sm font-semibold truncate',
                        task.status === 'done' ? 'text-slate-400 line-through' : 'text-slate-900'
                      )}
                    >
                      {task.title}
                    </p>

                    {task.description && (
                      <p className="text-xs text-slate-500 line-clamp-1">{task.description}</p>
                    )}

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                      {task.contact_name && (
                        <span className="flex items-center text-slate-600">
                          <User className="w-3 h-3 mr-1 text-slate-400" />
                          {task.contact_name}
                        </span>
                      )}

                      {task.due_at && (
                        <span className="flex items-center text-amber-700 bg-amber-50 px-2 py-0.2 rounded border border-amber-200">
                          <Calendar className="w-3 h-3 mr-1 text-amber-600" />
                          Due: {formatDate(task.due_at)}
                        </span>
                      )}

                      <span className="text-[11px] capitalize bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded">
                        via {task.source}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center">
                  {task.status === 'open' && (
                    <>
                      <button
                        onClick={() => handleSnooze(task.id, 1)}
                        className="px-2.5 py-1 text-xs text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg flex items-center transition"
                        title="Snooze for 1 day"
                      >
                        <BellOff className="w-3.5 h-3.5 mr-1 text-slate-400" /> +1 day
                      </button>
                      <button
                        onClick={() => updateTaskStatus(task.id, 'done')}
                        className="px-3 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition"
                      >
                        Mark Done
                      </button>
                    </>
                  )}

                  {task.status !== 'open' && (
                    <button
                      onClick={() => updateTaskStatus(task.id, 'open')}
                      className="px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-100 rounded-lg flex items-center transition"
                    >
                      <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reopen
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {pages > 1 && (
          <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
            <p className="text-xs text-slate-500">
              Page <span className="font-semibold text-slate-700">{page}</span> of{' '}
              <span className="font-semibold text-slate-700">{pages}</span> ({total} tasks)
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

      <CreateFollowUpModal
        isOpen={isNewTaskOpen}
        onClose={() => setIsNewTaskOpen(false)}
        onSuccess={() => fetchFollowUps()}
      />
    </div>
  );
}
