'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { ContactDetail } from '@/types/api';
import { EditContactModal } from './edit-contact-modal';
import { GdprScrubModal } from './gdpr-scrub-modal';
import {
  X,
  User,
  Phone,
  Mail,
  Calendar,
  Clock,
  MessageSquare,
  CheckCircle2,
  Edit2,
  Trash2,
  Ban,
  Loader2,
  ListTodo,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface ContactDetailDrawerProps {
  contactId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onRefresh: () => void;
}

export function ContactDetailDrawer({
  contactId,
  isOpen,
  onClose,
  onRefresh,
}: ContactDetailDrawerProps) {
  const [contact, setContact] = useState<ContactDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'calls' | 'appointments' | 'messages' | 'follow_ups'>('calls');

  const [isEditOpen, setIsEditOpen] = useState(false);
  const [isScrubOpen, setIsScrubOpen] = useState(false);

  useEffect(() => {
    if (!isOpen || !contactId) {
      setContact(null);
      return;
    }

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient<ContactDetail>(`/api/contacts/${contactId}`);
        setContact(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load contact profile');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [isOpen, contactId]);

  if (!isOpen) return null;

  const formatDate = (isoString: string) => {
    const date = new Date(isoString);
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-white shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out">
        {/* Header */}
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3 truncate">
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center flex-shrink-0">
              <User className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h2 className="text-base font-bold text-slate-900 truncate">
                {contact?.name || contact?.phone || (loading ? 'Loading...' : 'Contact')}
              </h2>
              <p className="text-xs text-slate-500">{contact?.phone}</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {contact && (
              <>
                <button
                  onClick={() => setIsEditOpen(true)}
                  className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-200/60 rounded-lg text-xs flex items-center"
                  title="Edit profile"
                >
                  <Edit2 className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setIsScrubOpen(true)}
                  className="p-1.5 text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg text-xs flex items-center"
                  title="GDPR Scrub"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </>
            )}
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-200/60"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              <p className="text-sm">Loading contact profile & history...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
              {error}
            </div>
          ) : contact ? (
            <>
              {/* Profile Card */}
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Contact Information
                  </span>
                  {contact.do_not_contact && (
                    <span className="text-[11px] font-bold px-2 py-0.5 bg-red-100 text-red-700 border border-red-200 rounded-full flex items-center">
                      <Ban className="w-3 h-3 mr-1" /> DNC Active
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400 block mb-0.5">Phone Number</span>
                    <a
                      href={`tel:${contact.phone}`}
                      className="font-semibold text-blue-600 hover:underline text-sm"
                    >
                      {contact.phone}
                    </a>
                  </div>

                  {contact.email && (
                    <div>
                      <span className="text-slate-400 block mb-0.5">Email</span>
                      <p className="font-medium text-slate-800">{contact.email}</p>
                    </div>
                  )}

                  <div className="col-span-2">
                    <span className="text-slate-400 block mb-0.5">Internal Notes</span>
                    <p className="text-slate-700 italic">
                      {contact.notes || 'No staff notes recorded yet.'}
                    </p>
                  </div>
                </div>
              </div>

              {/* History Tabs */}
              <div className="space-y-3">
                <div className="flex items-center space-x-1 border-b border-slate-200 pb-2">
                  <button
                    onClick={() => setActiveTab('calls')}
                    className={cn(
                      'px-3 py-1 text-xs font-semibold rounded-lg transition',
                      activeTab === 'calls'
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    )}
                  >
                    Calls ({contact.calls.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('appointments')}
                    className={cn(
                      'px-3 py-1 text-xs font-semibold rounded-lg transition',
                      activeTab === 'appointments'
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    )}
                  >
                    Bookings ({contact.appointments.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('messages')}
                    className={cn(
                      'px-3 py-1 text-xs font-semibold rounded-lg transition',
                      activeTab === 'messages'
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    )}
                  >
                    Messages ({contact.messages.length})
                  </button>
                  <button
                    onClick={() => setActiveTab('follow_ups')}
                    className={cn(
                      'px-3 py-1 text-xs font-semibold rounded-lg transition',
                      activeTab === 'follow_ups'
                        ? 'bg-blue-600 text-white'
                        : 'text-slate-600 hover:bg-slate-100'
                    )}
                  >
                    Tasks ({contact.follow_ups.length})
                  </button>
                </div>

                {/* Tab Views */}
                <div className="pt-1">
                  {activeTab === 'calls' && (
                    <div className="space-y-2">
                      {contact.calls.length === 0 ? (
                        <p className="text-xs text-slate-400 py-4 text-center">No calls recorded.</p>
                      ) : (
                        contact.calls.map((c) => (
                          <div
                            key={c.id}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1"
                          >
                            <div className="flex items-center justify-between text-slate-500 text-[11px]">
                              <span>{formatDate(c.started_at)}</span>
                              <span>{Math.round(c.duration_seconds)}s</span>
                            </div>
                            <p className="text-slate-800">{c.summary || 'Inbound phone call'}</p>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {activeTab === 'appointments' && (
                    <div className="space-y-2">
                      {contact.appointments.length === 0 ? (
                        <p className="text-xs text-slate-400 py-4 text-center">No bookings recorded.</p>
                      ) : (
                        contact.appointments.map((a) => (
                          <div
                            key={a.id}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs flex items-center justify-between"
                          >
                            <div>
                              <p className="font-semibold text-slate-800">
                                {a.service_name || 'Appointment'}
                              </p>
                              <p className="text-[11px] text-slate-500">{formatDate(a.start_at)}</p>
                            </div>
                            <span className="text-[11px] font-semibold uppercase px-2 py-0.5 bg-slate-200/80 rounded">
                              {a.status}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {activeTab === 'messages' && (
                    <div className="space-y-2">
                      {contact.messages.length === 0 ? (
                        <p className="text-xs text-slate-400 py-4 text-center">No messages recorded.</p>
                      ) : (
                        contact.messages.map((m) => (
                          <div
                            key={m.id}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-1"
                          >
                            <span className="text-[11px] text-slate-400">{formatDate(m.created_at)}</span>
                            <p className="text-slate-800">{m.reason}</p>
                          </div>
                        ))
                      )}
                    </div>
                  )}

                  {activeTab === 'follow_ups' && (
                    <div className="space-y-2">
                      {contact.follow_ups.length === 0 ? (
                        <p className="text-xs text-slate-400 py-4 text-center">No pending tasks.</p>
                      ) : (
                        contact.follow_ups.map((f) => (
                          <div
                            key={f.id}
                            className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs flex items-center justify-between"
                          >
                            <p className="font-semibold text-slate-800">{f.title}</p>
                            <span className="text-[11px] uppercase px-2 py-0.5 bg-slate-200 rounded">
                              {f.status}
                            </span>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {contact && (
        <EditContactModal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          onSuccess={() => {
            onRefresh();
            onClose();
          }}
          contact={contact}
        />
      )}

      {contact && (
        <GdprScrubModal
          isOpen={isScrubOpen}
          onClose={() => setIsScrubOpen(false)}
          onSuccess={() => {
            onRefresh();
            onClose();
          }}
          contactId={contact.id}
          contactName={contact.name}
          phone={contact.phone}
        />
      )}
    </>
  );
}
