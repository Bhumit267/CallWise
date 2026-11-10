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
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Follow-up Action Items
            </h2>
            <span className="bg-[#ffe600] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Task Hub
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Promises, customer callbacks, and staff action items created by the receptionist.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchFollowUps()}
            title="Refresh"
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>

          <button
            onClick={() => setIsNewTaskOpen(true)}
            className="inline-flex items-center px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover transition"
          >
            <PlusCircle className="w-4 h-4 mr-2" /> Create Task
          </button>
        </div>
      </div>

      {/* Tabs and Search Bar */}
      <div className="bg-white p-4 rounded-2xl brutal-border-3 brutal-shadow flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center space-x-2">
          <button
            onClick={() => {
              setActiveTab('open');
              setPage(1);
            }}
            className={cn(
              'px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
              activeTab === 'open'
                ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200'
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
              'px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
              activeTab === 'done'
                ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200'
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
              'px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
              activeTab === 'snoozed'
                ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
                : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200'
            )}
          >
            Snoozed
          </button>
        </div>

        {/* Search */}
        <div className="relative min-w-[260px]">
          <Search className="w-4 h-4 text-black absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search tasks..."
            className="brutal-input pl-10 text-xs font-bold"
          />
        </div>
      </div>

      {/* Task List */}
      <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
        {error && (
          <div className="p-4 bg-rose-100 text-rose-950 text-xs font-black uppercase border-b-2 border-black">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="divide-y-2 divide-black/10">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="space-y-2">
                  <div className="h-4 bg-neutral-200 rounded w-48" />
                  <div className="h-3 bg-neutral-100 rounded w-32" />
                </div>
                <div className="h-4 bg-neutral-200 rounded w-16" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-[#dcfce7] text-emerald-950 brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
              <CheckCircle2 className="w-8 h-8 stroke-[2.5]" />
            </div>
            <h3 className="text-base font-black uppercase text-black">
              {activeTab === 'open'
                ? 'All clear! No open tasks.'
                : `No ${activeTab} tasks found.`}
            </h3>
            <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
              Callbacks and follow-up requests scheduled during customer calls will be organized here.
            </p>
          </div>
        ) : (
          <div className="divide-y-2 divide-black/10">
            {items.map((task) => (
              <div
                key={task.id}
                className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-amber-50/50 transition-all duration-100"
              >
                <div className="flex items-start space-x-4 min-w-0">
                  <button
                    onClick={() =>
                      updateTaskStatus(task.id, task.status === 'done' ? 'open' : 'done')
                    }
                    className={cn(
                      'w-6 h-6 mt-0.5 rounded-lg brutal-border flex items-center justify-center flex-shrink-0 transition-all',
                      task.status === 'done'
                        ? 'bg-emerald-500 text-white brutal-shadow-xs'
                        : 'bg-white hover:bg-neutral-100'
                    )}
                  >
                    <Check className="w-4 h-4 stroke-[3]" />
                  </button>

                  <div className="min-w-0 space-y-1">
                    <p
                      className={cn(
                        'text-sm font-black truncate',
                        task.status === 'done' ? 'text-neutral-400 line-through' : 'text-black'
                      )}
                    >
                      {task.title}
                    </p>

                    {task.description && (
                      <p className="text-xs font-semibold text-neutral-600 line-clamp-1">{task.description}</p>
                    )}

                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                      {task.contact_name && (
                        <span className="flex items-center font-bold text-black bg-neutral-100 px-2 py-0.5 rounded brutal-border text-[11px]">
                          <User className="w-3 h-3 mr-1 text-black" />
                          {task.contact_name}
                        </span>
                      )}

                      {task.due_at && (
                        <span className="flex items-center text-amber-950 bg-[#fef9c3] px-2 py-0.5 rounded brutal-border font-bold text-[11px]">
                          <Calendar className="w-3 h-3 mr-1 text-black" />
                          Due: {formatDate(task.due_at)}
                        </span>
                      )}

                      <span className="text-[10px] font-mono font-bold uppercase bg-white text-neutral-700 px-2 py-0.5 rounded brutal-border">
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
                        className="px-3 py-1.5 text-xs font-black uppercase text-neutral-700 hover:text-black bg-white brutal-border brutal-shadow-xs rounded-lg flex items-center transition"
                        title="Snooze for 1 day"
                      >
                        <BellOff className="w-3.5 h-3.5 mr-1" /> +1 day
                      </button>
                      <button
                        onClick={() => updateTaskStatus(task.id, 'done')}
                        className="px-3.5 py-1.5 text-xs font-black uppercase text-emerald-950 bg-[#dcfce7] hover:bg-emerald-200 brutal-border brutal-shadow-xs rounded-xl transition"
                      >
                        Mark Done
                      </button>
                    </>
                  )}

                  {task.status !== 'open' && (
                    <button
                      onClick={() => updateTaskStatus(task.id, 'open')}
                      className="px-3 py-1.5 text-xs font-black uppercase text-neutral-800 hover:text-black bg-white brutal-border brutal-shadow-xs rounded-xl flex items-center transition"
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
          <div className="px-6 py-4 border-t-2 border-black flex items-center justify-between bg-neutral-50">
            <p className="text-xs font-black uppercase text-neutral-700">
              Page <span className="text-black">{page}</span> of{' '}
              <span className="text-black">{pages}</span> ({total} tasks)
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

      <CreateFollowUpModal
        isOpen={isNewTaskOpen}
        onClose={() => setIsNewTaskOpen(false)}
        onSuccess={() => fetchFollowUps()}
      />
    </div>
  );
}
