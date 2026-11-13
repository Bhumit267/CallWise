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
  PhoneCall,
  MessageSquareCode,
  Gauge,
  LogOut,
  ChevronDown,
  Menu,
  X,
  Building2,
  Check,
  Loader2,
  Sparkles,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface NavItem {
  name: string;
  href: string;
  icon: any;
  minRole?: 'owner' | 'manager' | 'staff';
}

const navItems: NavItem[] = [
  { name: 'Inbox', href: '/inbox', icon: Inbox },
  { name: 'Appointments', href: '/appointments', icon: Calendar },
  { name: 'Contacts', href: '/contacts', icon: Users },
  { name: 'Follow-ups', href: '/follow-ups', icon: Clock },
  { name: 'Knowledge Base', href: '/knowledge', icon: BookOpen },
  { name: 'Missed Questions', href: '/missed-questions', icon: HelpCircle },
  { name: 'Phone Numbers', href: '/phone-numbers', icon: PhoneCall, minRole: 'manager' },
  { name: 'Website Widget', href: '/widget', icon: MessageSquareCode, minRole: 'manager' },
  { name: 'Usage & Limits', href: '/usage', icon: Gauge, minRole: 'manager' },
  { name: 'Test Agent', href: '/test-agent', icon: Bot },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
  { name: 'Team & Access', href: '/team', icon: UserCheck, minRole: 'manager' },
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
      <div className="min-h-screen flex items-center justify-center bg-[#fbfaf6]">
        <div className="p-6 bg-white brutal-border-3 rounded-2xl brutal-shadow-lg flex items-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-black" />
          <span className="font-black text-sm uppercase tracking-wider">Loading Callwise...</span>
        </div>
      </div>
    );
  }

  const userRole = role?.toLowerCase() || 'staff';
  const roleHierarchy: Record<string, number> = { staff: 1, manager: 2, owner: 3 };
  const userLevel = roleHierarchy[userRole] || 1;

  const visibleNavItems = navItems.filter((item) => {
    if (!item.minRole) return true;
    return userLevel >= (roleHierarchy[item.minRole] || 1);
  });

  const userInitials = user.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : 'U';

  const roleBadgeStyles: Record<string, string> = {
    owner: 'bg-[#fef9c3] text-[#854d0e]',
    manager: 'bg-[#f3e8ff] text-[#6b21a8]',
    admin: 'bg-[#f3e8ff] text-[#6b21a8]',
    staff: 'bg-[#dbeafe] text-[#1e40af]',
  };

  return (
    <div className="h-screen max-h-screen flex bg-[#fbfaf6] text-black overflow-hidden">
      {/* Mobile Backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar (Desktop and Mobile) */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 w-64 bg-[#0a0a0a] text-white flex flex-col transition-transform duration-200 ease-in-out lg:static lg:translate-x-0 border-r-3 border-black shadow-brutal-lg lg:shadow-none',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        )}
      >
        {/* Brand / Logo */}
        <div className="h-16 flex items-center justify-between px-5 border-b-2 border-neutral-800">
          <Link href="/inbox" className="flex items-center space-x-3 text-white group">
            <div className="w-9 h-9 bg-[#ffe600] text-black brutal-border rounded-xl flex items-center justify-center font-black brutal-shadow-xs rotate-[-3deg] group-hover:rotate-0 transition-transform">
              <Bot className="w-5 h-5 stroke-[2.5]" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-black text-xl tracking-tight text-white">Callwise</span>
              <span className="text-[10px] bg-[#a3e635] text-black px-1.5 py-0.5 rounded font-black brutal-border uppercase tracking-wider">
                AI
              </span>
            </div>
          </Link>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden text-neutral-400 hover:text-white p-1"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Business Switcher */}
        <div className="px-4 py-3 border-b-2 border-neutral-800 relative">
          <button
            onClick={() => setBusinessDropdownOpen(!businessDropdownOpen)}
            className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl bg-neutral-900 hover:bg-neutral-800 text-left transition border-2 border-neutral-700 hover:border-white brutal-shadow-xs"
          >
            <div className="flex items-center space-x-2.5 truncate">
              <Building2 className="w-4 h-4 text-[#ffe600] flex-shrink-0" />
              <div className="truncate">
                <p className="text-xs font-black text-white truncate">
                  {currentBusiness?.name || 'Select Business'}
                </p>
                <p className="text-[10px] text-neutral-400 font-mono uppercase tracking-wider">
                  {role || 'Member'}
                </p>
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-neutral-400 flex-shrink-0 ml-1" />
          </button>

          {/* Business Switcher Dropdown */}
          {businessDropdownOpen && (
            <div className="absolute left-4 right-4 mt-2 bg-neutral-900 rounded-xl brutal-border shadow-brutal py-2 z-50">
              <div className="px-3 py-1 text-[10px] font-black text-neutral-400 uppercase tracking-widest">
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
                  className="w-full flex items-center justify-between px-3 py-2 text-xs font-bold text-neutral-200 hover:bg-neutral-800 text-left"
                >
                  <span className="truncate">{m.business?.name || 'Business'}</span>
                  {m.business_id === currentBusiness?.id && (
                    <Check className="w-4 h-4 text-[#ffe600] flex-shrink-0 ml-2" />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Nav Links */}
        <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  'flex items-center px-3.5 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider transition-all duration-100',
                  isActive
                    ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs translate-x-[2px]'
                    : 'text-neutral-300 hover:text-white hover:bg-neutral-900 border-2 border-transparent hover:border-neutral-700'
                )}
              >
                <Icon
                  className={cn(
                    'w-4 h-4 mr-3 flex-shrink-0 stroke-[2.5]',
                    isActive ? 'text-black' : 'text-neutral-400'
                  )}
                />
                <span>{item.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Card & Logout */}
        <div className="p-3 border-t-2 border-neutral-800 bg-[#000000]">
          <div className="flex items-center justify-between px-2 py-2 bg-neutral-900 rounded-xl border-2 border-neutral-800">
            <div className="flex items-center space-x-2.5 truncate">
              <div className="w-8 h-8 rounded-lg bg-blue-600 brutal-border flex items-center justify-center text-xs font-black text-white flex-shrink-0">
                {userInitials}
              </div>
              <div className="truncate">
                <p className="text-xs font-black text-white truncate">{user.full_name}</p>
                <p className="text-[10px] text-neutral-400 font-mono truncate">{user.email}</p>
              </div>
            </div>
            <button
              onClick={() => logout()}
              title="Sign out"
              className="text-neutral-400 hover:text-rose-400 p-1.5 rounded-lg hover:bg-neutral-800 transition"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Top Navbar */}
        <header className="h-16 shrink-0 bg-white border-b-3 border-black flex items-center justify-between px-4 sm:px-6 lg:px-8 shadow-xs">
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden p-2 rounded-xl brutal-border bg-white text-black hover:bg-neutral-100 brutal-shadow-xs"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-lg font-black uppercase tracking-tight text-black truncate">
              {navItems.find((n) => pathname.startsWith(n.href))?.name || 'Dashboard'}
            </h1>
          </div>

          <div className="flex items-center space-x-3 sm:space-x-4">
            {/* Live voice worker badge */}
            <div className="hidden md:inline-flex items-center gap-1.5 bg-[#dcfce7] text-[#166534] brutal-border font-black text-[11px] uppercase tracking-wider px-2.5 py-1 rounded-lg brutal-shadow-xs">
              <span className="w-2 h-2 rounded-full bg-[#22c55e] animate-pulse"></span>
              Live Agent Ready
            </div>

            {role && (
              <span
                className={cn(
                  'text-[11px] font-black uppercase tracking-wider px-2.5 py-1 rounded-lg brutal-border brutal-shadow-xs capitalize',
                  roleBadgeStyles[role] || 'bg-neutral-100 text-black'
                )}
              >
                {role}
              </span>
            )}
            <div className="text-right hidden sm:block">
              <p className="text-xs font-black text-black leading-tight">{currentBusiness?.name}</p>
              <p className="text-[10px] font-mono text-neutral-500">{currentBusiness?.timezone || 'UTC'}</p>
            </div>
          </div>
        </header>

        {/* Viewport Content */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 overflow-y-auto min-h-0 pb-24">{children}</main>
      </div>
    </div>
  );
}
