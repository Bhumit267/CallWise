'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { ContactListItem, PaginatedResponse } from '@/types/api';
import { ContactDetailDrawer } from '@/components/contacts/contact-detail-drawer';
import {
  Users,
  Search,
  RefreshCw,
  Phone,
  Mail,
  Calendar,
  Clock,
  Ban,
  ChevronLeft,
  ChevronRight,
  UserCheck,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function ContactsPage() {
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [items, setItems] = useState<ContactListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [selectedContactId, setSelectedContactId] = useState<string | null>(null);

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (search.trim()) params.set('search', search.trim());
      params.set('page', page.toString());
      params.set('page_size', pageSize.toString());

      const res = await apiClient<PaginatedResponse<ContactListItem>>(
        `/api/contacts?${params.toString()}`
      );
      setItems(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
    } catch (err: any) {
      setError(err.message || 'Failed to load contacts');
    } finally {
      setLoading(false);
    }
  }, [search, page, pageSize]);

  useEffect(() => {
    fetchContacts();
  }, [fetchContacts]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Customer Directory</h2>
          <p className="text-sm text-slate-500">
            Contacts automatically created and updated from caller phone interactions.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchContacts()}
            title="Refresh"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name, phone, or email..."
            className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
          />
        </div>

        <p className="text-xs text-slate-500">
          Showing <span className="font-semibold text-slate-800">{items.length}</span> of{' '}
          <span className="font-semibold text-slate-800">{total}</span> contacts
        </p>
      </div>

      {/* Contacts Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        {error && (
          <div className="p-4 bg-red-50 text-red-700 text-sm border-b border-red-200">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="divide-y divide-slate-100">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-full bg-slate-200" />
                  <div className="space-y-1.5">
                    <div className="h-4 bg-slate-200 rounded w-36" />
                    <div className="h-3 bg-slate-100 rounded w-24" />
                  </div>
                </div>
                <div className="h-3 bg-slate-100 rounded w-16" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
              <Users className="w-6 h-6" />
            </div>
            <h3 className="text-base font-semibold text-slate-800">No contacts found</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {search
                ? `No contacts matching "${search}".`
                : 'Customer profiles will automatically be created when callers interact with your AI receptionist.'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((c) => (
              <div
                key={c.id}
                onClick={() => setSelectedContactId(c.id)}
                className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/80 cursor-pointer transition"
              >
                <div className="flex items-center space-x-3.5 min-w-0">
                  <div className="w-10 h-10 rounded-full bg-blue-50 text-blue-700 border border-blue-200 flex items-center justify-center font-bold text-sm flex-shrink-0">
                    {c.name ? c.name[0].toUpperCase() : 'C'}
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-center space-x-2 mb-0.5">
                      <span className="text-sm font-bold text-slate-900 truncate">
                        {c.name || 'Unregistered Caller'}
                      </span>
                      {c.do_not_contact && (
                        <span className="text-[10px] font-bold px-1.5 py-0.2 bg-red-100 text-red-700 border border-red-200 rounded flex items-center">
                          <Ban className="w-2.5 h-2.5 mr-0.5" /> DNC
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span className="flex items-center">
                        <Phone className="w-3 h-3 mr-1 text-slate-400" />
                        {c.phone}
                      </span>
                      {c.email && (
                        <span className="flex items-center">
                          <Mail className="w-3 h-3 mr-1 text-slate-400" />
                          {c.email}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Metrics and Date */}
                <div className="flex items-center space-x-6 text-xs text-slate-500 self-end sm:self-center">
                  <div className="text-right hidden md:block">
                    <span className="font-semibold text-slate-800">{c.call_count}</span> calls &middot;{' '}
                    <span className="font-semibold text-slate-800">{c.appointment_count}</span> bookings
                  </div>
                  <span className="text-slate-400 text-[11px]">{formatDate(c.created_at)}</span>
                  <span className="text-blue-600 font-semibold text-xs">&rarr;</span>
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

      {/* Contact Detail Drawer */}
      <ContactDetailDrawer
        contactId={selectedContactId}
        isOpen={Boolean(selectedContactId)}
        onClose={() => setSelectedContactId(null)}
        onRefresh={() => fetchContacts()}
      />
    </div>
  );
}
