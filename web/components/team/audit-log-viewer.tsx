'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';
import { AuditLogItem, PaginatedResponse } from '@/types/api';
import {
  ShieldAlert,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  User,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export function AuditLogViewer() {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient<PaginatedResponse<AuditLogItem>>(
        `/api/audit-logs?page=${page}&page_size=${pageSize}`
      );
      setLogs(res.items || []);
      setTotal(res.total || 0);
      setPages(res.pages || 1);
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const getActionBadge = (action: string) => {
    if (action.includes('delete') || action.includes('scrub') || action.includes('remove')) {
      return 'bg-red-50 text-red-700 border-red-200';
    }
    if (action.includes('create') || action.includes('invite') || action.includes('resolve')) {
      return 'bg-emerald-50 text-emerald-700 border-emerald-200';
    }
    return 'bg-blue-50 text-blue-700 border-blue-200';
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-4 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900">Compliance & Security Audit Trail</h3>
          <p className="text-xs text-slate-500">
            Immutable log of configuration edits, team role changes, and data access.
          </p>
        </div>

        <button
          onClick={() => fetchLogs()}
          title="Refresh logs"
          className="p-2 border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 rounded-lg shadow-sm"
        >
          <RefreshCw className={cn('w-4 h-4', loading && 'animate-spin text-blue-600')} />
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200">
          {error}
        </div>
      )}

      {loading && logs.length === 0 ? (
        <div className="divide-y divide-slate-100">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="py-3 animate-pulse space-y-1">
              <div className="h-4 bg-slate-200 rounded w-48" />
              <div className="h-3 bg-slate-100 rounded w-64" />
            </div>
          ))}
        </div>
      ) : logs.length === 0 ? (
        <div className="py-12 text-center text-xs text-slate-400">
          No audit entries recorded yet.
        </div>
      ) : (
        <div className="divide-y divide-slate-100">
          {logs.map((log) => {
            const isExpanded = expandedId === log.id;
            return (
              <div key={log.id} className="py-3 text-xs space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span
                      className={cn(
                        'px-2 py-0.5 rounded border text-[11px] font-semibold uppercase',
                        getActionBadge(log.action)
                      )}
                    >
                      {log.action.replace(/_/g, ' ')}
                    </span>
                    <span className="font-semibold text-slate-800">
                      {log.user_email || log.user_name || 'System / Auto'}
                    </span>
                    <span className="text-slate-400">on</span>
                    <span className="font-mono text-slate-600">{log.resource_type}</span>
                  </div>

                  <div className="flex items-center space-x-3 text-slate-400">
                    <span>{formatDate(log.created_at)}</span>
                    {log.changes && Object.keys(log.changes).length > 0 && (
                      <button
                        onClick={() => setExpandedId(isExpanded ? null : log.id)}
                        className="text-blue-600 hover:text-blue-700 flex items-center"
                      >
                        {isExpanded ? (
                          <ChevronUp className="w-3.5 h-3.5" />
                        ) : (
                          <ChevronDown className="w-3.5 h-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {isExpanded && log.changes && (
                  <pre className="p-3 bg-slate-900 text-slate-200 rounded-lg font-mono text-[11px] overflow-x-auto">
                    {JSON.stringify(log.changes, null, 2)}
                  </pre>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Pagination */}
      {pages > 1 && (
        <div className="pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-500">
          <p>
            Page <span className="font-semibold text-slate-700">{page}</span> of{' '}
            <span className="font-semibold text-slate-700">{pages}</span> ({total} entries)
          </p>

          <div className="flex items-center space-x-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              className="p-1 border border-slate-200 rounded-md text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <button
              disabled={page >= pages}
              onClick={() => setPage((p) => Math.min(pages, p + 1))}
              className="p-1 border border-slate-200 rounded-md text-slate-600 hover:bg-slate-100 disabled:opacity-40"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

