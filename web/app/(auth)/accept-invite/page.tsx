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
        <p className="text-sm font-bold text-rose-600 bg-rose-50 p-3 rounded-xl border-2 border-black">
          Missing invitation token.
        </p>
        <Link href="/login" className="inline-block text-xs font-black uppercase text-black hover:underline">
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
      {error && (
        <div className="p-4 rounded-xl bg-rose-100 border-2 border-black text-xs font-bold text-rose-950 shadow-brutal-xs">
          {error}
        </div>
      )}

      <div>
        <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
          Your Full Name
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-black bg-white focus:outline-none focus:bg-amber-50/30 text-sm font-bold shadow-brutal-xs focus:shadow-brutal transition-all"
          placeholder="Jane Doe (if creating a new account)"
        />
      </div>

      <div>
        <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
          Create Password (if new user)
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full px-4 py-3 rounded-xl border-2 border-black bg-white focus:outline-none focus:bg-amber-50/30 text-sm font-bold shadow-brutal-xs focus:shadow-brutal transition-all"
          placeholder="Leave blank if you already have an account"
        />
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full mt-2 flex items-center justify-center py-3.5 px-5 rounded-xl text-sm font-black text-white bg-blue-600 hover:bg-blue-500 border-2 border-black shadow-brutal hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-brutal-sm active:translate-x-[4px] active:translate-y-[4px] active:shadow-none disabled:opacity-50 transition-all uppercase tracking-wider"
      >
        {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Accept & Join Workspace'}
      </button>

      <div className="text-center pt-2">
        <Link
          href="/login"
          className="inline-flex items-center text-xs font-black text-neutral-600 hover:text-black uppercase tracking-wider"
        >
          Back to sign in
        </Link>
      </div>
    </form>
  );
}

export default function AcceptInvitePage() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fbfaf6] px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      <div className="w-full max-w-md bg-white border-3 border-black rounded-2xl p-8 sm:p-10 shadow-brutal-xl relative z-10">
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-blue-600 border-2 border-black rounded-2xl flex items-center justify-center text-white shadow-brutal mb-4 rotate-[-2deg]">
            <Bot className="w-9 h-9" />
          </div>
          <h2 className="text-3xl font-black tracking-tight text-black">Team Invitation</h2>
          <p className="text-sm font-medium text-neutral-600 mt-1">
            Join your company on Callwise
          </p>
        </div>

        <Suspense fallback={<div className="flex justify-center p-8"><Loader2 className="w-8 h-8 animate-spin text-black" /></div>}>
          <AcceptInviteForm />
        </Suspense>
      </div>
    </div>
  );
}
