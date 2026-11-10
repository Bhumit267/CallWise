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
  Sparkles,
  ShieldAlert,
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
      <div className="p-16 flex flex-col items-center justify-center space-y-4">
        <div className="w-16 h-16 bg-[#ffe600] brutal-border-3 brutal-shadow flex items-center justify-center animate-bounce">
          <Gauge className="w-8 h-8 text-black" />
        </div>
        <p className="font-black text-sm uppercase tracking-wider text-black">
          Calculating Real-time Consumption Metrics...
        </p>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="p-6 bg-[#ff5a5a] text-black brutal-border-3 brutal-shadow-lg flex items-center space-x-3">
          <AlertCircle className="w-6 h-6 shrink-0" />
          <div className="font-black">
            <div className="text-base uppercase tracking-wide">Usage Loading Failed</div>
            <div className="text-sm font-bold opacity-90">{error || 'Failed to load usage data'}</div>
          </div>
        </div>
      </div>
    );
  }

  const { limits, current_month, daily_usage } = summary;

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
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8">
      {/* Header Banner */}
      <div className="bg-white brutal-border-3 brutal-shadow-lg p-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 bg-[#ffe600] px-3 py-1 brutal-border text-xs font-black uppercase tracking-wider mb-2">
            <Zap className="w-3.5 h-3.5" />
            <span>Monthly Telemetry & Quotas</span>
          </div>
          <h1 className="text-3xl font-black text-black uppercase tracking-tight flex items-center">
            <Gauge className="w-8 h-8 mr-3 text-black" /> Usage & Cost Center
          </h1>
          <p className="text-sm font-bold text-slate-600 mt-1">
            Real-time monthly consumption tracking with verified per-token and per-minute cost transparency.
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="bg-black text-white px-4 py-2 brutal-border text-xs font-black uppercase tracking-wider flex items-center">
            <Info className="w-4 h-4 mr-2 text-[#ffe600]" />
            Monthly Reset: 1st
          </div>
        </div>
      </div>

      {/* 4 Metric Quota Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Voice Minutes Card */}
        <div className="bg-[#fef9c3] brutal-border-3 brutal-shadow p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-2 border-b-2 border-black">
              <span className="font-black text-xs uppercase tracking-wider flex items-center text-black">
                <Phone className="w-4 h-4 mr-1.5" /> Voice Minutes
              </span>
              <span className="bg-black text-[#ffe600] px-2 py-0.5 text-xs font-black brutal-border">
                {voicePercent}%
              </span>
            </div>
            <div className="mt-4 flex items-baseline space-x-2">
              <span className="text-3xl font-black text-black">
                {current_month.voice_minutes}
              </span>
              <span className="text-xs font-black text-slate-700 uppercase">
                / {limits.voice_minutes_per_month} min
              </span>
            </div>
          </div>
          <div>
            <div className="w-full h-4 bg-white brutal-border overflow-hidden">
              <div
                className="h-full bg-black transition-all duration-300"
                style={{ width: `${voicePercent}%` }}
              />
            </div>
            <p className="text-[11px] font-bold text-slate-600 mt-2">
              LiveKit audio streaming + Groq STT/TTS
            </p>
          </div>
        </div>

        {/* Chat Messages Card */}
        <div className="bg-[#dbeafe] brutal-border-3 brutal-shadow p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-2 border-b-2 border-black">
              <span className="font-black text-xs uppercase tracking-wider flex items-center text-black">
                <MessageSquare className="w-4 h-4 mr-1.5" /> Chat Messages
              </span>
              <span className="bg-black text-white px-2 py-0.5 text-xs font-black brutal-border">
                {chatPercent}%
              </span>
            </div>
            <div className="mt-4 flex items-baseline space-x-2">
              <span className="text-3xl font-black text-black">
                {current_month.chat_messages}
              </span>
              <span className="text-xs font-black text-slate-700 uppercase">
                / {limits.chat_messages_per_month} msgs
              </span>
            </div>
          </div>
          <div>
            <div className="w-full h-4 bg-white brutal-border overflow-hidden">
              <div
                className="h-full bg-[#2563eb] transition-all duration-300"
                style={{ width: `${chatPercent}%` }}
              />
            </div>
            <p className="text-[11px] font-bold text-slate-600 mt-2">
              Embedded widget inquiries & web sessions
            </p>
          </div>
        </div>

        {/* LLM Tokens Card */}
        <div className="bg-[#f3e8ff] brutal-border-3 brutal-shadow p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-2 border-b-2 border-black">
              <span className="font-black text-xs uppercase tracking-wider flex items-center text-black">
                <Cpu className="w-4 h-4 mr-1.5" /> LLM Tokens
              </span>
              <span className="bg-black text-[#c084fc] px-2 py-0.5 text-xs font-black brutal-border">
                {tokenPercent}%
              </span>
            </div>
            <div className="mt-4 flex items-baseline space-x-2">
              <span className="text-3xl font-black text-black">
                {(current_month.llm_tokens / 1000).toFixed(1)}k
              </span>
              <span className="text-xs font-black text-slate-700 uppercase">
                / {(limits.llm_tokens_per_month / 1000).toFixed(0)}k
              </span>
            </div>
          </div>
          <div>
            <div className="w-full h-4 bg-white brutal-border overflow-hidden">
              <div
                className="h-full bg-[#9333ea] transition-all duration-300"
                style={{ width: `${tokenPercent}%` }}
              />
            </div>
            <p className="text-[11px] font-bold text-slate-600 mt-2">
              Llama 3.1 8B instant prompt + output
            </p>
          </div>
        </div>

        {/* MTD Estimated Cost Card */}
        <div className="bg-[#bbf7d0] brutal-border-3 brutal-shadow p-5 flex flex-col justify-between space-y-4">
          <div>
            <div className="flex items-center justify-between pb-2 border-b-2 border-black">
              <span className="font-black text-xs uppercase tracking-wider flex items-center text-black">
                <DollarSign className="w-4 h-4 mr-1" /> Estimated Cost (MTD)
              </span>
              <span className="bg-black text-[#86efac] px-2 py-0.5 text-xs font-black brutal-border">
                USD
              </span>
            </div>
            <div className="mt-4 flex items-baseline space-x-2">
              <span className="text-3xl font-black text-black">
                ${current_month.total_cost_usd.toFixed(2)}
              </span>
              <span className="text-xs font-black text-slate-700 uppercase">
                Estimated
              </span>
            </div>
          </div>
          <div className="space-y-1 bg-white brutal-border p-2 text-[10px] font-black uppercase text-black">
            <div>• Max Call: {Math.floor(limits.max_call_duration_seconds / 60)} Mins</div>
            <div>• Max Concurrency: {limits.max_concurrent_calls} Lines</div>
          </div>
        </div>
      </div>

      {/* 14-Day Consumption Breakdown Table */}
      <div className="bg-white brutal-border-3 brutal-shadow-lg overflow-hidden">
        <div className="px-6 py-4 bg-[#ffe600] border-b-3 border-black flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <TrendingUp className="w-5 h-5 text-black" />
            <h2 className="text-base font-black text-black uppercase tracking-wider">
              14-Day Consumption & Daily Cost Telemetry
            </h2>
          </div>
          <span className="bg-black text-white px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
            Daily Log
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead className="bg-black text-white text-xs font-black uppercase tracking-wider border-b-2 border-black">
              <tr>
                <th className="px-6 py-3.5">Date</th>
                <th className="px-6 py-3.5">Voice Minutes</th>
                <th className="px-6 py-3.5">Chat Sessions</th>
                <th className="px-6 py-3.5 text-right">Est. Cost (USD)</th>
              </tr>
            </thead>
            <tbody className="divide-y-2 divide-black/10 text-sm font-bold">
              {daily_usage.map((d) => (
                <tr key={d.date} className="hover:bg-[#ffe600]/15 transition">
                  <td className="px-6 py-3.5 font-black text-black">{d.date}</td>
                  <td className="px-6 py-3.5 text-slate-800">{d.voice_minutes.toFixed(1)} min</td>
                  <td className="px-6 py-3.5 text-slate-800">{d.chat_messages}</td>
                  <td className="px-6 py-3.5 text-right font-black text-black">
                    ${d.total_cost_usd.toFixed(4)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Per-Session Cost Tracking Table */}
      <div className="bg-white brutal-border-3 brutal-shadow-lg overflow-hidden">
        <div className="px-6 py-4 bg-black text-white flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Clock className="w-5 h-5 text-[#ffe600]" />
            <h2 className="text-base font-black uppercase tracking-wider">
              Recent Session Cost History
            </h2>
          </div>
          <span className="bg-[#ffe600] text-black px-2.5 py-0.5 brutal-border text-xs font-black uppercase">
            {records.length} Recorded Sessions
          </span>
        </div>

        {records.length === 0 ? (
          <div className="py-16 text-center space-y-3">
            <ShieldAlert className="w-10 h-10 mx-auto text-slate-400" />
            <p className="font-black text-sm uppercase tracking-wider text-slate-500">
              No recent session records logged yet.
            </p>
            <p className="text-xs font-bold text-slate-400">
              Run test calls from Test Agent or place live calls to inspect per-session cost tracking.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-[#f1f5f9] text-black text-xs font-black uppercase tracking-wider border-b-2 border-black">
                <tr>
                  <th className="px-6 py-3.5">Session / Channel</th>
                  <th className="px-6 py-3.5">Timestamp</th>
                  <th className="px-6 py-3.5">Duration</th>
                  <th className="px-6 py-3.5">Engine & Model</th>
                  <th className="px-6 py-3.5">Tokens (Prompt/Resp)</th>
                  <th className="px-6 py-3.5 text-right">Est. Cost</th>
                </tr>
              </thead>
              <tbody className="divide-y-2 divide-black/10 text-xs font-bold">
                {records.map((r) => (
                  <tr key={r.id} className="hover:bg-[#ffe600]/15 transition">
                    <td className="px-6 py-3.5">
                      <div className="flex items-center space-x-2">
                        <span
                          className={cn(
                            'inline-flex items-center px-2 py-0.5 brutal-border text-[10px] font-black uppercase',
                            r.session_type === 'phone'
                              ? 'bg-[#dbeafe] text-black'
                              : 'bg-[#bbf7d0] text-black'
                          )}
                        >
                          {r.session_type}
                        </span>
                        <span className="font-mono font-black text-slate-700 truncate max-w-[120px]">
                          {r.call_id ? String(r.call_id).slice(0, 8) + '...' : 'N/A'}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-3.5 text-slate-700 font-bold">{formatDate(r.created_at)}</td>
                    <td className="px-6 py-3.5 font-mono font-black text-black">
                      {formatSeconds(r.duration_seconds)}
                    </td>
                    <td className="px-6 py-3.5 text-slate-800">
                      <span className="font-black text-black">{r.llm_provider || 'Groq'}</span>
                      {r.llm_model && <span className="text-slate-500 ml-1">({r.llm_model})</span>}
                    </td>
                    <td className="px-6 py-3.5 font-mono font-bold text-slate-700">
                      {r.llm_input_tokens} / {r.llm_output_tokens}
                    </td>
                    <td className="px-6 py-3.5 text-right font-mono font-black text-black">
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
