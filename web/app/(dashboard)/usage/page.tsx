'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { UsageSummaryResponse, UsageRecordItem } from '@/types/api';
import {
  Gauge,
  Phone,
  MessageSquare,
  Cpu,
  DollarSign,
  TrendingUp,
  AlertCircle,
  Clock,
  Zap,
  Info,
  Loader2,
  Calendar,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function UsagePage() {
  const [summary, setSummary] = useState<UsageSummaryResponse | null>(null);
  const [records, setRecords] = useState<UsageRecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [sumRes, recRes] = await Promise.all([
        apiClient<UsageSummaryResponse>('/api/usage/summary'),
        apiClient<UsageRecordItem[]>('/api/usage/calls?limit=25'),
      ]);
      setSummary(sumRes);
      setRecords(recRes || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load usage & cost data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const formatSeconds = (secs: number) => {
    const mins = Math.floor(secs / 60);
    const rem = secs % 60;
    return `${mins}m ${rem}s`;
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="p-16 flex flex-col items-center justify-center text-slate-400 space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        <p className="text-sm">Loading usage metrics and cost estimation...</p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="p-4 bg-red-50 text-red-700 rounded-xl border border-red-200 text-sm">
          {error || 'Failed to load usage data'}
        </div>
      </div>
    );
  }

  const { limits, current_month, daily_usage } = summary;

  // Percentage calculations
  const voicePercent = Math.min(
    Math.round((current_month.voice_minutes / (limits.voice_minutes_per_month || 1)) * 100),
    100
  );
  const chatPercent = Math.min(
    Math.round((current_month.chat_messages / (limits.chat_messages_per_month || 1)) * 100),
    100
  );
  const tokenPercent = Math.min(
    Math.round((current_month.llm_tokens / (limits.llm_tokens_per_month || 1)) * 100),
    100
  );

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center">
            <Gauge className="w-6 h-6 mr-2.5 text-blue-600" /> Usage Limits & Cost Tracking
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Real-time monthly consumption vs limits, with transparent per-unit estimated cost tracking.
          </p>
        </div>
        <div className="inline-flex items-center px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 border border-slate-200 text-xs font-semibold">
          <Info className="w-3.5 h-3.5 mr-1.5 text-slate-400" />
          Pricing Table: Clearly Estimated
        </div>
      </div>

      {/* Usage Limit Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Voice Minutes Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center">
              <Phone className="w-3.5 h-3.5 mr-1.5 text-blue-600" /> Voice Minutes
            </span>
            <span className="text-xs font-bold text-slate-700">{voicePercent}%</span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-slate-900">
              {current_month.voice_minutes}
            </span>
            <span className="text-xs text-slate-400">/ {limits.voice_minutes_per_month} min</span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                voicePercent > 90
                  ? 'bg-red-500'
                  : voicePercent > 75
                  ? 'bg-amber-500'
                  : 'bg-blue-600'
              )}
              style={{ width: `${voicePercent}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">
            Resets on the 1st of each calendar month.
          </p>
        </div>

        {/* Chat Sessions Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center">
              <MessageSquare className="w-3.5 h-3.5 mr-1.5 text-emerald-600" /> Chat Messages
            </span>
            <span className="text-xs font-bold text-slate-700">{chatPercent}%</span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-slate-900">
              {current_month.chat_messages}
            </span>
            <span className="text-xs text-slate-400">/ {limits.chat_messages_per_month} msgs</span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                chatPercent > 90
                  ? 'bg-red-500'
                  : chatPercent > 75
                  ? 'bg-amber-500'
                  : 'bg-emerald-600'
              )}
              style={{ width: `${chatPercent}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">
            Sessions captured through the website chat widget.
          </p>
        </div>

        {/* LLM Tokens Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center">
              <Cpu className="w-3.5 h-3.5 mr-1.5 text-purple-600" /> LLM Tokens
            </span>
            <span className="text-xs font-bold text-slate-700">{tokenPercent}%</span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-slate-900">
              {(current_month.llm_tokens / 1000).toFixed(1)}k
            </span>
            <span className="text-xs text-slate-400">
              / {(limits.llm_tokens_per_month / 1000).toFixed(0)}k
            </span>
          </div>
          <div className="w-full h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all duration-500',
                tokenPercent > 90
                  ? 'bg-red-500'
                  : tokenPercent > 75
                  ? 'bg-amber-500'
                  : 'bg-purple-600'
              )}
              style={{ width: `${tokenPercent}%` }}
            />
          </div>
          <p className="text-[11px] text-slate-400">
            Combined prompt input & generation tokens.
          </p>
        </div>

        {/* Estimated Cost Card */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center">
              <DollarSign className="w-3.5 h-3.5 mr-1 text-emerald-600" /> Estimated Cost (MTD)
            </span>
            <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 uppercase">
              Estimate
            </span>
          </div>
          <div className="flex items-baseline space-x-1">
            <span className="text-2xl font-extrabold text-slate-900">
              ${current_month.total_cost_usd.toFixed(2)}
            </span>
            <span className="text-xs text-slate-400">USD</span>
          </div>
          <div className="text-[11px] text-slate-500 space-y-0.5 pt-1">
            <p>• Max Call Duration: {Math.floor(limits.max_call_duration_seconds / 60)} mins</p>
            <p>• Max Concurrent Calls: {limits.max_concurrent_calls}</p>
          </div>
        </div>
      </div>

      {/* Daily Usage Trend Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-800 flex items-center">
            <TrendingUp className="w-4 h-4 mr-2 text-blue-600" /> 14-Day Consumption & Daily Estimated Cost
          </h2>
          <span className="text-xs text-slate-400 font-medium">Daily Breakdown</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50/80 text-slate-500 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider">
              <tr>
                <th className="px-6 py-3.5">Date</th>
                <th className="px-6 py-3.5">Voice Minutes</th>
                <th className="px-6 py-3.5">Chat Sessions</th>
                <th className="px-6 py-3.5 text-right">Est. Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono text-xs">
              {daily_usage.map((d) => (
                <tr key={d.date} className="hover:bg-slate-50/50 transition">
                  <td className="px-6 py-3 font-sans font-medium text-slate-900">{d.date}</td>
                  <td className="px-6 py-3 text-slate-700">{d.voice_minutes.toFixed(1)} min</td>
                  <td className="px-6 py-3 text-slate-700">{d.chat_messages}</td>
                  <td className="px-6 py-3 text-right font-bold text-slate-900">
                    ${d.total_cost_usd.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-Call & Per-Chat Cost Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-800">Recent Session Cost History</h2>
          <span className="text-xs text-slate-400 font-medium">{records.length} Recorded Sessions</span>
        </div>

        {records.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-xs">
            No session records found. Make test calls or widget queries to inspect per-session cost tracking.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50/80 text-slate-500 border-b border-slate-200 text-xs font-semibold uppercase tracking-wider">
                <tr>
                  <th className="px-6 py-3.5">Session ID / Type</th>
                  <th className="px-6 py-3.5">Timestamp</th>
                  <th className="px-6 py-3.5">Duration</th>
                  <th className="px-6 py-3.5">Provider & Model</th>
                  <th className="px-6 py-3.5">Tokens (In / Out)</th>
                  <th className="px-6 py-3.5 text-right">Estimated Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-xs">
                {records.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-50/50 transition">
                    <td className="px-6 py-3.5 font-medium text-slate-900">
                      <div className="flex items-center space-x-2">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold uppercase border',
                            r.session_type === 'phone'
                              ? 'bg-blue-50 text-blue-700 border-blue-200'
                              : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          )}
                        >
                          {r.session_type}
                        </span>
                        <span className="font-mono text-slate-500 truncate max-w-[120px]">
                          {r.call_id ? String(r.call_id).slice(0, 8) + '...' : 'N/A'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-3.5 text-slate-600">{formatDate(r.created_at)}</td>
                    <td className="px-6 py-3.5 text-slate-700 font-mono">
                      {formatSeconds(r.duration_seconds)}
                    </td>
                    <td className="px-6 py-3.5 text-slate-700">
                      <span className="font-medium text-slate-900">{r.llm_provider || 'Groq'}</span>
                      {r.llm_model && <span className="text-slate-400 ml-1">({r.llm_model})</span>}
                    </td>
                    <td className="px-6 py-3.5 font-mono text-slate-600">
                      {r.llm_input_tokens} / {r.llm_output_tokens}
                    </td>
                    <td className="px-6 py-3.5 text-right font-mono font-bold text-slate-900">
                      ${r.estimated_cost_usd.toFixed(4)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
