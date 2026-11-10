'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { AppointmentListItem, PaginatedResponse, AppointmentCalendarItem } from '@/types/api';
import { BookAppointmentModal } from '@/components/appointments/book-appointment-modal';
import { AppointmentDetailDrawer } from '@/components/appointments/appointment-detail-drawer';
import { RescheduleModal } from '@/components/appointments/reschedule-modal';
import { CancelModal } from '@/components/appointments/cancel-modal';
import {
  Calendar as CalendarIcon,
  PlusCircle,
  Search,
  Filter,
  RefreshCw,
  Clock,
  User,
  Phone,
  ChevronLeft,
  ChevronRight,
  RotateCcw,
  Ban,
  CheckCircle2,
  CalendarDays,
  List,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const STATUS_FILTERS = [
  { id: 'all', label: 'All Statuses' },
  { id: 'booked', label: 'Booked' },
  { id: 'completed', label: 'Completed' },
  { id: 'rescheduled', label: 'Rescheduled' },
  { id: 'cancelled', label: 'Cancelled' },
];

export default function AppointmentsPage() {
  const [viewMode, setViewMode] = useState<'list' | 'calendar'>('list');
  const [statusFilter, setStatusFilter] = useState('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);

  const [items, setItems] = useState<AppointmentListItem[]>([]);
  const [calendarItems, setCalendarItems] = useState<AppointmentCalendarItem[]>([]);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected item modals
  const [selectedAppointmentId, setSelectedAppointmentId] = useState<string | null>(null);
  const [isBookModalOpen, setIsBookModalOpen] = useState(false);
  const [rescheduleTarget, setRescheduleTarget] = useState<AppointmentListItem | null>(null);
  const [cancelTarget, setCancelTarget] = useState<AppointmentListItem | null>(null);

  const fetchAppointments = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (viewMode === 'list') {
        const params = new URLSearchParams();
        if (statusFilter !== 'all') params.set('status', statusFilter);
        if (search.trim()) params.set('search', search.trim());
        params.set('page', page.toString());
        params.set('page_size', pageSize.toString());

        const res = await apiClient<PaginatedResponse<AppointmentListItem>>(
          `/api/appointments?${params.toString()}`
        );
        setItems(res.items || []);
        setTotal(res.total || 0);
        setPages(res.pages || 1);
      } else {
        // Fetch 14 day window for calendar view
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 3);
        const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 11);

        const data = await apiClient<AppointmentCalendarItem[]>(
          `/api/appointments/calendar?start_date=${start.toISOString()}&end_date=${end.toISOString()}`
        );
        setCalendarItems(data || []);
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load appointments');
    } finally {
      setLoading(false);
    }
  }, [viewMode, statusFilter, search, page, pageSize]);

  useEffect(() => {
    fetchAppointments();
  }, [fetchAppointments]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getStatusBadge = (status: string) => {
    switch (status.toLowerCase()) {
      case 'booked':
        return 'bg-[#dcfce7] text-emerald-950';
      case 'completed':
        return 'bg-[#dbeafe] text-blue-950';
      case 'cancelled':
        return 'bg-[#fee2e2] text-rose-950';
      case 'rescheduled':
        return 'bg-[#fef9c3] text-amber-950';
      default:
        return 'bg-neutral-100 text-black';
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Appointments & Bookings
            </h2>
            <span className="bg-[#ffe600] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Live Calendar
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Real-time schedule of appointments booked by your AI receptionist or staff.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-white brutal-border rounded-xl p-1 brutal-shadow-xs">
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition',
                viewMode === 'list'
                  ? 'bg-black text-white'
                  : 'text-neutral-700 hover:text-black'
              )}
            >
              <List className="w-3.5 h-3.5 mr-1.5 stroke-[2.5]" /> Agenda
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-lg text-xs font-black uppercase tracking-wider transition',
                viewMode === 'calendar'
                  ? 'bg-black text-white'
                  : 'text-neutral-700 hover:text-black'
              )}
            >
              <CalendarDays className="w-3.5 h-3.5 mr-1.5 stroke-[2.5]" /> Timeline
            </button>
          </div>

          <button
            onClick={() => fetchAppointments()}
            title="Refresh"
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>

          <button
            onClick={() => setIsBookModalOpen(true)}
            className="inline-flex items-center px-4 py-2.5 bg-[#10b981] hover:bg-[#059669] text-white text-xs font-black uppercase tracking-wider rounded-xl brutal-border brutal-shadow brutal-shadow-hover"
          >
            <PlusCircle className="w-4 h-4 mr-2" /> Book Appointment
          </button>
        </div>
      </div>

      {/* Sync Status Banner */}
      <div className="bg-[#dbeafe] brutal-border rounded-2xl p-4 brutal-shadow-xs flex items-center justify-between text-xs text-blue-950 font-bold">
        <div className="flex items-center space-x-2.5">
          <CalendarIcon className="w-5 h-5 text-blue-700 flex-shrink-0" />
          <span>
            <span className="font-black uppercase tracking-wider">Calendar Sync Active:</span> Inbound booking conflicts are prevented automatically across your schedule.
          </span>
        </div>
        <span className="font-black uppercase tracking-wider text-[10px] bg-white text-blue-800 brutal-border px-2.5 py-1 rounded-md brutal-shadow-xs">
          Sync Connected
        </span>
      </div>

      {/* Filters and Search Bar */}
      {viewMode === 'list' && (
        <div className="bg-white p-4 rounded-2xl brutal-border-3 brutal-shadow space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Status Pills */}
            <div className="flex items-center space-x-2 overflow-x-auto pb-1 lg:pb-0">
              {STATUS_FILTERS.map((f) => {
                const isActive = statusFilter === f.id;
                return (
                  <button
                    key={f.id}
                    onClick={() => {
                      setStatusFilter(f.id);
                      setPage(1);
                    }}
                    className={cn(
                      'px-3.5 py-2 rounded-xl text-xs font-black uppercase tracking-wider whitespace-nowrap transition-all duration-100',
                      isActive
                        ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs translate-x-[1px]'
                        : 'bg-neutral-100 text-neutral-700 hover:text-black hover:bg-neutral-200 border-2 border-transparent hover:border-black'
                    )}
                  >
                    {f.label}
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
                placeholder="Search customer, phone, or service..."
                className="brutal-input pl-10 text-xs font-bold"
              />
            </div>
          </div>
        </div>
      )}

      {/* Agenda List View */}
      {viewMode === 'list' ? (
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
                  <div className="h-4 bg-neutral-200 rounded w-20" />
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <div className="w-14 h-14 rounded-2xl bg-neutral-100 text-black brutal-border brutal-shadow flex items-center justify-center mx-auto rotate-[-6deg]">
                <CalendarIcon className="w-7 h-7 stroke-[2.5]" />
              </div>
              <h3 className="text-base font-black uppercase text-black">No appointments found</h3>
              <p className="text-xs font-semibold text-neutral-500 max-w-sm mx-auto">
                {search
                  ? `No bookings matching "${search}".`
                  : 'Appointments scheduled by your callers or booked manually will appear here.'}
              </p>
            </div>
          ) : (
            <div className="divide-y-2 divide-black/10">
              {items.map((apt) => (
                <div
                  key={apt.id}
                  onClick={() => setSelectedAppointmentId(apt.id)}
                  className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-amber-50/50 cursor-pointer transition-all duration-100"
                >
                  <div className="flex items-start sm:items-center space-x-4 min-w-0">
                    <div className="w-11 h-11 rounded-xl bg-[#dcfce7] text-emerald-950 brutal-border brutal-shadow-xs flex items-center justify-center flex-shrink-0">
                      <Clock className="w-5 h-5 stroke-[2.5]" />
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center space-x-2 mb-1">
                        <span className="text-sm font-black text-black truncate">
                          {apt.customer_name}
                        </span>
                        <span
                          className={cn(
                            'text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs',
                            getStatusBadge(apt.status)
                          )}
                        >
                          {apt.status}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                        <span className="font-black text-black bg-neutral-100 px-2 py-0.5 rounded brutal-border text-[11px]">
                          {apt.service_name}
                        </span>
                        <span className="flex items-center font-mono font-bold text-neutral-600">
                          <Phone className="w-3.5 h-3.5 mr-1 text-black" />
                          {apt.customer_phone}
                        </span>
                        <span className="flex items-center font-bold text-black bg-[#fef9c3] px-2 py-0.5 rounded brutal-border text-[11px]">
                          <CalendarIcon className="w-3.5 h-3.5 mr-1 text-black" />
                          {formatDate(apt.start_at)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions */}
                  <div
                    className="flex items-center space-x-2 flex-shrink-0 self-end sm:self-center"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {apt.status !== 'cancelled' && (
                      <>
                        <button
                          onClick={() => setRescheduleTarget(apt)}
                          title="Reschedule"
                          className="px-2.5 py-1 bg-white brutal-border brutal-shadow-xs text-xs font-black uppercase text-black hover:bg-neutral-100 rounded-lg flex items-center"
                        >
                          <RotateCcw className="w-3 h-3 mr-1" /> Reschedule
                        </button>
                        <button
                          onClick={() => setCancelTarget(apt)}
                          title="Cancel"
                          className="px-2.5 py-1 bg-rose-100 brutal-border brutal-shadow-xs text-xs font-black uppercase text-rose-950 hover:bg-rose-200 rounded-lg flex items-center"
                        >
                          <Ban className="w-3 h-3 mr-1" /> Cancel
                        </button>
                      </>
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
                <span className="text-black">{pages}</span> ({total} bookings)
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
      ) : (
        /* Timeline View */
        <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg p-6">
          <h3 className="text-base font-black uppercase text-black mb-4">14-Day Booking Schedule</h3>
          {calendarItems.length === 0 ? (
            <p className="text-xs font-semibold text-neutral-500">No appointments scheduled in the next 14 days.</p>
          ) : (
            <div className="space-y-3">
              {calendarItems.map((ci) => (
                <div key={ci.id} className="p-3 bg-neutral-50 brutal-border rounded-xl flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-xs font-bold text-black">{formatDate(ci.start_at)}</span>
                    <span className="font-black text-sm text-black">{ci.customer_name}</span>
                    <span className="text-xs font-bold text-neutral-600">({ci.service_name})</span>
                  </div>
                  <span className={cn('text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border', getStatusBadge(ci.status))}>
                    {ci.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Book Appointment Modal */}
      <BookAppointmentModal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
        onSuccess={() => {
          fetchAppointments();
        }}
      />

      {/* Reschedule Modal */}
      {rescheduleTarget && (
        <RescheduleModal
          isOpen={Boolean(rescheduleTarget)}
          appointmentId={rescheduleTarget.id}
          customerName={rescheduleTarget.customer_name}
          currentStart={rescheduleTarget.start_at}
          onClose={() => setRescheduleTarget(null)}
          onSuccess={() => {
            setRescheduleTarget(null);
            fetchAppointments();
          }}
        />
      )}

      {/* Cancel Modal */}
      {cancelTarget && (
        <CancelModal
          isOpen={Boolean(cancelTarget)}
          appointmentId={cancelTarget.id}
          customerName={cancelTarget.customer_name}
          serviceName={cancelTarget.service_name}
          startAt={cancelTarget.start_at}
          onClose={() => setCancelTarget(null)}
          onSuccess={() => {
            setCancelTarget(null);
            fetchAppointments();
          }}
        />
      )}

      {/* Appointment Detail Drawer */}
      <AppointmentDetailDrawer
        appointmentId={selectedAppointmentId}
        isOpen={Boolean(selectedAppointmentId)}
        onClose={() => setSelectedAppointmentId(null)}
        onRefresh={() => {
          fetchAppointments();
        }}
      />
    </div>
  );
}
