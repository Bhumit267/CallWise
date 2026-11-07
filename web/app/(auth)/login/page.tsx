'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useAuth } from '@/contexts/auth-context';
import { Bot, Loader2, ArrowRight, Eye, EyeOff } from 'lucide-react';

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
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-12 sm:px-6 lg:px-8">
      <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-xl shadow-sm border border-slate-200">
        <div className="flex flex-col items-center">
          <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center text-white shadow-md shadow-blue-500/20 mb-3">
            <Bot className="w-7 h-7" />
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-slate-900">Sign in to Callwise</h2>
          <p className="text-sm text-slate-500 mt-1">Your AI Voice Receptionist Platform</p>
        </div>

        {error && (
          <div className="p-3.5 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
            {error}
          </div>
        )}

        <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">Email address</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
              placeholder="you@company.com"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-slate-700">Password</label>
              <Link
                href="/forgot-password"
                className="text-xs font-medium text-blue-600 hover:text-blue-500"
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
                className="w-full px-3.5 py-2.5 pr-10 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-transparent text-sm"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Quick Fill Demo Credentials */}
          <div className="p-3 bg-slate-50 border border-slate-200 rounded-lg text-xs flex items-center justify-between">
            <span className="text-slate-600 font-medium">Demo login:</span>
            <button
              type="button"
              onClick={() => {
                setEmail('bhumit@gmail.com');
                setPassword('Password123!');
              }}
              className="text-blue-600 font-bold hover:underline"
            >
              Autofill bhumit@gmail.com
            </button>
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
                Sign in <ArrowRight className="w-4 h-4 ml-2" />
              </>
            )}
          </button>
        </form>

        <div className="text-center text-sm text-slate-600 pt-2 border-t border-slate-100">
          Don&apos;t have an account?{' '}
          <Link href="/signup" className="font-semibold text-blue-600 hover:text-blue-500">
            Sign up
          </Link>
        </div>
      </div>
    </div>
  );
}

