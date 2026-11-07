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
  const [role, setRole] = useState<'owner' | 'admin' | 'staff' | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const refreshAuth = async () => {
    try {
      const data = await apiClient<{
        user: User;
        business: Business;
        memberships: Membership[];
      }>('/api/auth/me');

      setUser(data.user);
      setCurrentBusiness(data.business);
      setMemberships(data.memberships || []);

      const currentMembership = data.memberships?.find(
        (m) => m.business_id === data.business.id
      );
      setRole(currentMembership ? currentMembership.role : null);
    } catch (err) {
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
    await apiClient('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    await refreshAuth();
    router.push('/inbox');
  };

  const signup = async (
    fullName: string,
    email: string,
    password: string,
    businessName: string
  ) => {
    await apiClient('/api/auth/signup', {
      method: 'POST',
      body: JSON.stringify({
        full_name: fullName,
        email,
        password,
        business_name: businessName,
      }),
    });
    await refreshAuth();
    router.push('/inbox');
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

