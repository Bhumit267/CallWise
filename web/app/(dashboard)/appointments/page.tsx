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
        return 'bg-emerald-100 text-emerald-800 border-emerald-200';
      case 'completed':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'cancelled':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'rescheduled':
        return 'bg-amber-100 text-amber-800 border-amber-200';
      default:
        return 'bg-slate-100 text-slate-800 border-slate-200';
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Appointments & Bookings
          </h2>
          <p className="text-sm text-slate-500">
            Real-time schedule of appointments booked by your AI receptionist or staff.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="flex items-center bg-white border border-slate-200 rounded-lg p-0.5 shadow-sm">
            <button
              onClick={() => setViewMode('list')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-md text-xs font-semibold transition',
                viewMode === 'list'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              )}
            >
              <List className="w-3.5 h-3.5 mr-1.5" /> Agenda
            </button>
            <button
              onClick={() => setViewMode('calendar')}
              className={cn(
                'flex items-center px-3 py-1.5 rounded-md text-xs font-semibold transition',
                viewMode === 'calendar'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 hover:text-slate-900'
              )}
            >
              <CalendarDays className="w-3.5 h-3.5 mr-1.5" /> Timeline
            </button>
          </div>

          <button
            onClick={() => fetchAppointments()}
            title="Refresh"
            className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm"
          >
            <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
          </button>

          <button
            onClick={() => setIsBookModalOpen(true)}
            className="inline-flex items-center px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-semibold rounded-lg shadow-sm transition"
          >
            <PlusCircle className="w-4 h-4 mr-2" /> Book Appointment
          </button>
        </div>
      </div>

      {/* Sync Status Banner */}
      <div className="bg-blue-50/70 border border-blue-200 rounded-xl px-4 py-3 flex items-center justify-between text-xs text-blue-900">
        <div className="flex items-center space-x-2">
          <CalendarIcon className="w-4 h-4 text-blue-600 flex-shrink-0" />
          <span>
            <span className="font-semibold">Calendar Sync Active:</span> Inbound booking conflicts are prevented automatically across your business schedule.
          </span>
        </div>
        <span className="font-semibold text-blue-700 bg-blue-100/80 px-2 py-0.5 rounded">
          Sync Connected
        </span>
      </div>

      {/* Filters and Search Bar */}
      {viewMode === 'list' && (
        <div className="bg-white p-4 rounded-xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            {/* Status Pills */}
            <div className="flex items-center space-x-1.5 overflow-x-auto pb-1 lg:pb-0">
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
                      'px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition',
                      isActive
                        ? 'bg-blue-600 text-white shadow-sm'
                        : 'text-slate-600 hover:bg-slate-100'
                    )}
                  >
                    {f.label}
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
                placeholder="Search customer, phone, or service..."
                className="w-full pl-9 pr-3.5 py-2 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
              />
            </div>
          </div>
        </div>
      )}

      {/* Agenda List View */}
      {viewMode === 'list' ? (
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
                  <div className="h-4 bg-slate-200 rounded w-20" />
                </div>
              ))}
            </div>
          ) : items.length === 0 ? (
            <div className="py-16 text-center space-y-3">
              <div className="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto">
                <CalendarIcon className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-slate-800">No appointments found</h3>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                {search
                  ? `No bookings matching "${search}".`
                  : 'Appointments scheduled by your callers or booked manually will appear here.'}
              </p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {items.map((apt) => (
                <div
                  key={apt.id}
                  onClick={() => setSelectedAppointmentId(apt.id)}
                  className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/80 cursor-pointer transition"
                >
                  <div className="flex items-start sm:items-center space-x-3.5 min-w-0">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center justify-center flex-shrink-0">
                      <Clock className="w-5 h-5" />
                    </div>

                    <div className="min-w-0">
                      <div className="flex items-center space-x-2 mb-0.5">
                        <span className="text-sm font-bold text-slate-900 truncate">
                          {apt.customer_name}
                        </span>
                        <span
                          className={cn(
                            'text-[10px] font-semibold px-2 py-0.5 rounded-full border uppercase tracking-wider',
                            getStatusBadge(apt.status)
                          )}
                        >
                          {apt.status}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                        <span className="font-semibold text-slate-700">
                          {apt.service_name}
                        </span>
                        <span className="flex items-center">
                          <Phone className="w-3 h-3 mr-1 text-slate-400" />
                          {apt.customer_phone}
                        </span>
                        <span className="flex items-center text-slate-700">
                          <CalendarIcon className="w-3 h-3 mr-1 text-slate-400" />
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
                          className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg text-xs flex items-center"
                        >
                          <RotateCcw className="w-3.5 h-3.5 mr-1" /> Reschedule
                        </button>
                        <button
                          onClick={() => setCancelTarget(apt)}
                          title="Cancel"
                          className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg text-xs flex items-center"
                        >
                          <Ban className="w-3.5 h-3.5 mr-1" /> Cancel
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
            <div className="px-6 py-4 border-t border-slate-100 flex items-center justify-between bg-slate-50/50">
              <p className="text-xs text-slate-500">
                Page <span className="font-semibold text-slate-700">{page}</span> of{' '}
                <span className="font-semibold text-slate-700">{pages}</span> ({total} bookings)
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
      ) : (
        /* Calendar Timeline View */
        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-900">Upcoming Timeline Schedule</h3>
          {calendarItems.length === 0 ? (
            <div className="py-12 text-center text-xs text-slate-500">
              No appointments scheduled for the current 14-day window.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {calendarItems.map((item) => (
                <div
                  key={item.id}
                  onClick={() => setSelectedAppointmentId(item.id)}
                  className="p-3.5 border border-slate-200 rounded-xl hover:border-blue-400 hover:shadow-sm cursor-pointer transition bg-slate-50/50"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs font-bold text-slate-900 truncate">
                      {item.customer_name}
                    </span>
                    <span
                      className={cn(
                        'text-[10px] font-semibold px-2 py-0.2 rounded-full border uppercase',
                        getStatusBadge(item.status)
                      )}
                    >
                      {item.status}
                    </span>
                  </div>
                  <p className="text-xs text-blue-600 font-medium mb-1">{item.service_name}</p>
                  <p className="text-[11px] text-slate-500">{formatDate(item.start_at)}</p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Modals & Drawers */}
      <BookAppointmentModal
        isOpen={isBookModalOpen}
        onClose={() => setIsBookModalOpen(false)}
        onSuccess={() => fetchAppointments()}
      />

      <AppointmentDetailDrawer
        appointmentId={selectedAppointmentId}
        isOpen={Boolean(selectedAppointmentId)}
        onClose={() => setSelectedAppointmentId(null)}
        onRefresh={() => fetchAppointments()}
      />

      {rescheduleTarget && (
        <RescheduleModal
          isOpen={Boolean(rescheduleTarget)}
          onClose={() => setRescheduleTarget(null)}
          onSuccess={() => fetchAppointments()}
          appointmentId={rescheduleTarget.id}
          customerName={rescheduleTarget.customer_name}
          currentStart={rescheduleTarget.start_at}
        />
      )}

      {cancelTarget && (
        <CancelModal
          isOpen={Boolean(cancelTarget)}
          onClose={() => setCancelTarget(null)}
          onSuccess={() => fetchAppointments()}
          appointmentId={cancelTarget.id}
          customerName={cancelTarget.customer_name}
          serviceName={cancelTarget.service_name}
          startAt={cancelTarget.start_at}
        />
      )}
    </div>
  );
}
