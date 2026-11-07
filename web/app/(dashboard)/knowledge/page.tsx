'use client';

import React from 'react';
import { BookOpen } from 'lucide-react';

export default function KnowledgePage() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Knowledge Base & Ingestion</h2>
          <p className="text-sm text-slate-500">Ingest websites, upload documents, and train your AI receptionist.</p>
        </div>
      </div>
      <div className="bg-white rounded-xl border border-slate-200 p-12 text-center shadow-sm">
        <div className="w-12 h-12 rounded-full bg-blue-50 text-blue-600 flex items-center justify-center mx-auto mb-4">
          <BookOpen className="w-6 h-6" />
        </div>
        <h3 className="text-base font-semibold text-slate-900">Knowledge Base Ready</h3>
        <p className="text-sm text-slate-500 max-w-sm mx-auto mt-1">
          Knowledge sources, document chunks, and live crawl status will appear here.
        </p>
      </div>
    </div>
  );
}

