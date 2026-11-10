'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart3,
  TrendingUp,
  PhoneCall,
  PhoneForwarded,
  Clock,
  Calendar,
  AlertCircle,
  RefreshCw,
  HelpCircle,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { AnalyticsOverviewResponse } from '@/types/api';

export default function AnalyticsPage() {
  const [period, setPeriod] = useState<'today' | '7d' | '30d'>('7d');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AnalyticsOverviewResponse | null>(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient<AnalyticsOverviewResponse>(`/api/analytics?period=${period}`);
      setData(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load analytics data.');
    } finally {
      setLoading(false);
    }
  }, [period]);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  const maxDailyCalls = Math.max(...(data?.calls_per_day?.map((d) => d.total) || [1]), 1);
  const maxHourlyCalls = Math.max(...(data?.busiest_hours?.map((h) => h.call_count) || [1]), 1);

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Performance & Analytics
            </h2>
            <span className="bg-[#a3e635] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              Metrics
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Real-time insights into call volume, booking conversions, agent latency, and knowledge gaps.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          {/* Period selector */}
          <div className="inline-flex rounded-xl brutal-border bg-white p-1 brutal-shadow-xs">
            <button
              onClick={() => setPeriod('today')}
              className={`px-3 py-1.5 text-xs font-black uppercase tracking-wider rounded-lg transition-all ${
                period === 'today' ? 'bg-[#ffe600] text-black brutal-border' : 'text-neutral-700 hover:text-black'
              }`}
            >
              Today
            </button>
            <button
              onClick={() => setPeriod('7d')}
              className={`px-3 py-1.5 text-xs font-black uppercase tracking-wider rounded-lg transition-all ${
                period === '7d' ? 'bg-[#ffe600] text-black brutal-border' : 'text-neutral-700 hover:text-black'
              }`}
            >
              7 Days
            </button>
            <button
              onClick={() => setPeriod('30d')}
              className={`px-3 py-1.5 text-xs font-black uppercase tracking-wider rounded-lg transition-all ${
                period === '30d' ? 'bg-[#ffe600] text-black brutal-border' : 'text-neutral-700 hover:text-black'
              }`}
            >
              30 Days
            </button>
          </div>

          <button
            onClick={() => fetchAnalytics()}
            disabled={loading}
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
            title="Refresh analytics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-100 border-2 border-black rounded-xl text-rose-950 text-xs font-black uppercase flex items-center justify-between brutal-shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchAnalytics()}
            className="text-xs font-black underline hover:text-black"
          >
            Retry
          </button>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Calls */}
        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Total Calls</span>
            <div className="w-9 h-9 rounded-xl bg-[#dbeafe] text-blue-950 brutal-border brutal-shadow-xs flex items-center justify-center">
              <PhoneCall className="w-4 h-4 stroke-[2.5]" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black text-black">
              {loading ? '-' : data?.total_calls ?? 0}
            </div>
            <p className="text-xs font-bold text-neutral-600 mt-1">
              Answered: <span className="font-mono text-black">{data?.answered_count ?? 0}</span>
            </p>
          </div>
        </div>

        {/* Booking Conversion Rate */}
        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Booking Rate</span>
            <div className="w-9 h-9 rounded-xl bg-[#dcfce7] text-emerald-950 brutal-border brutal-shadow-xs flex items-center justify-center">
              <TrendingUp className="w-4 h-4 stroke-[2.5]" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black text-emerald-700">
              {loading ? '-' : `${((data?.booking_conversion_rate ?? 0) * 100).toFixed(1)}%`}
            </div>
            <p className="text-xs font-semibold text-neutral-600 mt-1">Calls resulting in confirmed bookings</p>
          </div>
        </div>

        {/* Latency (Median & P95) */}
        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Turn Latency</span>
            <div className="w-9 h-9 rounded-xl bg-[#f3e8ff] text-purple-950 brutal-border brutal-shadow-xs flex items-center justify-center">
              <Clock className="w-4 h-4 stroke-[2.5]" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-3xl font-black text-black font-mono">
              {loading ? '-' : `${data?.latency_metrics?.median_ms ?? 0} ms`}
            </div>
            <p className="text-xs font-bold text-neutral-600 mt-1">
              P95: <span className="font-mono text-black">{data?.latency_metrics?.p95_ms ?? 0} ms</span>
            </p>
          </div>
        </div>

        {/* Action Outcomes (Transfers & Messages) */}
        <div className="bg-white rounded-2xl brutal-border-3 p-5 brutal-shadow">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase text-neutral-500 tracking-wider">Dispositions</span>
            <div className="w-9 h-9 rounded-xl bg-[#fef9c3] text-amber-950 brutal-border brutal-shadow-xs flex items-center justify-center">
              <PhoneForwarded className="w-4 h-4 stroke-[2.5]" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-4">
            <div>
              <span className="text-3xl font-black text-black">{loading ? '-' : data?.transferred_count ?? 0}</span>
              <p className="text-[10px] font-black uppercase text-neutral-500">Transfers</p>
            </div>
            <div className="border-l-2 border-black pl-4">
              <span className="text-3xl font-black text-black">{loading ? '-' : data?.message_taken_count ?? 0}</span>
              <p className="text-[10px] font-black uppercase text-neutral-500">Messages</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily Volume Bar Chart */}
        <div className="lg:col-span-2 bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg">
          <div className="flex items-center justify-between mb-4 border-b-2 border-black pb-3">
            <div>
              <h3 className="text-sm font-black uppercase text-black flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-blue-600 stroke-[2.5]" />
                Call Volume & Status Distribution
              </h3>
              <p className="text-xs font-semibold text-neutral-500">Daily calls categorized by answered and transferred</p>
            </div>
            <div className="flex items-center gap-3 text-xs font-bold">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-blue-600 brutal-border"></span> Answered
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-sm bg-[#ffe600] brutal-border"></span> Transferred
              </span>
            </div>
          </div>

          {loading ? (
            <div className="h-56 flex items-center justify-center text-xs font-bold text-neutral-400 animate-pulse">
              Loading call trends...
            </div>
          ) : !data?.calls_per_day || data.calls_per_day.length === 0 ? (
            <div className="h-56 flex flex-col items-center justify-center text-xs font-bold text-neutral-400">
              <Calendar className="w-8 h-8 text-neutral-300 mb-2" />
              <span>No call data recorded for this period</span>
            </div>
          ) : (
            <div className="h-56 flex items-end gap-2 pt-6 pb-2 border-b-2 border-black/10">
              {data.calls_per_day.map((d) => {
                const heightPct = Math.round((d.total / maxDailyCalls) * 100);
                const answeredPct = d.total > 0 ? (d.answered / d.total) * 100 : 0;
                const transferredPct = d.total > 0 ? (d.transferred / d.total) * 100 : 0;

                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center h-full justify-end group relative">
                    {/* Tooltip */}
                    <div className="absolute -top-12 bg-black text-white text-[10px] font-mono py-1 px-2 rounded-lg brutal-border pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-10 whitespace-nowrap shadow-brutal-xs">
                      <div>{d.date}</div>
                      <div>Total: {d.total} | Ans: {d.answered} | Xfer: {d.transferred}</div>
                    </div>

                    {/* Bar Stack */}
                    <div
                      className="w-full max-w-[36px] bg-neutral-100 rounded-t-md brutal-border flex flex-col justify-end overflow-hidden transition-all duration-300 hover:opacity-90"
                      style={{ height: `${Math.max(heightPct, 8)}%` }}
                    >
                      {/* Transferred segment */}
                      <div
                        className="w-full bg-[#ffe600]"
                        style={{ height: `${transferredPct}%` }}
                      />
                      {/* Answered segment */}
                      <div
                        className="w-full bg-blue-600"
                        style={{ height: `${answeredPct}%` }}
                      />
                    </div>
                    {/* Date label */}
                    <span className="text-[10px] font-mono font-bold text-neutral-600 mt-2 truncate w-full text-center">
                      {d.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 24-Hour Call Distribution (Busiest Hours) */}
        <div className="bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1 border-b-2 border-black pb-3">
              <h3 className="text-sm font-black uppercase text-black flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-600 stroke-[2.5]" />
                Hourly Traffic Heat
              </h3>
            </div>
            <p className="text-xs font-semibold text-neutral-500 my-3">Call distribution across 24 hours ({data?.timezone || 'Local'})</p>

            {loading ? (
              <div className="h-44 flex items-center justify-center text-xs font-bold text-neutral-400 animate-pulse">
                Loading hourly distribution...
              </div>
            ) : !data?.busiest_hours || data.busiest_hours.length === 0 ? (
              <div className="h-44 flex items-center justify-center text-xs font-bold text-neutral-400">
                No hourly patterns detected
              </div>
            ) : (
              <div className="h-44 flex items-end gap-1 pt-4 pb-2">
                {data.busiest_hours.map((h) => {
                  const barHeight = Math.round((h.call_count / maxHourlyCalls) * 100);
                  const isPeak = h.call_count === maxHourlyCalls && h.call_count > 0;
                  return (
                    <div
                      key={h.hour}
                      className="flex-1 flex flex-col items-center h-full justify-end group relative"
                    >
                      <div className="absolute -top-8 bg-black text-white text-[10px] font-mono py-0.5 px-1.5 rounded brutal-border pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-10 whitespace-nowrap">
                        {h.hour}:00 - {h.call_count} calls
                      </div>
                      <div
                        className={`w-full rounded-t-sm brutal-border transition-all ${
                          isPeak ? 'bg-purple-600' : 'bg-purple-200 hover:bg-purple-300'
                        }`}
                        style={{ height: `${Math.max(barHeight, 6)}%` }}
                      />
                      {h.hour % 4 === 0 && (
                        <span className="text-[9px] font-mono font-bold text-neutral-500 mt-1">{h.hour}h</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div className="text-[11px] font-mono font-bold text-neutral-500 border-t-2 border-black pt-3 flex items-center justify-between">
            <span>Peak hourly traffic</span>
            <span className="font-black text-black">Peak: {maxHourlyCalls} calls/hr</span>
          </div>
        </div>
      </div>

      {/* Breakdown Rows: Top Services & Top Missed Questions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Services */}
        <div className="bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg">
          <div className="flex items-center justify-between mb-4 border-b-2 border-black pb-3">
            <div>
              <h3 className="text-sm font-black uppercase text-black">Top Inquired Services</h3>
              <p className="text-xs font-semibold text-neutral-500">Services most booked or requested via voice agent</p>
            </div>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-neutral-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : !data?.top_services || data.top_services.length === 0 ? (
            <p className="text-xs font-bold text-neutral-400 py-6 text-center">No service booking activity recorded.</p>
          ) : (
            <div className="space-y-3">
              {data.top_services.map((svc) => (
                <div
                  key={svc.service_id}
                  className="flex items-center justify-between p-3.5 rounded-xl brutal-border bg-neutral-50 hover:bg-amber-50/50 transition-colors"
                >
                  <div className="min-w-0 pr-3">
                    <div className="font-black text-sm text-black truncate">{svc.name}</div>
                    <div className="text-xs font-semibold text-neutral-600">{svc.booking_count} bookings recorded</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-black text-black font-mono">
                      ${svc.revenue.toLocaleString()}
                    </div>
                    <div className="text-[10px] font-black uppercase text-emerald-800">Estimated value</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top Missed Questions / Knowledge Gaps */}
        <div className="bg-white rounded-2xl brutal-border-3 p-6 brutal-shadow-lg">
          <div className="flex items-center justify-between mb-4 border-b-2 border-black pb-3">
            <div>
              <h3 className="text-sm font-black uppercase text-black flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-amber-500 stroke-[2.5]" />
                Frequent Knowledge Gaps
              </h3>
              <p className="text-xs font-semibold text-neutral-500">Unanswered caller queries requiring additions</p>
            </div>
            <a
              href="/missed-questions"
              className="text-xs font-black uppercase text-blue-600 hover:text-black transition-colors underline"
            >
              View Queue &rarr;
            </a>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-neutral-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : !data?.top_missed_questions || data.top_missed_questions.length === 0 ? (
            <p className="text-xs font-bold text-neutral-400 py-6 text-center">No knowledge gaps detected! Voice agent answered all queries.</p>
          ) : (
            <div className="space-y-3">
              {data.top_missed_questions.map((miss, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3.5 rounded-xl brutal-border bg-[#fef9c3]"
                >
                  <div className="min-w-0 pr-3">
                    <div className="text-xs font-black text-black truncate">&quot;{miss.query}&quot;</div>
                    <div className="text-[11px] font-mono text-neutral-600">Status: {miss.status}</div>
                  </div>
                  <span className="shrink-0 px-2.5 py-1 text-[11px] font-black uppercase rounded-lg bg-black text-white brutal-border">
                    {miss.count} {miss.count === 1 ? 'time' : 'times'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
