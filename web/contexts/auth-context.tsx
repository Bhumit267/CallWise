'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api';
import { User, Business, Membership, AuthContextType } from '@/types/api';

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [currentBusiness, setCurrentBusiness] = useState<Business | null>(null);
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [role, setRole] = useState<'owner' | 'manager' | 'admin' | 'staff' | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const refreshAuth = async () => {
    try {
      const data = await apiClient<any>('/api/auth/me');
      setUser(data.user);
      const activeBiz = data.current_business || (data.memberships && data.memberships[0]) || null;
      setCurrentBusiness(activeBiz);
      setMemberships(data.memberships || []);
      setRole(activeBiz?.role || null);
    } catch (err) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('callwise_token');
      }
      setUser(null);
      setCurrentBusiness(null);
      setMemberships([]);
      setRole(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    refreshAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await apiClient<any>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    if (res?.session_token && typeof window !== 'undefined') {
      localStorage.setItem('callwise_token', res.session_token);
    }
    if (res?.user) setUser(res.user);
    if (res?.current_business) setCurrentBusiness(res.current_business);
    if (res?.memberships) setMemberships(res.memberships);
    if (res?.current_business?.role) setRole(res.current_business.role);
    window.location.href = '/inbox';
  };

  const signup = async (
    fullName: string,
    email: string,
    password: string,
    businessName: string,
    businessType: string = 'Dental Clinic'
  ) => {
    const res = await apiClient<any>('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({
        owner_name: fullName.trim(),
        email: email.trim(),
        password,
        business_name: businessName.trim(),
        business_type: businessType.trim() || 'Dental Clinic',
      }),
    });
    if (res?.session_token && typeof window !== 'undefined') {
      localStorage.setItem('callwise_token', res.session_token);
    }
    if (res?.user) setUser(res.user);
    if (res?.current_business) setCurrentBusiness(res.current_business);
    if (res?.memberships) setMemberships(res.memberships);
    if (res?.current_business?.role) setRole(res.current_business.role);
    window.location.href = '/onboarding';
  };

  const logout = async () => {
    try {
      await apiClient('/api/auth/logout', { method: 'POST' });
    } catch (err) {
      // Ignore error on logout
    } finally {
      setUser(null);
      setCurrentBusiness(null);
      setMemberships([]);
      setRole(null);
      router.push('/login');
    }
  };

  const switchBusiness = async (businessId: string) => {
    await apiClient('/api/auth/switch-business', {
      method: 'POST',
      body: JSON.stringify({ business_id: businessId }),
    });
    await refreshAuth();
    // Refresh page or trigger re-fetch of current business data
    router.refresh();
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        currentBusiness,
        memberships,
        role,
        isLoading,
        login,
        signup,
        logout,
        switchBusiness,
        refreshAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

