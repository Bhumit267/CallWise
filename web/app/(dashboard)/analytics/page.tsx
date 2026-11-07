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

  // Max calculations for clean SVG / bar rendering
  const maxDailyCalls = Math.max(...(data?.calls_per_day?.map((d) => d.total) || [1]), 1);
  const maxHourlyCalls = Math.max(...(data?.busiest_hours?.map((h) => h.call_count) || [1]), 1);

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Performance & Call Analytics</h2>
          <p className="text-sm text-slate-500">
            Real-time insights into call volume, booking conversions, agent latency, and knowledge gaps.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Period selector */}
          <div className="inline-flex rounded-lg border border-slate-200 bg-white p-1 shadow-xs">
            <button
              onClick={() => setPeriod('today')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                period === 'today' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Today
            </button>
            <button
              onClick={() => setPeriod('7d')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                period === '7d' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Last 7 Days
            </button>
            <button
              onClick={() => setPeriod('30d')}
              className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                period === '30d' ? 'bg-blue-600 text-white' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              Last 30 Days
            </button>
          </div>

          <button
            onClick={() => fetchAnalytics()}
            disabled={loading}
            className="p-2 border border-slate-200 bg-white rounded-lg hover:bg-slate-50 text-slate-600 transition-colors"
            title="Refresh analytics"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchAnalytics()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Calls */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Total Calls</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <PhoneCall className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900">
              {loading ? '-' : data?.total_calls ?? 0}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Answered: <span className="font-semibold text-slate-700">{data?.answered_count ?? 0}</span>
            </p>
          </div>
        </div>

        {/* Booking Conversion Rate */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Booking Conversion</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <TrendingUp className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-emerald-600">
              {loading ? '-' : `${((data?.booking_conversion_rate ?? 0) * 100).toFixed(1)}%`}
            </div>
            <p className="text-xs text-slate-500 mt-1">Calls resulting in confirmed appointments</p>
          </div>
        </div>

        {/* Latency (Median & P95) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Turn Latency</span>
            <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <div className="text-2xl font-bold text-slate-900">
              {loading ? '-' : `${data?.latency_metrics?.median_ms ?? 0} ms`}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              P95: <span className="font-semibold text-slate-700">{data?.latency_metrics?.p95_ms ?? 0} ms</span> (
              {data?.latency_metrics?.sample_count ?? 0} samples)
            </p>
          </div>
        </div>

        {/* Action Outcomes (Transfers & Messages) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500 uppercase tracking-wider">Call Dispositions</span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <PhoneForwarded className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-4">
            <div>
              <span className="text-2xl font-bold text-slate-900">{loading ? '-' : data?.transferred_count ?? 0}</span>
              <p className="text-xs text-slate-500">Transferred</p>
            </div>
            <div className="border-l border-slate-200 pl-4">
              <span className="text-2xl font-bold text-slate-900">{loading ? '-' : data?.message_taken_count ?? 0}</span>
              <p className="text-xs text-slate-500">Messages</p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Daily Volume Bar Chart */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-blue-600" />
                Call Volume & Status Distribution
              </h3>
              <p className="text-xs text-slate-500">Daily calls categorized by answered, transferred, or message taken</p>
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-600">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span> Answered
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Transferred
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-slate-300"></span> Other
              </span>
            </div>
          </div>

          {loading ? (
            <div className="h-56 flex items-center justify-center text-sm text-slate-400 animate-pulse">
              Loading call trends...
            </div>
          ) : !data?.calls_per_day || data.calls_per_day.length === 0 ? (
            <div className="h-56 flex flex-col items-center justify-center text-sm text-slate-400">
              <Calendar className="w-8 h-8 text-slate-300 mb-2" />
              <span>No call data recorded for this period</span>
            </div>
          ) : (
            <div className="h-56 flex items-end gap-2 pt-6 pb-2 border-b border-slate-100">
              {data.calls_per_day.map((d) => {
                const heightPct = Math.round((d.total / maxDailyCalls) * 100);
                const answeredPct = d.total > 0 ? (d.answered / d.total) * 100 : 0;
                const transferredPct = d.total > 0 ? (d.transferred / d.total) * 100 : 0;

                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center h-full justify-end group relative">
                    {/* Tooltip */}
                    <div className="absolute -top-12 bg-slate-900 text-white text-[11px] py-1 px-2 rounded pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-10 whitespace-nowrap shadow-md">
                      <div className="font-semibold">{d.date}</div>
                      <div>Total: {d.total} | Ans: {d.answered} | Xfer: {d.transferred}</div>
                    </div>

                    {/* Bar Stack */}
                    <div
                      className="w-full max-w-[36px] bg-slate-200 rounded-t-sm flex flex-col justify-end overflow-hidden transition-all duration-300 hover:opacity-90"
                      style={{ height: `${Math.max(heightPct, 6)}%` }}
                    >
                      {/* Transferred segment */}
                      <div
                        className="w-full bg-amber-400"
                        style={{ height: `${transferredPct}%` }}
                      />
                      {/* Answered segment */}
                      <div
                        className="w-full bg-blue-600"
                        style={{ height: `${answeredPct}%` }}
                      />
                    </div>
                    {/* Date label */}
                    <span className="text-[10px] text-slate-400 mt-2 truncate w-full text-center">
                      {d.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* 24-Hour Call Distribution (Busiest Hours) */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <Clock className="w-4 h-4 text-purple-600" />
                Hourly Traffic Heat
              </h3>
            </div>
            <p className="text-xs text-slate-500 mb-4">Call distribution across 24 hours ({data?.timezone || 'Local'})</p>

            {loading ? (
              <div className="h-44 flex items-center justify-center text-sm text-slate-400 animate-pulse">
                Loading hourly distribution...
              </div>
            ) : !data?.busiest_hours || data.busiest_hours.length === 0 ? (
              <div className="h-44 flex items-center justify-center text-sm text-slate-400">
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
                      <div className="absolute -top-8 bg-slate-900 text-white text-[10px] py-0.5 px-1.5 rounded pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity z-10 whitespace-nowrap">
                        {h.hour}:00 - {h.call_count} calls
                      </div>
                      <div
                        className={`w-full rounded-t-xs transition-all ${
                          isPeak ? 'bg-purple-600' : 'bg-purple-200 hover:bg-purple-300'
                        }`}
                        style={{ height: `${Math.max(barHeight, 4)}%` }}
                      />
                      {h.hour % 4 === 0 && (
                        <span className="text-[9px] text-slate-400 mt-1">{h.hour}h</span>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          <div className="text-[11px] text-slate-400 border-t border-slate-100 pt-3 flex items-center justify-between">
            <span>Peak times guide agent shift scheduling</span>
            <span className="font-semibold text-slate-600">Peak: {maxHourlyCalls} calls/hr</span>
          </div>
        </div>
      </div>

      {/* Breakdown Rows: Top Services & Top Missed Questions */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Services */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900">Top Inquired Services</h3>
              <p className="text-xs text-slate-500">Services most booked or requested via voice agent</p>
            </div>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-slate-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : !data?.top_services || data.top_services.length === 0 ? (
            <p className="text-sm text-slate-400 py-6 text-center">No service booking activity recorded.</p>
          ) : (
            <div className="space-y-3">
              {data.top_services.map((svc) => (
                <div
                  key={svc.service_id}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-100 hover:border-slate-200 hover:bg-slate-50/50 transition-colors"
                >
                  <div className="min-w-0 pr-3">
                    <div className="font-medium text-sm text-slate-900 truncate">{svc.name}</div>
                    <div className="text-xs text-slate-500">{svc.booking_count} bookings recorded</div>
                  </div>
                  <div className="text-right shrink-0">
                    <div className="text-sm font-semibold text-slate-900">
                      ${svc.revenue.toLocaleString()}
                    </div>
                    <div className="text-[11px] text-emerald-600 font-medium">Estimated value</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top Missed Questions / Knowledge Gaps */}
        <div className="bg-white rounded-xl border border-slate-200 p-5 shadow-xs">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-amber-500" />
                Frequent Knowledge Gaps
              </h3>
              <p className="text-xs text-slate-500">Unanswered caller queries requiring knowledge base additions</p>
            </div>
            <a
              href="/missed-questions"
              className="text-xs font-semibold text-blue-600 hover:text-blue-800 transition-colors"
            >
              View Queue &rarr;
            </a>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-10 bg-slate-100 rounded-lg animate-pulse" />
              ))}
            </div>
          ) : !data?.top_missed_questions || data.top_missed_questions.length === 0 ? (
            <p className="text-sm text-slate-400 py-6 text-center">No knowledge gaps detected! Voice agent answered all queries.</p>
          ) : (
            <div className="space-y-3">
              {data.top_missed_questions.map((miss, idx) => (
                <div
                  key={idx}
                  className="flex items-center justify-between p-3 rounded-lg border border-slate-100 bg-amber-50/30"
                >
                  <div className="min-w-0 pr-3">
                    <div className="text-sm font-medium text-slate-900 truncate">"{miss.query}"</div>
                    <div className="text-xs text-slate-500">Status: {miss.status}</div>
                  </div>
                  <span className="shrink-0 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-100 text-amber-800">
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
