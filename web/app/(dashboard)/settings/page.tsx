'use client';

import React from 'react';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Business & Agent Settings</h2>
          <p className="text-sm text-slate-500">Configure phone routing, business hours, AI prompts, and services.</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Settings className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">Settings View Ready</h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1">
          Business profile, operating hours, forwarding numbers, and service catalogs will be managed here.
        </p>
      </div>
    </div>
  );
}
