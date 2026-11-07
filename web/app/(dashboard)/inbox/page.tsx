'use client';

import React from 'react';
import { Inbox } from 'lucide-react';

export default function InboxPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Unified Call & Message Inbox</h2>
          <p className="text-sm text-slate-500">Live feed of incoming calls, voicemail messages, and conversations.</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Inbox className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">Inbox Initialized</h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1">
          Calls and messages received by your AI voice receptionist will appear here.
        </p>
      </div>
    </div>
  );
}

