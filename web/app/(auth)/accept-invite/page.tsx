'use client';

import React, { useState, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';
import { apiClient } from '@/lib/api';
import { Bot, Loader2, ArrowRight } from 'lucide-react';

function AcceptInviteForm() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { refreshAuth } = useAuth();
  const token = searchParams.get('token') || '';

  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiClient('/api/auth/accept-invite', {
        method: 'POST',
        body: JSON.stringify({
          token,
          name: name.trim() || undefined,
          password: password || undefined,
        }),
      });
      await refreshAuth();
      router.push('/inbox');
    } catch (err: any) {
      setError(err.message || 'Failed to accept invitation. Link may be expired.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="text-center space-y-4">
        <p className="text-sm text-red-600">Missing invitation token.</p>
        <Link href="/login" className="text-sm font-semibold text-blue-600 hover:text-blue-500">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
      {error && (
        <div className="p-3.5 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
          {error}
        </div>
      )}

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Your Full Name</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
          placeholder="Jane Doe (if creating a new account)"
        />
        <p className="text-xs text-slate-400 mt-1">Required if you don't already have an account.</p>
      </div>

      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">Set Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
          placeholder="At least 8 characters"
        />
        <p className="text-xs text-slate-400 mt-1">Leave empty if you already have a Callwise password.</p>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full flex items-center justify-center py-2.5 px-4 border border-transparent rounded-lg shadow-sm text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 transition"
      >
        {loading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <>
            Accept & Join Team <ArrowRight className="w-4 h-4 ml-2" />
          </>
        )}
      </button>

      <div className="text-center">
        <Link href="/login" className="text-xs text-slate-500 hover:text-slate-800">
          Already have an account? Sign in first, then click the invite link again.
        </Link>
      </div>
    </form>
  );
}

export default function AcceptInvitePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-xl shadow-sm border border-slate-200">
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-md shadow-blue-500/20 mb-3">
            <Bot className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Join your team</h2>
          <p className="text-sm text-slate-500 mt-1">You've been invited to collaborate on Callwise</p>
        </div>

        <Suspense fallback={<div className="flex justify-center p-4"><Loader2 className="w-6 h-6 animate-spin text-blue-600" /></div>}>
          <AcceptInviteForm />
        </Suspense>
      </div>
    </div>
  );
}
