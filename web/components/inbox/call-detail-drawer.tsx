'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { CallDetail } from '@/types/api';
import { AudioPlayer } from './audio-player';
import { CreateFollowUpModal } from './create-follow-up-modal';
import {
  X,
  Phone,
  User,
  Clock,
  Calendar,
  Sparkles,
  Zap,
  ArrowRightLeft,
  MessageSquare,
  HelpCircle,
  PlusCircle,
  Loader2,
  CheckCircle2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface CallDetailDrawerProps {
  callId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onFollowUpCreated?: () => void;
}

export function CallDetailDrawer({
  callId,
  isOpen,
  onClose,
  onFollowUpCreated,
}: CallDetailDrawerProps) {
  const [call, setCall] = useState<CallDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isFollowUpModalOpen, setIsFollowUpModalOpen] = useState(false);

  useEffect(() => {
    if (!isOpen || !callId) {
      setCall(null);
      return;
    }

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient<CallDetail>(`/api/calls/${callId}`);
        setCall(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load call details');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [isOpen, callId]);

  if (!isOpen) return null;

  const formatDuration = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}m ${s < 10 ? '0' : ''}${s}s`;
  };

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
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out">
        {/* Header */}
        <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="flex items-center space-x-3 truncate">
            <div className="w-9 h-9 rounded-full bg-blue-100 text-blue-600 flex items-center justify-center flex-shrink-0">
              <Phone className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h2 className="text-base font-bold text-slate-900 truncate">
                {call?.caller_number || (loading ? 'Loading...' : 'Call Details')}
              </h2>
              <p className="text-xs text-slate-500">
                {call?.contact_name ? `Contact: ${call.contact_name}` : 'Unregistered Caller'}
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsFollowUpModalOpen(true)}
              className="inline-flex items-center text-xs font-semibold px-3 py-1.5 bg-blue-50 text-blue-700 hover:bg-blue-100 rounded-lg transition"
            >
              <PlusCircle className="w-3.5 h-3.5 mr-1.5" /> Follow-up
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-200/60"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading ? (
            <div className="py-24 flex flex-col items-center justify-center text-slate-400 space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              <p className="text-sm">Loading complete call transcript and details...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
              {error}
            </div>
          ) : call ? (
            <>
              {/* Metadata Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold flex items-center">
                    <Clock className="w-3 h-3 mr-1" /> Duration
                  </span>
                  <p className="text-sm font-bold text-slate-800 mt-0.5">
                    {formatDuration(call.duration_seconds)}
                  </p>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold flex items-center">
                    <Calendar className="w-3 h-3 mr-1" /> Started At
                  </span>
                  <p className="text-xs font-medium text-slate-800 mt-1 truncate">
                    {formatDate(call.started_at)}
                  </p>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold flex items-center">
                    <User className="w-3 h-3 mr-1" /> Turns
                  </span>
                  <p className="text-sm font-bold text-slate-800 mt-0.5">
                    {call.turns.length} messages
                  </p>
                </div>

                <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
                  <span className="text-[11px] text-slate-400 uppercase font-semibold flex items-center">
                    <Zap className="w-3 h-3 mr-1" /> AI Engine
                  </span>
                  <p className="text-xs font-medium text-slate-800 mt-1 truncate">
                    {call.llm_model || 'gpt-4o-mini'}
                  </p>
                </div>
              </div>

              {/* Audio Playback */}
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                  Call Recording
                </h3>
                <AudioPlayer
                  audioUrl={call.audio_url}
                  durationSeconds={call.duration_seconds}
                />
              </div>

              {/* AI Call Summary */}
              {call.summary && (
                <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-4">
                  <div className="flex items-center space-x-2 text-blue-700 mb-1.5">
                    <Sparkles className="w-4 h-4" />
                    <h3 className="text-xs font-bold uppercase tracking-wider">AI Executive Summary</h3>
                  </div>
                  <p className="text-sm text-slate-800 leading-relaxed">{call.summary}</p>
                </div>
              )}

              {/* Linked Records: Appointments, Messages, Transfers, Knowledge Misses */}
              {(call.appointments.length > 0 ||
                call.messages.length > 0 ||
                call.transfers.length > 0 ||
                call.knowledge_misses.length > 0) && (
                <div className="space-y-3">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Outcomes & Actions Taken
                  </h3>

                  <div className="space-y-2">
                    {call.appointments.map((apt) => (
                      <div
                        key={apt.id}
                        className="flex items-center justify-between p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-900"
                      >
                        <div className="flex items-center space-x-2.5">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                          <div>
                            <p className="text-xs font-bold">Appointment Booked: {apt.customer_name}</p>
                            <p className="text-[11px] text-emerald-700">{formatDate(apt.start_at)}</p>
                          </div>
                        </div>
                        <span className="text-xs font-semibold px-2 py-0.5 bg-emerald-200/60 rounded uppercase">
                          {apt.status}
                        </span>
                      </div>
                    ))}

                    {call.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className="flex items-center justify-between p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-900"
                      >
                        <div className="flex items-center space-x-2.5">
                          <MessageSquare className="w-4 h-4 text-amber-600 flex-shrink-0" />
                          <div>
                            <p className="text-xs font-bold">Message Taken: {msg.caller_name}</p>
                            <p className="text-[11px] text-amber-700">{msg.reason}</p>
                          </div>
                        </div>
                        <span className="text-xs font-mono text-amber-800">{msg.callback_number}</span>
                      </div>
                    ))}

                    {call.transfers.map((tr) => (
                      <div
                        key={tr.id}
                        className="flex items-center justify-between p-3 bg-purple-50 border border-purple-200 rounded-lg text-purple-900"
                      >
                        <div className="flex items-center space-x-2.5">
                          <ArrowRightLeft className="w-4 h-4 text-purple-600 flex-shrink-0" />
                          <div>
                            <p className="text-xs font-bold">Call Transfer Initiated</p>
                            <p className="text-[11px] text-purple-700">{tr.reason}</p>
                          </div>
                        </div>
                        <span className="text-xs uppercase px-2 py-0.5 bg-purple-200/60 rounded">
                          {tr.status}
                        </span>
                      </div>
                    ))}

                    {call.knowledge_misses.map((km) => (
                      <div
                        key={km.id}
                        className="flex items-center justify-between p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-900"
                      >
                        <div className="flex items-center space-x-2.5">
                          <HelpCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
                          <div>
                            <p className="text-xs font-bold">Unanswered Question Flagged</p>
                            <p className="text-[11px] text-rose-700">"{km.query}"</p>
                          </div>
                        </div>
                        <span className="text-xs uppercase px-2 py-0.5 bg-rose-200/60 rounded">
                          {km.status}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Turn-by-turn Transcript */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
                    Dialogue Transcript ({call.turns.length} turns)
                  </h3>
                </div>

                <div className="space-y-4 pt-1">
                  {call.turns.length === 0 ? (
                    <div className="p-8 text-center text-slate-400 bg-slate-50 rounded-xl border border-dashed border-slate-200">
                      No turns recorded for this call.
                    </div>
                  ) : (
                    call.turns.map((turn, idx) => {
                      const isAgent = turn.speaker.toLowerCase() === 'agent';
                      return (
                        <div
                          key={turn.id || idx}
                          className={cn(
                            'flex flex-col',
                            isAgent ? 'items-end' : 'items-start'
                          )}
                        >
                          <div className="flex items-center space-x-2 mb-1 px-1">
                            <span className="text-[11px] font-semibold text-slate-500 capitalize">
                              {isAgent ? 'AI Receptionist' : 'Caller'}
                            </span>
                            {turn.latency_ms !== null && turn.latency_ms !== undefined && (
                              <span className="text-[10px] bg-slate-100 text-slate-600 px-1.5 py-0.2 rounded font-mono">
                                ⚡ {Math.round(turn.latency_ms)}ms
                              </span>
                            )}
                          </div>
                          <div
                            className={cn(
                              'max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm',
                              isAgent
                                ? 'bg-blue-600 text-white rounded-br-none'
                                : 'bg-slate-100 text-slate-900 border border-slate-200 rounded-bl-none'
                            )}
                          >
                            {turn.text}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Follow-up Creation Modal */}
      {call && (
        <CreateFollowUpModal
          isOpen={isFollowUpModalOpen}
          onClose={() => setIsFollowUpModalOpen(false)}
          onSuccess={() => {
            if (onFollowUpCreated) onFollowUpCreated();
          }}
          defaultTitle={`Follow up with ${call.caller_number || 'Caller'}`}
          defaultDescription={call.summary ? `Context from call: ${call.summary}` : ''}
          contactId={call.contact_id}
          contactName={call.contact_name}
        />
      )}
    </>
  );
}
