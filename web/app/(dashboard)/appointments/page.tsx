'use client';

import React from 'react';
import { Calendar } from 'lucide-react';

export default function AppointmentsPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Appointments & Bookings</h2>
          <p className="text-sm text-slate-500">Manage bookings made by your AI voice receptionist and calendar sync.</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <Calendar className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">Appointments View Ready</h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1">
          Calendar appointments and scheduling details will be displayed here.
        </p>
      </div>
    </div>
  );
}
