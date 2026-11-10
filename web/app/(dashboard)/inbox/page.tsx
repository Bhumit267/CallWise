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
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const TABS = [
  { id: 'all', label: 'All Activity', icon: Inbox },
  { id: 'call', label: 'Calls', icon: Phone },
  { id: 'message', label: 'Messages', icon: MessageSquare },
  { id: 'appointment', label: 'Bookings', icon: Calendar },
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
          color: 'bg-[#dbeafe] text-blue-900',
          label: 'Call',
        };
      case 'message':
        return {
          icon: MessageSquare,
          color: 'bg-[#fef9c3] text-amber-900',
          label: 'Message',
        };
      case 'appointment':
        return {
          icon: Calendar,
          color: 'bg-[#dcfce7] text-emerald-900',
          label: 'Booking',
        };
      case 'transfer':
        return {
          icon: ArrowRightLeft,
          color: 'bg-[#f3e8ff] text-purple-900',
          label: 'Transfer',
        };
      default:
        return {
          icon: Inbox,
          color: 'bg-neutral-100 text-neutral-900',
          label: item.item_type,
        };
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Unified Activity Inbox
            </h2>
            <span className="bg-[#a3e635] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Live Feed
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Real-time feed of caller conversations, booked appointments, and messages.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchInbox()}
            title="Refresh feed"
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>
          <button
            onClick={() => setIsNewFollowUpOpen(true)}
            className="inline-flex items-center px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover"
          >
            <PlusCircle className="w-4 h-4 mr-2" /> New Task
          </button>
        </div>
      </div>

      {/* Tabs and Search Bar */}
      <div className="bg-white p-4 rounded-2xl brutal-border-3 brutal-shadow space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Tab Filter */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 lg:pb-0">
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
                    'flex items-center px-3.5 py-2 rounded-xl text-xs font-black uppercase tracking-wider whitespace-nowrap transition-all duration-100',
                    isActive
                      ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs translate-x-[1px]'
                      : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200 border-2 border-transparent hover:border-black'
                  )}
                >
                  <Icon className="w-3.5 h-3.5 mr-1.5 stroke-[2.5]" />
                  {tab.label}
                </button>
              );
            })}
          </div>

          {/* Search Box */}
          <div className="relative min-w-[280px]">
            <Search className="w-4 h-4 text-black absolute left-3.5 top-3" />
            <input
              type="text"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setPage(1);
              }}
              placeholder="Search caller, phone, or topic..."
              className="brutal-input pl-10 text-xs font-bold"
            />
          </div>
        </div>
      </div>

      {/* Main List */}
      <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
        {error && (
          <div className="p-4 bg-rose-100 text-rose-950 text-xs font-black uppercase border-b-2 border-black">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="divide-y-2 divide-black/10">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="p-4 flex items-center space-x-4 animate-pulse">
                <div className="w-11 h-11 rounded-xl bg-neutral-200 brutal-border" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-neutral-200 rounded w-1/4" />
                  <div className="h-3 bg-neutral-100 rounded w-1/2" />
                </div>
                <div className="h-3 bg-neutral-100 rounded w-16" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-neutral-100 text-black brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
              <Inbox className="w-7 h-7 stroke-[2.5]" />
            </div>
            <h3 className="text-base font-black uppercase text-black">No activity recorded</h3>
            <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
              {search
                ? `No activity matching "${search}". Try adjusting your query.`
                : 'Calls, callback messages, and bookings handled by your AI receptionist will appear here.'}
            </p>
          </div>
        ) : (
          <div className="divide-y-2 divide-black/10">
            {items.map((item) => {
              const badge = getItemBadge(item);
              const BadgeIcon = badge.icon;
              const isClickable = item.item_type === 'call' || item.item_type === 'message';

              return (
                <div
                  key={item.id}
                  onClick={() => isClickable && handleRowClick(item)}
                  className={cn(
                    'p-4 sm:p-5 flex items-start sm:items-center justify-between gap-4 transition-all duration-100',
                    isClickable
                      ? 'cursor-pointer hover:bg-amber-50/50'
                      : 'hover:bg-neutral-50/50'
                  )}
                >
                  <div className="flex items-start sm:items-center space-x-4 min-w-0">
                    {/* Item Type Badge Icon */}
                    <div
                      className={cn(
                        'w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 brutal-border brutal-shadow-xs',
                        badge.color
                      )}
                    >
                      <BadgeIcon className="w-5 h-5 stroke-[2.5]" />
                    </div>

                    {/* Information */}
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 mb-1">
                        <span className="text-sm font-black text-black truncate">
                          {item.title}
                        </span>

                        {item.contact_name && (
                          <span className="text-[10px] font-black uppercase bg-[#fef9c3] text-black px-2 py-0.5 rounded brutal-border brutal-shadow-xs flex items-center">
                            <User className="w-3 h-3 mr-1 text-black" />
                            {item.contact_name}
                          </span>
                        )}

                        {item.meta?.duration_seconds ? (
                          <span className="text-[10px] font-mono font-bold text-black bg-neutral-100 px-2 py-0.5 rounded brutal-border">
                            {formatDuration(item.meta.duration_seconds)}
                          </span>
                        ) : null}
                      </div>

                      <p className="text-xs font-semibold text-neutral-600 line-clamp-1 max-w-2xl">
                        {item.description || 'No summary recorded'}
                      </p>
                    </div>
                  </div>

                  {/* Timestamp and Action */}
                  <div className="flex-shrink-0 text-right">
                    <span className="text-xs font-mono font-bold text-neutral-500 whitespace-nowrap block">
                      {formatTimestamp(item.timestamp)}
                    </span>
                    {isClickable && (
                      <span className="text-[10px] font-black uppercase text-blue-600 hover:text-black hidden sm:inline-block mt-1">
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
          <div className="px-6 py-4 border-t-2 border-black flex items-center justify-between bg-neutral-50">
            <p className="text-xs font-black uppercase text-neutral-700">
              Page <span className="text-black">{page}</span> of{' '}
              <span className="text-black">{pages}</span> ({total} items)
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
