'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';
import {
  Inbox,
  Calendar,
  Users,
  Clock,
  BookOpen,
  HelpCircle,
  BarChart3,
  Settings,
  UserCheck,
  Bot,
  LogOut,
  ChevronDown,
  Menu,
  X,
  Building2,
  Check,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

const navItems = [
  { name: 'Inbox', href: '/inbox', icon: Inbox },
  { name: 'Appointments', href: '/appointments', icon: Calendar },
  { name: 'Contacts', href: '/contacts', icon: Users },
  { name: 'Follow-ups', href: '/follow-ups', icon: Clock },
  { name: 'Knowledge Base', href: '/knowledge', icon: BookOpen },
  { name: 'Missed Questions', href: '/missed-questions', icon: HelpCircle },
  { name: 'Test Agent', href: '/test-agent', icon: Bot },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
  { name: 'Team & Access', href: '/team', icon: UserCheck },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { user, currentBusiness, memberships, role, isLoading, logout, switchBusiness } =
    useAuth();
  const pathname = usePathname();
  const router = useRouter();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [businessDropdownOpen, setBusinessDropdownOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !user) {
      router.replace('/login');
    }
  }, [user, isLoading, router]);

  if (isLoading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const userInitials = user.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'U';

  const roleBadgeColors: Record<string, string> = {
    owner: 'bg-amber-100 text-amber-800 border-amber-200',
    admin: 'bg-purple-100 text-purple-800 border-purple-200',
    staff: 'bg-blue-100 text-blue-800 border-blue-200',
  };

  return (
    <div className="min-h-screen flex bg-slate-50">
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar (Desktop and Mobile) */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 text-slate-300 flex flex-col transition-transform duration-200 ease-in-out lg:static lg:translate-x-0',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand / Logo */}
        <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800">
          <Link href="/inbox" className="flex items-center space-x-3 text-white">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white shadow">
              <Bot className="w-5 h-5" />
            </div>
            <span className="font-bold text-lg tracking-tight">Callwise</span>
          </Link>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden text-slate-400 hover:text-white"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Business Switcher */}
        <div className="px-4 py-3 border-b border-slate-800 relative">
          <button
            onClick={() => setBusinessDropdownOpen(!businessDropdownOpen)}
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-left transition border border-slate-700/60"
          >
            <div className="flex items-center space-x-2.5 truncate">
              <Building2 className="w-4 h-4 text-blue-400 flex-shrink-0" />
              <div className="truncate">
                <p className="text-xs font-semibold text-slate-200 truncate">
                  {currentBusiness?.name || 'Select Business'}
                </p>
                <p className="text-[11px] text-slate-400 capitalize">{role || 'Member'}</p>
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-slate-400 flex-shrink-0 ml-1" />
          </button>

          {/* Business Switcher Dropdown */}
          {businessDropdownOpen && (
            <div className="absolute left-4 right-4 mt-2 bg-slate-800 rounded-lg shadow-xl border border-slate-700 py-1.5 z-50">
              <div className="px-3 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                Switch Business
              </div>
              {memberships.map((m) => (
                <button
                  key={m.id}
                  onClick={async () => {
                    setBusinessDropdownOpen(false);
                    if (m.business_id !== currentBusiness?.id) {
                      await switchBusiness(m.business_id);
                    }
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-xs text-slate-200 hover:bg-slate-700/60 text-left"
                >
                  <span className="truncate">{m.business?.name || 'Business'}</span>
                  {m.business_id === currentBusiness?.id && (
                    <Check className="w-4 h-4 text-blue-400 flex-shrink-0 ml-2" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Nav Links */}
        <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition',
                  isActive
                    ? 'bg-blue-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                )}
              >
                <Icon className={cn('w-4 h-4 mr-3 flex-shrink-0', isActive ? 'text-white' : 'text-slate-400')} />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Card & Logout */}
        <div className="p-3 border-t border-slate-800">
          <div className="flex items-center justify-between px-2 py-2">
            <div className="flex items-center space-x-3 truncate">
              <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-slate-200 flex-shrink-0">
                {userInitials}
              </div>
              <div className="truncate">
                <p className="text-xs font-semibold text-slate-200 truncate">{user.full_name}</p>
                <p className="text-[11px] text-slate-400 truncate">{user.email}</p>
              </div>
            </div>
            <button
              onClick={() => logout()}
              title="Sign out"
              className="text-slate-400 hover:text-red-400 p-1.5 rounded-lg hover:bg-slate-800 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Navbar */}
        <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-4 sm:px-6 lg:px-8">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-semibold text-slate-800 truncate">
              {navItems.find((n) => pathname.startsWith(n.href))?.name || 'Dashboard'}
            </h1>
          </div>

          <div className="flex items-center space-x-4">
            {role && (
              <span
                className={cn(
                  'text-xs font-semibold px-2.5 py-1 rounded-full border capitalize',
                  roleBadgeColors[role] || 'bg-slate-100 text-slate-800 border-slate-200'
                )}
              >
                {role}
              </span>
            )}
            <div className="text-right hidden sm:block">
              <p className="text-xs font-medium text-slate-800">{currentBusiness?.name}</p>
              <p className="text-[11px] text-slate-500">{currentBusiness?.timezone || 'UTC'}</p>
            </div>
          </div>
        </header>

        {/* Viewport Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}

