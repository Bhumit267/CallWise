'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { apiClient } from '@/lib/api';
import { Bot, Loader2, ArrowLeft, MailCheck, Sparkles } from 'lucide-react';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await apiClient('/api/auth/forgot-password', {
        method: 'POST',
        body: JSON.stringify({ email }),
      });
      setSubmitted(true);
    } catch (err: any) {
      setError(err.message || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fbfaf6] px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      <div className="w-full max-w-md bg-white border-3 border-black rounded-2xl p-8 sm:p-10 shadow-brutal-xl relative z-10">
        <div className="flex flex-col items-center text-center">
          <div className="w-16 h-16 bg-blue-600 border-2 border-black rounded-2xl flex items-center justify-center text-white shadow-brutal mb-4 rotate-[-3deg]">
            <Bot className="w-9 h-9" />
          </div>

          <h2 className="text-3xl font-black tracking-tight text-black">Reset Password</h2>
          <p className="text-sm font-medium text-neutral-600 mt-1">
            We&apos;ll send you an email with reset instructions
          </p>
        </div>

        {submitted ? (
          <div className="mt-8 text-center space-y-5">
            <div className="mx-auto w-16 h-16 rounded-2xl bg-[#a3e635] border-2 border-black shadow-brutal flex items-center justify-center text-black">
              <MailCheck className="w-8 h-8" />
            </div>
            <p className="text-sm font-medium text-neutral-800 bg-amber-50 p-4 rounded-xl border-2 border-black shadow-brutal-xs">
              If an account exists for <span className="font-black text-black">{email}</span>, you will receive a reset link shortly.
            </p>
            <div className="pt-2">
              <Link
                href="/login"
                className="w-full inline-flex items-center justify-center py-3 px-4 rounded-xl font-black text-sm text-black bg-white border-2 border-black shadow-brutal hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-brutal-xs uppercase tracking-wider"
              >
                <ArrowLeft className="w-4 h-4 mr-2" /> Back to sign in
              </Link>
            </div>
          </div>
        ) : (
          <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
            {error && (
              <div className="p-4 rounded-xl bg-rose-100 border-2 border-black text-xs font-bold text-rose-950 shadow-brutal-xs">
                {error}
              </div>
            )}

            <div>
              <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
                Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 rounded-xl border-2 border-black bg-white focus:outline-none focus:bg-amber-50/30 text-sm font-bold placeholder:text-neutral-400 placeholder:font-normal shadow-brutal-xs focus:shadow-brutal transition-all"
                placeholder="you@company.com"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center py-3.5 px-5 rounded-xl text-sm font-black text-white bg-blue-600 hover:bg-blue-500 border-2 border-black shadow-brutal hover:translate-x-[2px] hover:translate-y-[2px] hover:shadow-brutal-sm active:translate-x-[4px] active:translate-y-[4px] active:shadow-none disabled:opacity-50 transition-all uppercase tracking-wider"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send reset link'}
            </button>

            <div className="text-center pt-2">
              <Link
                href="/login"
                className="inline-flex items-center text-xs font-black text-neutral-600 hover:text-black uppercase tracking-wider"
              >
                <ArrowLeft className="w-4 h-4 mr-1.5" /> Back to sign in
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
