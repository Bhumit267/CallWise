export interface User {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  created_at: string;
}

export interface Business {
  id: string;
  name: string;
  phone_number?: string | null;
  timezone: string;
  is_active: boolean;
  created_at?: string;
  agent_prompt?: string | null;
  forwarding_number?: string | null;
  greeting?: string | null;
}

export interface Membership {
  id: string;
  user_id: string;
  business_id: string;
  role: 'owner' | 'admin' | 'staff';
  business: Business;
}

export interface AuthContextType {
  user: User | null;
  currentBusiness: Business | null;
  memberships: Membership[];
  role: 'owner' | 'admin' | 'staff' | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (fullName: string, email: string, password: string, businessName: string) => Promise<void>;
  logout: () => Promise<void>;
  switchBusiness: (businessId: string) => Promise<void>;
  refreshAuth: () => Promise<void>;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface CallRecord {
  id: string;
  business_id: string;
  caller_phone: string;
  direction: string;
  duration_seconds: number;
  outcome: string;
  summary?: string | null;
  sentiment?: string | null;
  started_at: string;
  ended_at?: string | null;
  created_at: string;
}

export interface AppointmentRecord {
  id: string;
  business_id: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  service_name?: string | null;
  service_id?: string | null;
  start_at: string;
  end_at: string;
  status: 'booked' | 'completed' | 'cancelled' | 'rescheduled';
  notes?: string | null;
  created_at: string;
}

export interface ContactRecord {
  id: string;
  business_id: string;
  name?: string | null;
  phone: string;
  email?: string | null;
  notes?: string | null;
  vip: boolean;
  dnc: boolean;
  created_at: string;
}

export interface FollowUpRecord {
  id: string;
  business_id: string;
  contact_id?: string | null;
  contact_phone?: string | null;
  contact_name?: string | null;
  note: string;
  status: 'pending' | 'completed' | 'dismissed';
  due_at?: string | null;
  created_at: string;
}

export interface KnowledgeMissRecord {
  id: string;
  business_id: string;
  question: string;
  occurrences: number;
  status: 'open' | 'resolved' | 'ignored';
  created_at: string;
}

export interface TeamMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: 'owner' | 'admin' | 'staff';
  created_at: string;
}

export interface TeamInvite {
  id: string;
  email: string;
  role: 'owner' | 'admin' | 'staff';
  token: string;
  expires_at: string;
  created_at: string;
}
