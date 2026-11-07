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

export interface InboxItem {
  id: string;
  item_type: 'call' | 'message' | 'transfer' | 'appointment';
  timestamp: string;
  title: string;
  description?: string | null;
  contact_id?: string | null;
  contact_name?: string | null;
  phone?: string | null;
  meta: Record<string, any>;
}

export interface CallTurnItem {
  id: string;
  speaker: 'caller' | 'agent' | string;
  text: string;
  latency_ms?: number | null;
  timestamp: string;
}

export interface CallDetail {
  id: string;
  caller_number?: string | null;
  contact_id?: string | null;
  contact_name?: string | null;
  started_at: string;
  ended_at?: string | null;
  duration_seconds: number;
  summary?: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  tts_provider?: string | null;
  stt_provider?: string | null;
  audio_url?: string | null;
  turns: CallTurnItem[];
  appointments: {
    id: string;
    service_id: string;
    customer_name: string;
    start_at: string;
    end_at: string;
    status: string;
  }[];
  messages: {
    id: string;
    caller_name: string;
    callback_number: string;
    reason: string;
    created_at: string;
  }[];
  transfers: {
    id: string;
    reason: string;
    status: string;
    timestamp: string;
  }[];
  knowledge_misses: {
    id: string;
    query: string;
    status: string;
    created_at: string;
  }[];
}

export interface MessageDetail {
  id: string;
  call_id?: string | null;
  contact_id?: string | null;
  contact_name?: string | null;
  caller_name: string;
  callback_number: string;
  reason: string;
  created_at: string;
  call_summary?: string | null;
}

export interface ServiceItem {
  id: string;
  name: string;
  duration_minutes: number;
  price?: number | null;
  description?: string | null;
  is_active: boolean;
}

export interface AppointmentListItem {
  id: string;
  service_id: string;
  service_name: string;
  customer_name: string;
  customer_phone: string;
  customer_email?: string | null;
  start_at: string;
  end_at: string;
  status: 'booked' | 'completed' | 'cancelled' | 'rescheduled';
  contact_id?: string | null;
  call_id?: string | null;
  created_at: string;
}

export interface AppointmentCalendarItem {
  id: string;
  service_id: string;
  service_name: string;
  customer_name: string;
  customer_phone: string;
  start_at: string;
  end_at: string;
  status: string;
}

export interface AppointmentDetail {
  id: string;
  service_id: string;
  service_name: string;
  customer_name: string;
  customer_phone: string; // UNMASKED
  customer_email?: string | null;
  start_at: string;
  end_at: string;
  status: 'booked' | 'completed' | 'cancelled' | 'rescheduled';
  contact_id?: string | null;
  call_id?: string | null;
  created_at: string;
  notes?: string | null;
  reminders: {
    id: string;
    scheduled_at: string;
    status: string;
    channel: string;
  }[];
  verification_attempts: {
    id: string;
    verified: boolean;
    timestamp: string;
  }[];
}

export interface ContactListItem {
  id: string;
  name?: string | null;
  phone: string;
  email?: string | null;
  notes?: string | null;
  do_not_contact: boolean;
  call_count: number;
  appointment_count: number;
  created_at: string;
}

export interface ContactDetail {
  id: string;
  name?: string | null;
  phone: string; // UNMASKED
  email?: string | null;
  notes?: string | null;
  do_not_contact: boolean;
  created_at: string;
  calls: {
    id: string;
    started_at: string;
    duration_seconds: number;
    summary?: string | null;
  }[];
  appointments: {
    id: string;
    service_id: string;
    service_name?: string | null;
    start_at: string;
    end_at: string;
    status: string;
  }[];
  messages: {
    id: string;
    caller_name: string;
    callback_number: string;
    reason: string;
    created_at: string;
  }[];
  follow_ups: {
    id: string;
    title: string;
    status: string;
    due_at?: string | null;
  }[];
}

export interface FollowUpListItem {
  id: string;
  contact_id?: string | null;
  contact_name?: string | null;
  assigned_to_user_id?: string | null;
  assigned_to_name?: string | null;
  title: string;
  description?: string | null;
  source: string;
  source_id?: string | null;
  status: 'open' | 'done' | 'snoozed';
  snoozed_until?: string | null;
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
