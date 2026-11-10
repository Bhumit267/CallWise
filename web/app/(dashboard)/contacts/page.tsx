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
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Customer Directory
            </h2>
            <span className="bg-[#ffe600] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Auto Synced
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Contacts automatically created and updated from caller phone interactions.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => fetchContacts()}
            title="Refresh"
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="bg-white p-4 rounded-2xl brutal-border-3 brutal-shadow flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="w-4 h-4 text-black absolute left-3.5 top-3" />
          <input
            type="text"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Search by name, phone, or email..."
            className="brutal-input pl-10 text-xs font-bold"
          />
        </div>

        <div className="text-xs font-black uppercase text-neutral-700 bg-neutral-100 px-3 py-1.5 rounded-lg brutal-border">
          Showing <span className="text-black">{items.length}</span> of{' '}
          <span className="text-black">{total}</span> contacts
        </div>
      </div>

      {/* Contacts Table */}
      <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
        {error && (
          <div className="p-4 bg-rose-100 text-rose-950 text-xs font-black uppercase border-b-2 border-black">
            {error}
          </div>
        )}

        {loading && items.length === 0 ? (
          <div className="divide-y-2 divide-black/10">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="p-4 flex items-center justify-between animate-pulse">
                <div className="flex items-center space-x-4">
                  <div className="w-11 h-11 rounded-xl bg-neutral-200 brutal-border" />
                  <div className="space-y-1.5">
                    <div className="h-4 bg-neutral-200 rounded w-36" />
                    <div className="h-3 bg-neutral-100 rounded w-24" />
                  </div>
                </div>
                <div className="h-3 bg-neutral-100 rounded w-16" />
              </div>
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <div className="w-14 h-14 rounded-2xl bg-neutral-100 text-black brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
              <Users className="w-7 h-7 stroke-[2.5]" />
            </div>
            <h3 className="text-base font-black uppercase text-black">No contacts found</h3>
            <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
              {search
                ? `No contacts matching "${search}".`
                : 'Customer profiles will automatically be created when callers interact with your AI receptionist.'}
            </p>
          </div>
        ) : (
          <div className="divide-y-2 divide-black/10">
            {items.map((c) => (
              <div
                key={c.id}
                onClick={() => setSelectedContactId(c.id)}
                className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-amber-50/50 cursor-pointer transition-all duration-100"
              >
                <div className="flex items-center space-x-4 min-w-0">
                  <div className="w-11 h-11 rounded-xl bg-[#ffe600] text-black brutal-border brutal-shadow-xs flex items-center justify-center font-black text-sm flex-shrink-0">
                    {c.name ? c.name[0].toUpperCase() : 'C'}
                  </div>

                  <div className="min-w-0">
                    <div className="flex items-center space-x-2 mb-1">
                      <span className="text-sm font-black text-black truncate">
                        {c.name || 'Unregistered Caller'}
                      </span>
                      {c.do_not_contact && (
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 bg-rose-100 text-rose-950 brutal-border brutal-shadow-xs rounded flex items-center">
                          <Ban className="w-3 h-3 mr-1" /> DNC
                        </span>
                      )}
                    </div>

                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
                      <span className="flex items-center font-mono font-bold text-black">
                        <Phone className="w-3.5 h-3.5 mr-1 text-black" />
                        {c.phone}
                      </span>
                      {c.email && (
                        <span className="flex items-center font-mono text-neutral-600">
                          <Mail className="w-3.5 h-3.5 mr-1 text-neutral-400" />
                          {c.email}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Metrics and Date */}
                <div className="flex items-center space-x-4 text-xs self-end sm:self-center">
                  <div className="flex items-center gap-2 hidden md:flex">
                    <span className="font-black bg-neutral-100 px-2 py-0.5 rounded brutal-border text-[11px] text-black">
                      {c.call_count} calls
                    </span>
                    <span className="font-black bg-[#dcfce7] px-2 py-0.5 rounded brutal-border text-[11px] text-emerald-950">
                      {c.appointment_count} bookings
                    </span>
                  </div>
                  <span className="font-mono text-neutral-500 text-[11px] font-bold">{formatDate(c.created_at)}</span>
                  <span className="text-black font-black text-xs">&rarr;</span>
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
              <span className="text-black">{pages}</span> ({total} contacts)
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

      {/* Contact Detail Drawer */}
      <ContactDetailDrawer
        contactId={selectedContactId}
        isOpen={Boolean(selectedContactId)}
        onClose={() => setSelectedContactId(null)}
        onRefresh={() => {
          fetchContacts();
        }}
      />
    </div>
  );
}
