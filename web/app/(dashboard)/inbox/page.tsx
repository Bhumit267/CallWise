'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { InboxItem, PaginatedResponse } from '@/types/api';
import { CallDetailDrawer } from '@/components/inbox/call-detail-drawer';
import { MessageDetailModal } from '@/components/inbox/message-detail-modal';
import { CreateFollowUpModal } from '@/components/inbox/create-follow-up-modal';
import {
  Inbox,
  Phone,
  MessageSquare,
  Calendar,
  ArrowRightLeft,
  Search,
  RefreshCw,
  PlusCircle,
  Clock,
  User,
  ChevronLeft,
  ChevronRight,
  Filter,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const TABS = [
  { id: 'all', label: 'All Activity', icon: Inbox },
  { id: 'call', label: 'Calls', icon: Phone },
  { id: 'message', label: 'Messages', icon: MessageSquare },
  { id: 'appointment', label: 'Appointments', icon: Calendar },
  { id: 'transfer', label: 'Transfers', icon: ArrowRightLeft },
];

export default function InboxPage() {
  const [activeTab, setActiveTab] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [items, setItems] = useState<InboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected item detail drawers
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null);
  const [isNewFollowUpOpen, setIsNewFollowUpOpen] = useState(false);

  const fetchInbox = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (activeTab !== 'all') params.set('type', activeTab);
      if (search.trim()) params.set('search', search.trim());
      params.set('page', page.toString());
      params.set('page_size', pageSize.toString());

      const res = await apiClient<PaginatedResponse<InboxItem>>(
        `/api/inbox?${params.toString()}`
      );
      setItems(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch inbox items');
    } finally {
      setLoading(false);
    }
  }, [activeTab, search, page, pageSize]);

  useEffect(() => {
    fetchInbox();
  }, [fetchInbox]);

  const handleRowClick = (item: InboxItem) => {
    if (item.item_type === 'call') {
      const callId = item.meta?.call_id || item.id.replace('call_', '');
      setSelectedCallId(callId);
    } else if (item.item_type === 'message') {
      const msgId = item.meta?.message_id || item.id.replace('message_', '');
      setSelectedMessageId(msgId);
    }
  };

  const formatTimestamp = (iso: string) => {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24 && d.getDate() === now.getDate()) {
      return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    }
    if (diffDays === 1) return 'Yesterday';
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const formatDuration = (secs?: number) => {
    if (!secs) return null;
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}m ${s < 10 ? '0' : ''}${s}s`;
  };

  const getItemBadge = (item: InboxItem) => {
    switch (item.item_type) {
      case 'call':
        return {
          icon: Phone,
          color: 'bg-blue-100 text-blue-800 border-blue-200',
          label: 'Call',
        };
      case 'message':
        return {
          icon: MessageSquare,
          color: 'bg-amber-100 text-amber-800 border-amber-200',
          label: 'Message',
        };
      case 'appointment':
        return {
          icon: Calendar,
          color: 'bg-emerald-100 text-emerald-800 border-emerald-200',
          label: 'Booking',
        };
      case 'transfer':
        return {
          icon: ArrowRightLeft,
          color: 'bg-purple-100 text-purple-800 border-purple-200',
          label: 'Transfer',
        };
      default:
        return {
          icon: Inbox,
          color: 'bg-slate-100 text-slate-800 border-slate-200',
          label: item.item_type,
        };
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Unified Activity Inbox</h2>
          <p className="text-sm text-slate-500">
            Real-time feed of caller conversations, booked appointments, and messages.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchInbox()}
            title="Refresh feed"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm transition"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>
          <button
            onClick={() => setIsNewFollowUpOpen(true)}
            className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
          >
            <PlusCircle className="w-4 h-4 mr-2" /> New Task
          </button>
        </div>
      </div>

      {/* Tabs and Search Bar */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Tab Filter */}
          <div className="flex items-center space-x-1 overflow-x-auto pb-1 lg:pb-0">
            {TABS.map((tab) => {
              const Icon = tab.icon;
              const isActive = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setPage(1);
                  }}
                  className={cn(
                    'flex items-center px-3.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition',
                    isActive
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100'
                  )}
                >
                  <Icon className="w-3.5 h-3.5 mr-1.5" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Search Box */}
          <div className="relative min-w-[280px]">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search phone, caller, or topic..."
              className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent"
            />
          </div>
        </div>
      </div>

      {/* Main List */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 text-red-700 text-sm border-b border-red-200">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="divide-y divide-slate-100">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="p-4 flex items-center space-x-4 animate-pulse">
                <div className="w-10 h-10 rounded-full bg-slate-200" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-slate-200 rounded w-1/4" />
                  <div className="h-3 bg-slate-100 rounded w-1/2" />
                </div>
                <div className="h-3 bg-slate-100 rounded w-16" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <Inbox className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-800">No activity recorded</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {search
                ? `No activity matching "${search}". Try adjusting your search query.`
                : 'Calls, callback messages, and bookings handled by your AI receptionist will appear here.'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((item) => {
              const badge = getItemBadge(item);
              const BadgeIcon = badge.icon;
              const isClickable = item.item_type === 'call' || item.item_type === 'message';

              return (
                <div
                  key={item.id}
                  onClick={() => isClickable && handleRowClick(item)}
                  className={cn(
                    'p-4 flex items-start sm:items-center justify-between gap-4 transition',
                    isClickable
                      ? 'cursor-pointer hover:bg-slate-50/80'
                      : 'hover:bg-slate-50/40'
                  )}
                >
                  <div className="flex items-start sm:items-center space-x-3.5 min-w-0">
                    {/* Item Type Badge Icon */}
                    <div
                      className={cn(
                        'w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 border',
                        badge.color
                      )}
                    >
                      <BadgeIcon className="w-5 h-5" />
                    </div>

                    {/* Information */}
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-0.5">
                        <span className="text-sm font-semibold text-slate-900 truncate">
                          {item.title}
                        </span>

                        {item.contact_name && (
                          <span className="text-[11px] font-medium bg-slate-100 text-slate-700 px-2 py-0.5 rounded-full flex items-center">
                            <User className="w-3 h-3 mr-1 text-slate-400" />
                            {item.contact_name}
                          </span>
                        )}

                        {item.meta?.duration_seconds ? (
                          <span className="text-[11px] font-mono text-slate-500 bg-slate-100 px-1.5 py-0.2 rounded">
                            {formatDuration(item.meta.duration_seconds)}
                          </span>
                        ) : null}
                      </div>

                      <p className="text-xs text-slate-500 line-clamp-1 max-w-2xl">
                        {item.description || 'No summary recorded'}
                      </p>
                    </div>
                  </div>

                  {/* Timestamp and Action */}
                  <div className="flex-shrink-0 text-right">
                    <span className="text-xs font-medium text-slate-400 whitespace-nowrap block">
                      {formatTimestamp(item.timestamp)}
                    </span>
                    {isClickable && (
                      <span className="text-[11px] font-semibold text-blue-600 hover:text-blue-700 hidden sm:inline-block mt-0.5">
                        View details &rarr;
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Pagination Footer */}
        {pages > 1 && (
          <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
            <p className="text-xs text-slate-500">
              Showing page <span className="font-semibold text-slate-700">{page}</span> of{' '}
              <span className="font-semibold text-slate-700">{pages}</span> ({total} items total)
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

      {/* Slide-over Call Detail Drawer */}
      <CallDetailDrawer
        callId={selectedCallId}
        isOpen={Boolean(selectedCallId)}
        onClose={() => setSelectedCallId(null)}
        onFollowUpCreated={() => {
          fetchInbox();
        }}
      />

      {/* Message Detail Modal */}
      <MessageDetailModal
        messageId={selectedMessageId}
        isOpen={Boolean(selectedMessageId)}
        onClose={() => setSelectedMessageId(null)}
        onFollowUpCreated={() => {
          fetchInbox();
        }}
      />

      {/* Standalone New Follow-up Modal */}
      <CreateFollowUpModal
        isOpen={isNewFollowUpOpen}
        onClose={() => setIsNewFollowUpOpen(false)}
        onSuccess={() => {
          fetchInbox();
        }}
        defaultTitle=""
        defaultDescription=""
      />
    </div>
  );
}
