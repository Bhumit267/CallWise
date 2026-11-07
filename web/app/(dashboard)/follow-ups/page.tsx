'use client';

import React from 'react';
import { Clock } from 'lucide-react';

export default function FollowUpsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Follow-up Tasks & Action Items</h2>
          <p className="text-sm text-slate-500">Track promises, callbacks, and pending human actions.</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Clock className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">Follow-ups View Ready</h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1">
          Pending callback requests and AI follow-up action items will be organized here.
        </p>
      </div>
    </div>
  );
}

