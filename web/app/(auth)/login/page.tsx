'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/auth-context';
import { Bot, Loader2, ArrowRight, Eye, EyeOff, Sparkles } from 'lucide-react';

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || 'Failed to sign in. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#fbfaf6] px-4 py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background Neo-Brutalist decorative shapes */}
      <div className="absolute top-10 left-10 w-24 h-24 bg-[#ffe600] border-3 border-black rounded-2xl shadow-brutal rotate-6 pointer-events-none hidden md:block opacity-70" />
      <div className="absolute bottom-12 right-12 w-28 h-28 bg-[#38bdf8] border-3 border-black rounded-full shadow-brutal -rotate-12 pointer-events-none hidden md:block opacity-70" />
      <div className="absolute -bottom-8 left-1/4 w-32 h-16 bg-[#a3e635] border-3 border-black rounded-xl shadow-brutal rotate-3 pointer-events-none hidden lg:block opacity-60" />

      <div className="w-full max-w-md bg-white brutal-border-3 rounded-2xl p-8 sm:p-10 brutal-shadow-xl relative z-10">
        <div className="flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-1.5 bg-[#ffe600] brutal-border font-black uppercase text-[11px] tracking-wider px-3 py-1 rounded-md brutal-shadow-xs mb-5">
            <Sparkles className="w-3.5 h-3.5" /> Callwise Receptionist
          </div>

          <div className="w-16 h-16 bg-blue-600 brutal-border rounded-2xl flex items-center justify-center text-white brutal-shadow mb-4 rotate-[-3deg] hover:rotate-0 transition-transform">
            <Bot className="w-9 h-9" />
          </div>

          <h2 className="text-3xl font-black tracking-tight text-black">Sign in</h2>
          <p className="text-sm font-semibold text-neutral-600 mt-1">
            Access your AI Voice Receptionist workspace
          </p>
        </div>

        {error && (
          <div className="mt-6 p-4 rounded-xl bg-rose-100 brutal-border text-xs font-bold text-rose-950 brutal-shadow-xs">
            {error}
          </div>
        )}

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="block text-xs font-black uppercase tracking-wider text-black mb-1.5">
              Email Address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="brutal-input"
              placeholder="you@company.com"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-black uppercase tracking-wider text-black">
                Password
              </label>
              <Link
                href="/forgot-password"
                className="text-xs font-bold text-blue-600 hover:text-black underline underline-offset-2"
              >
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="brutal-input pr-11"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3.5 top-1/2 -translate-y-1/2 text-neutral-600 hover:text-black font-bold p-1"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center py-3.5 px-5 rounded-xl text-sm font-black text-white bg-blue-600 hover:bg-blue-500 brutal-border brutal-shadow brutal-shadow-hover disabled:opacity-50 uppercase tracking-wider"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                Sign In <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </button>
        </form>

        <div className="text-center text-sm font-medium text-neutral-600 mt-6 pt-5 border-t-2 border-black/10">
          Don&apos;t have an account?{' '}
          <Link href="/signup" className="font-black text-black hover:text-blue-600 underline underline-offset-2">
            Create an account
          </Link>
        </div>
      </div>
    </div>
  );
}
