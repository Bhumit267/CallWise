'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { MessageDetail } from '@/types/api';
import { CreateFollowUpModal } from './create-follow-up-modal';
import {
  X,
  MessageSquare,
  Phone,
  User,
  Calendar,
  Sparkles,
  PlusCircle,
  Loader2,
} from 'lucide-react';

interface MessageDetailModalProps {
  messageId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onFollowUpCreated?: () => void;
}

export function MessageDetailModal({
  messageId,
  isOpen,
  onClose,
  onFollowUpCreated,
}: MessageDetailModalProps) {
  const [message, setMessage] = useState<MessageDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isFollowUpModalOpen, setIsFollowUpModalOpen] = useState(false);

  useEffect(() => {
    if (!isOpen || !messageId) {
      setMessage(null);
      return;
    }

    const fetchDetail = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await apiClient<MessageDetail>(`/api/messages/${messageId}`);
        setMessage(data);
      } catch (err: any) {
        setError(err.message || 'Failed to load message details');
      } finally {
        setLoading(false);
      }
    };

    fetchDetail();
  }, [isOpen, messageId]);

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
      <div className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center p-4">
        <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col">
          {/* Header */}
          <div className="h-16 px-6 border-b border-slate-200 flex items-center justify-between bg-slate-50">
            <div className="flex items-center space-x-3 truncate">
              <div className="w-9 h-9 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center flex-shrink-0">
                <MessageSquare className="w-5 h-5" />
              </div>
              <div className="truncate">
                <h2 className="text-base font-bold text-slate-900 truncate">
                  Callback Message
                </h2>
                <p className="text-xs text-slate-500">
                  {message?.caller_name || (loading ? 'Loading...' : 'Recorded Message')}
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

          {/* Body */}
          <div className="p-6 space-y-5">
            {loading ? (
              <div className="py-12 flex flex-col items-center justify-center text-slate-400 space-y-3">
                <Loader2 className="w-8 h-8 animate-spin text-amber-600" />
                <p className="text-sm">Loading message details...</p>
              </div>
            ) : error ? (
              <div className="p-4 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
                {error}
              </div>
            ) : message ? (
              <>
                {/* Caller & Contact Info Card */}
                <div className="grid grid-cols-2 gap-3 bg-slate-50 border border-slate-200 rounded-xl p-4">
                  <div>
                    <span className="text-[11px] text-slate-400 uppercase font-semibold flex items-center">
                      <User className="w-3 h-3 mr-1" /> Caller Name
                    </span>
                    <p className="text-sm font-bold text-slate-800 mt-0.5">
                      {message.caller_name}
                    </p>
                  </div>

                  <div>
                    <span className="text-[11px] text-slate-400 uppercase font-semibold flex items-center">
                      <Phone className="w-3 h-3 mr-1" /> Callback Number
                    </span>
                    <a
                      href={`tel:${message.callback_number}`}
                      className="text-sm font-semibold text-blue-600 hover:underline mt-0.5 block"
                    >
                      {message.callback_number}
                    </a>
                  </div>

                  <div className="col-span-2 pt-2 border-t border-slate-200/60 flex items-center text-xs text-slate-500">
                    <Calendar className="w-3.5 h-3.5 mr-1 text-slate-400" />
                    Received on {formatDate(message.created_at)}
                  </div>
                </div>

                {/* Message Reason / Transcript */}
                <div>
                  <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">
                    Message Content & Reason
                  </h3>
                  <div className="bg-amber-50/60 border border-amber-200 rounded-xl p-4 text-slate-800 text-sm leading-relaxed">
                    {message.reason}
                  </div>
                </div>

                {/* Call Summary if available */}
                {message.call_summary && (
                  <div>
                    <div className="flex items-center space-x-1.5 text-blue-600 mb-1.5">
                      <Sparkles className="w-3.5 h-3.5" />
                      <h3 className="text-xs font-bold uppercase tracking-wider">
                        Call Context
                      </h3>
                    </div>
                    <div className="bg-slate-50 border border-slate-200 rounded-xl p-3.5 text-xs text-slate-700 leading-relaxed">
                      {message.call_summary}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="pt-2 flex items-center justify-between border-t border-slate-100">
                  <a
                    href={`tel:${message.callback_number}`}
                    className="inline-flex items-center px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg transition"
                  >
                    <Phone className="w-3.5 h-3.5 mr-1.5" /> Call Back
                  </a>

                  <button
                    onClick={() => setIsFollowUpModalOpen(true)}
                    className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow transition"
                  >
                    <PlusCircle className="w-3.5 h-3.5 mr-1.5" /> Create Follow-up
                  </button>
                </div>
              </>
            ) : null}
          </div>
        </div>
      </div>

      {message && (
        <CreateFollowUpModal
          isOpen={isFollowUpModalOpen}
          onClose={() => setIsFollowUpModalOpen(false)}
          onSuccess={() => {
            if (onFollowUpCreated) onFollowUpCreated();
          }}
          defaultTitle={`Call back ${message.caller_name} (${message.callback_number})`}
          defaultDescription={`Message: ${message.reason}`}
          contactId={message.contact_id}
          contactName={message.contact_name}
        />
      )}
    </>
  );
}
