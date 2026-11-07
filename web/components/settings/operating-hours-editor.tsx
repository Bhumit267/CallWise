'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { Clock, Check, Loader2, Save } from 'lucide-react';
import { cn } from '@/lib/utils';

const DAYS = [
  { key: 'monday', label: 'Monday' },
  { key: 'tuesday', label: 'Tuesday' },
  { key: 'wednesday', label: 'Wednesday' },
  { key: 'thursday', label: 'Thursday' },
  { key: 'friday', label: 'Friday' },
  { key: 'saturday', label: 'Saturday' },
  { key: 'sunday', label: 'Sunday' },
];

const DEFAULT_HOURS = {
  monday: { open: '09:00', close: '17:00', closed: false },
  tuesday: { open: '09:00', close: '17:00', closed: false },
  wednesday: { open: '09:00', close: '17:00', closed: false },
  thursday: { open: '09:00', close: '17:00', closed: false },
  friday: { open: '09:00', close: '17:00', closed: false },
  saturday: { open: null, close: null, closed: true },
  sunday: { open: null, close: null, closed: true },
};

interface OperatingHoursEditorProps {
  initialHours?: Record<string, any>;
  onSaved?: () => void;
}

export function OperatingHoursEditor({
  initialHours,
  onSaved,
}: OperatingHoursEditorProps) {
  const [hours, setHours] = useState<Record<string, any>>(DEFAULT_HOURS);
  const [loading, setLoading] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialHours && Object.keys(initialHours).length > 0) {
      setHours({ ...DEFAULT_HOURS, ...initialHours });
    }
  }, [initialHours]);

  const handleToggleClosed = (day: string) => {
    setHours((prev) => {
      const dayData = prev[day] || { open: '09:00', close: '17:00', closed: false };
      const nextClosed = !dayData.closed;
      return {
        ...prev,
        [day]: {
          ...dayData,
          closed: nextClosed,
          open: nextClosed ? null : dayData.open || '09:00',
          close: nextClosed ? null : dayData.close || '17:00',
        },
      };
    });
    setSavedSuccess(false);
  };

  const handleTimeChange = (day: string, field: 'open' | 'close', value: string) => {
    setHours((prev) => ({
      ...prev,
      [day]: {
        ...(prev[day] || { closed: false }),
        [field]: value,
      },
    }));
    setSavedSuccess(false);
  };

  const handleSave = async () => {
    setLoading(true);
    setError(null);
    setSavedSuccess(false);

    try {
      await apiClient('/api/settings/hours', {
        method: 'PUT',
        body: JSON.stringify({ hours }),
      });
      setSavedSuccess(true);
      if (onSaved) onSaved();
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to update operating hours');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-6 space-y-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
        <div>
          <h3 className="text-base font-bold text-slate-900">Weekly Operating Hours</h3>
          <p className="text-xs text-slate-500">
            Calls received outside these hours trigger after-hours routing, voicemail, or emergency handling.
          </p>
        </div>

        <button
          onClick={handleSave}
          disabled={loading}
          className="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-sm transition disabled:opacity-50"
        >
          {loading ? (
            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
          ) : savedSuccess ? (
            <Check className="w-4 h-4 mr-1.5 text-emerald-300" />
          ) : (
            <Save className="w-4 h-4 mr-1.5" />
          )}
          {savedSuccess ? 'Hours Saved!' : 'Save Schedule'}
        </button>
      </div>

      {error && (
        <div className="p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-200">
          {error}
        </div>
      )}

      <div className="divide-y divide-slate-100">
        {DAYS.map((day) => {
          const dayData = hours[day.key] || { closed: false, open: '09:00', close: '17:00' };
          const isClosed = Boolean(dayData.closed);

          return (
            <div
              key={day.key}
              className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs"
            >
              <div className="w-28 font-semibold text-slate-800">{day.label}</div>

              <div className="flex items-center space-x-4">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isClosed}
                    onChange={() => handleToggleClosed(day.key)}
                    className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                  />
                  <span className="text-slate-600 font-medium">Closed</span>
                </label>

                {!isClosed ? (
                  <div className="flex items-center space-x-2">
                    <input
                      type="time"
                      value={dayData.open || '09:00'}
                      onChange={(e) => handleTimeChange(day.key, 'open', e.target.value)}
                      className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                    <span className="text-slate-400">to</span>
                    <input
                      type="time"
                      value={dayData.close || '17:00'}
                      onChange={(e) => handleTimeChange(day.key, 'close', e.target.value)}
                      className="px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:outline-none focus:ring-2 focus:ring-blue-600"
                    />
                  </div>
                ) : (
                  <span className="text-slate-400 italic">No business hours set</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
