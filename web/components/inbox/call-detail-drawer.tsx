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
  Globe,
  Radio,
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
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onClose}
      />

      {/* Drawer Container */}
      <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl bg-white border-l-3 border-black brutal-shadow-xl flex flex-col transform transition-transform duration-300 ease-in-out">
        {/* Header */}
        <div className="h-18 px-6 border-b-3 border-black flex items-center justify-between bg-[#ffe600]">
          <div className="flex items-center space-x-3 truncate">
            <div className="w-10 h-10 bg-black text-[#ffe600] brutal-border flex items-center justify-center shrink-0">
              <Phone className="w-5 h-5" />
            </div>
            <div className="truncate">
              <h2 className="text-base font-black text-black uppercase tracking-tight truncate">
                {call?.caller_number || (loading ? 'Loading...' : 'Call Details')}
              </h2>
              <div className="flex items-center space-x-2 mt-0.5">
                <span className={cn(
                  "inline-flex items-center px-2 py-0.5 text-[10px] font-black uppercase brutal-border",
                  (call as any)?.source === 'chat'
                    ? "bg-[#bbf7d0] text-black"
                    : (call as any)?.source === 'web'
                    ? "bg-[#f3e8ff] text-black"
                    : "bg-[#dbeafe] text-black"
                )}>
                  {(call as any)?.source === 'chat' ? (
                    <><MessageSquare className="w-3 h-3 mr-1" /> Chat Widget</>
                  ) : (call as any)?.source === 'web' ? (
                    <><Globe className="w-3 h-3 mr-1" /> Web Audio</>
                  ) : (
                    <><Phone className="w-3 h-3 mr-1" /> Inbound Call</>
                  )}
                </span>
                <p className="text-xs font-bold text-slate-800 truncate">
                  {call?.contact_name ? `Contact: ${call.contact_name}` : 'Unregistered Caller'}
                </p>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsFollowUpModalOpen(true)}
              className="bg-black text-[#ffe600] font-black text-xs uppercase px-3 py-1.5 brutal-border brutal-shadow-hover flex items-center"
            >
              <PlusCircle className="w-3.5 h-3.5 mr-1.5" /> Follow-up
            </button>
            <button
              onClick={onClose}
              className="w-8 h-8 bg-black text-white brutal-border flex items-center justify-center hover:bg-slate-800"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-[#fbfaf6]">
          {loading ? (
            <div className="py-24 flex flex-col items-center justify-center space-y-3">
              <div className="w-12 h-12 bg-[#ffe600] brutal-border-3 brutal-shadow flex items-center justify-center animate-spin">
                <Radio className="w-6 h-6 text-black" />
              </div>
              <p className="font-black text-xs uppercase tracking-wider text-black">
                Retrieving Call Log Telemetry & Transcript...
              </p>
            </div>
          ) : error ? (
            <div className="p-4 bg-[#ff5a5a] text-black font-black brutal-border-3 brutal-shadow-sm">
              {error}
            </div>
          ) : call ? (
            <>
              {/* Metadata Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="bg-white brutal-border-3 p-3">
                  <span className="text-[10px] text-slate-500 uppercase font-black tracking-wider flex items-center">
                    <Clock className="w-3 h-3 mr-1 text-black" /> Duration
                  </span>
                  <p className="text-sm font-black text-black mt-1 font-mono">
                    {formatDuration(call.duration_seconds)}
                  </p>
                </div>

                <div className="bg-white brutal-border-3 p-3">
                  <span className="text-[10px] text-slate-500 uppercase font-black tracking-wider flex items-center">
                    <Calendar className="w-3 h-3 mr-1 text-black" /> Started
                  </span>
                  <p className="text-xs font-black text-black mt-1 truncate">
                    {formatDate(call.started_at)}
                  </p>
                </div>

                <div className="bg-white brutal-border-3 p-3">
                  <span className="text-[10px] text-slate-500 uppercase font-black tracking-wider flex items-center">
                    <User className="w-3 h-3 mr-1 text-black" /> Turns
                  </span>
                  <p className="text-sm font-black text-black mt-1">
                    {call.turns.length} Dialogues
                  </p>
                </div>

                <div className="bg-white brutal-border-3 p-3">
                  <span className="text-[10px] text-slate-500 uppercase font-black tracking-wider flex items-center">
                    <Zap className="w-3 h-3 mr-1 text-black" /> Engine
                  </span>
                  <p className="text-xs font-black text-black mt-1 truncate">
                    {call.llm_model || 'llama-3.1-8b'}
                  </p>
                </div>
              </div>

              {/* Audio Playback */}
              <div className="bg-white brutal-border-3 p-4">
                <h3 className="text-xs font-black uppercase tracking-wider text-black mb-2 flex items-center">
                  <Radio className="w-4 h-4 mr-1.5" /> Call Recording
                </h3>
                <AudioPlayer
                  audioUrl={call.audio_url}
                  durationSeconds={call.duration_seconds}
                />
              </div>

              {/* AI Call Summary & Intelligence */}
              <div className="bg-[#fef9c3] brutal-border-3 brutal-shadow-sm p-4 space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center space-x-2 text-black">
                    <Sparkles className="w-4 h-4 fill-black" />
                    <h3 className="text-xs font-black uppercase tracking-wider">AI Executive Brief & Intelligence</h3>
                  </div>
                  <div className="flex items-center space-x-1.5 flex-wrap">
                    {call.urgency === 'high' && (
                      <span className="px-2 py-0.5 text-[10px] font-black uppercase bg-[#ff5a5a] text-black brutal-border">
                        High Urgency
                      </span>
                    )}
                    {call.sentiment && (
                      <span className={cn(
                        "px-2 py-0.5 text-[10px] font-black uppercase brutal-border",
                        call.sentiment === 'frustrated'
                          ? "bg-[#fed7aa] text-amber-950"
                          : call.sentiment === 'positive'
                          ? "bg-[#bbf7d0] text-emerald-950"
                          : "bg-white text-black"
                      )}>
                        {call.sentiment}
                      </span>
                    )}
                    {call.intent && (
                      <span className="px-2 py-0.5 text-[10px] font-black uppercase bg-white text-black brutal-border">
                        {call.intent.replace('_', ' ')}
                      </span>
                    )}
                  </div>
                </div>

                {call.summary ? (
                  <p className="text-sm font-bold text-slate-800 leading-relaxed">{call.summary}</p>
                ) : (
                  <p className="text-xs font-semibold text-slate-600 italic">No summary generated for this call.</p>
                )}

                {/* Structured Notes */}
                {call.structured_notes && (
                  <div className="pt-2 border-t border-black/10 text-xs space-y-1">
                    {call.structured_notes.key_details && (
                      <p className="text-slate-800">
                        <strong className="text-black uppercase text-[10px] tracking-wider">Key Details: </strong>
                        {call.structured_notes.key_details}
                      </p>
                    )}
                    {call.structured_notes.action_items && call.structured_notes.action_items !== 'None' && (
                      <p className="text-slate-800">
                        <strong className="text-black uppercase text-[10px] tracking-wider">Follow-up: </strong>
                        {call.structured_notes.action_items}
                      </p>
                    )}
                  </div>
                )}

                {/* Tags */}
                {call.tags && call.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {call.tags.map((tag: string, idx: number) => (
                      <span key={idx} className="text-[10px] font-bold text-slate-700 bg-black/5 px-2 py-0.5 rounded">
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Linked Records */}
              {(call.appointments.length > 0 ||
                call.messages.length > 0 ||
                call.transfers.length > 0 ||
                call.knowledge_misses.length > 0) && (
                <div className="space-y-3">
                  <h3 className="text-xs font-black uppercase tracking-wider text-black">
                    Outcomes & Actions Taken
                  </h3>

                  <div className="space-y-2">
                    {call.appointments.map((apt) => (
                      <div
                        key={apt.id}
                        className="flex items-center justify-between p-3 bg-[#bbf7d0] brutal-border text-black"
                      >
                        <div className="flex items-center space-x-2.5">
                          <CheckCircle2 className="w-5 h-5 text-black shrink-0" />
                          <div>
                            <p className="text-xs font-black uppercase">Appointment Booked: {apt.customer_name}</p>
                            <p className="text-[11px] font-bold text-slate-700">{formatDate(apt.start_at)}</p>
                          </div>
                        </div>
                        <span className="text-[10px] font-black px-2 py-0.5 bg-black text-[#86efac] brutal-border uppercase">
                          {apt.status}
                        </span>
                      </div>
                    ))}

                    {call.messages.map((msg) => (
                      <div
                        key={msg.id}
                        className="flex items-center justify-between p-3 bg-[#fef08a] brutal-border text-black"
                      >
                        <div className="flex items-center space-x-2.5">
                          <MessageSquare className="w-5 h-5 text-black shrink-0" />
                          <div>
                            <p className="text-xs font-black uppercase">Message Captured: {msg.caller_name}</p>
                            <p className="text-[11px] font-bold text-slate-700">{msg.reason}</p>
                          </div>
                        </div>
                        <span className="text-xs font-mono font-black text-black">{msg.callback_number}</span>
                      </div>
                    ))}

                    {call.transfers.map((tr) => (
                      <div
                        key={tr.id}
                        className="flex items-center justify-between p-3 bg-[#f3e8ff] brutal-border text-black"
                      >
                        <div className="flex items-center space-x-2.5">
                          <ArrowRightLeft className="w-5 h-5 text-black shrink-0" />
                          <div>
                            <p className="text-xs font-black uppercase">Call Transfer Initiated</p>
                            <p className="text-[11px] font-bold text-slate-700">{tr.reason}</p>
                          </div>
                        </div>
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 bg-black text-[#c084fc] brutal-border">
                          {tr.status}
                        </span>
                      </div>
                    ))}

                    {call.knowledge_misses.map((km) => (
                      <div
                        key={km.id}
                        className="flex items-center justify-between p-3 bg-[#ff5a5a]/20 brutal-border text-black"
                      >
                        <div className="flex items-center space-x-2.5">
                          <HelpCircle className="w-5 h-5 text-black shrink-0" />
                          <div>
                            <p className="text-xs font-black uppercase">Unanswered Inquiry Flagged</p>
                            <p className="text-[11px] font-bold text-slate-800">"{km.query}"</p>
                          </div>
                        </div>
                        <span className="text-[10px] font-black uppercase px-2 py-0.5 bg-black text-[#ff5a5a] brutal-border">
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
                  <h3 className="text-xs font-black uppercase tracking-wider text-black">
                    Dialogue Transcript ({call.turns.length} turns)
                  </h3>
                </div>

                <div className="space-y-4 pt-1">
                  {call.turns.length === 0 ? (
                    <div className="p-8 text-center bg-white brutal-border-3 text-xs font-black uppercase text-slate-400">
                      No turns recorded for this session.
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
                            <span className="text-[10px] font-black text-black uppercase tracking-wider">
                              {isAgent ? 'AI Receptionist' : 'Caller'}
                            </span>
                            {turn.latency_ms !== null && turn.latency_ms !== undefined && (
                              <span className="text-[10px] bg-black text-[#ffe600] px-1.5 py-0.5 brutal-border font-mono font-black">
                                ⚡ {Math.round(turn.latency_ms)}ms
                              </span>
                            )}
                          </div>
                          <div
                            className={cn(
                              'max-w-[85%] px-4 py-3 text-xs font-bold leading-relaxed brutal-border-3 brutal-shadow-sm',
                              isAgent
                                ? 'bg-[#fef08a] text-black'
                                : 'bg-[#dbeafe] text-black'
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
