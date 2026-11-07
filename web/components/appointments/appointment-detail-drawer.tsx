'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { AppointmentDetail } from '@/types/api';
import { RescheduleModal } from './reschedule-modal';
import { CancelModal } from './cancel-modal';
import {
  X,
  Calendar,
  Clock,
  User,
  Phone,
  Mail,
  Bell,
  ShieldCheck,
  RotateCcw,
  Ban,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface AppointmentDetailDrawerProps {
  appointmentId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

export function AppointmentDetailDrawer({
  appointmentId,
  isOpen,
  onClose,
  onRefresh,
}: AppointmentDetailDrawerProps) {
  const [appointment, setAppointment] = useState<AppointmentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [isRescheduleOpen, setIsRescheduleOpen] = useState(false);
  const [isCancelOpen, setIsCancelOpen] = useState(false);

  useEffect(() => {
    if (!isOpen || !appointmentId) {
      setAppointment(null);
      return;
    }

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient<AppointmentDetail>(
          `/api/appointments/${appointmentId}`
        );
        setAppointment(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load appointment details');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [isOpen, appointmentId]);

  if (!isOpen) return null;

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
      year: 'numeric',
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
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-white shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out">
        {/* Header */}
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3 truncate">
            <div className="w-9 h-9 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0">
              <Calendar className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h2 className="text-base font-bold text-slate-900 truncate">
                {appointment?.service_name || 'Appointment Details'}
              </h2>
              <p className="text-xs text-slate-500">
                {appointment?.customer_name || (loading ? 'Loading...' : '')}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-200/60"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-600" />
              <p className="text-sm">Loading appointment details...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
              {error}
            </div>
          ) : appointment ? (
            <>
              {/* Status and Action Buttons */}
              <div className="flex items-center justify-between">
                <span
                  className={cn(
                    'text-xs font-semibold px-3 py-1 rounded-full border uppercase tracking-wider',
                    getStatusBadge(appointment.status)
                  )}
                >
                  {appointment.status}
                </span>

                {appointment.status !== 'cancelled' && (
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setIsRescheduleOpen(true)}
                      className="inline-flex items-center text-xs font-semibold px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition"
                    >
                      <RotateCcw className="w-3.5 h-3.5 mr-1.5" /> Reschedule
                    </button>
                    <button
                      onClick={() => setIsCancelOpen(true)}
                      className="inline-flex items-center text-xs font-semibold px-3 py-1.5 bg-red-50 hover:bg-red-100 text-red-700 rounded-lg transition"
                    >
                      <Ban className="w-3.5 h-3.5 mr-1.5" /> Cancel
                    </button>
                  </div>
                )}
              </div>

              {/* Customer Information Card */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                  Customer & Service Details
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 flex items-center mb-0.5">
                      <User className="w-3.5 h-3.5 mr-1" /> Customer
                    </span>
                    <p className="font-semibold text-slate-800 text-sm">
                      {appointment.customer_name}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400 flex items-center mb-0.5">
                      <Phone className="w-3.5 h-3.5 mr-1" /> Phone Number
                    </span>
                    <a
                      href={`tel:${appointment.customer_phone}`}
                      className="font-semibold text-blue-600 hover:underline text-sm"
                    >
                      {appointment.customer_phone}
                    </a>
                  </div>

                  {appointment.customer_email && (
                    <div>
                      <span className="text-slate-400 flex items-center mb-0.5">
                        <Mail className="w-3.5 h-3.5 mr-1" /> Email
                      </span>
                      <p className="font-medium text-slate-700">
                        {appointment.customer_email}
                      </p>
                    </div>
                  )}

                  <div>
                    <span className="text-slate-400 flex items-center mb-0.5">
                      <Clock className="w-3.5 h-3.5 mr-1" /> Scheduled Time
                    </span>
                    <p className="font-medium text-slate-800">
                      {formatDate(appointment.start_at)}
                    </p>
                  </div>
                </div>
              </div>

              {/* Reminders History */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center">
                  <Bell className="w-3.5 h-3.5 mr-1" /> Automated Reminders ({appointment.reminders.length})
                </h3>

                {appointment.reminders.length === 0 ? (
                  <p className="text-xs text-slate-400 bg-slate-50 p-3 rounded-lg border border-slate-200">
                    No automated reminders scheduled for this booking.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {appointment.reminders.map((rem) => (
                      <div
                        key={rem.id}
                        className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs"
                      >
                        <div>
                          <p className="font-semibold text-slate-800 capitalize">
                            {rem.channel} Reminder
                          </p>
                          <p className="text-slate-500 text-[11px]">
                            Scheduled: {formatDate(rem.scheduled_at)}
                          </p>
                        </div>
                        <span className="text-[11px] font-semibold px-2 py-0.5 bg-slate-200/70 rounded capitalize">
                          {rem.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Verification Attempts */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center">
                  <ShieldCheck className="w-3.5 h-3.5 mr-1" /> Security & Verification
                </h3>

                {appointment.verification_attempts.length === 0 ? (
                  <p className="text-xs text-slate-400 bg-slate-50 p-3 rounded-lg border border-slate-200">
                    Standard booking; no verification pin required.
                  </p>
                ) : (
                  <div className="space-y-2">
                    {appointment.verification_attempts.map((v) => (
                      <div
                        key={v.id}
                        className="p-3 bg-slate-50 border border-slate-200 rounded-lg flex items-center justify-between text-xs"
                      >
                        <div className="flex items-center space-x-2">
                          <CheckCircle2
                            className={cn(
                              'w-4 h-4',
                              v.verified ? 'text-emerald-600' : 'text-slate-400'
                            )}
                          />
                          <span className="font-medium text-slate-800">
                            {v.verified ? 'PIN Verified' : 'Attempt Failed'}
                          </span>
                        </div>
                        <span className="text-slate-400 text-[11px]">
                          {formatDate(v.timestamp)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Reschedule Modal */}
      {appointment && (
        <RescheduleModal
          isOpen={isRescheduleOpen}
          onClose={() => setIsRescheduleOpen(false)}
          onSuccess={() => {
            onRefresh();
            onClose();
          }}
          appointmentId={appointment.id}
          customerName={appointment.customer_name}
          currentStart={appointment.start_at}
        />
      )}

      {/* Cancel Modal */}
      {appointment && (
        <CancelModal
          isOpen={isCancelOpen}
          onClose={() => setIsCancelOpen(false)}
          onSuccess={() => {
            onRefresh();
            onClose();
          }}
          appointmentId={appointment.id}
          customerName={appointment.customer_name}
          serviceName={appointment.service_name}
          startAt={appointment.start_at}
        />
      )}
    </>
  );
}
