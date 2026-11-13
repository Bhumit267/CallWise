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
  business_type?: string | null;
  phone_number?: string | null;
  timezone: string;
  is_active: boolean;
  created_at?: string;
  agent_prompt?: string | null;
  forwarding_number?: string | null;
  transfer_number?: string | null;
  notification_email?: string | null;
  greeting?: string | null;
  tone?: string | null;
  hours?: Record<string, any> | null;
}

export interface Membership {
  id: string;
  user_id: string;
  business_id: string;
  role: 'owner' | 'manager' | 'admin' | 'staff';
  business: Business;
}

export interface AuthContextType {
  user: User | null;
  currentBusiness: Business | null;
  memberships: Membership[];
  role: 'owner' | 'manager' | 'admin' | 'staff' | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (fullName: string, email: string, password: string, businessName: string, businessType?: string) => Promise<void>;
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
  intent?: string | null;
  urgency?: 'high' | 'normal' | string | null;
  sentiment?: 'positive' | 'neutral' | 'frustrated' | string | null;
  tags?: string[] | null;
  structured_notes?: Record<string, any> | null;
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
  price: number;
  description?: string | null;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface BusinessSettingsResponse {
  id: string;
  name: string;
  business_type: string;
  greeting: string;
  tone: string;
  timezone: string;
  transfer_number?: string | null;
  notification_email?: string | null;
  retention_days?: number;
  website_url?: string | null;
  hours: Record<string, { open?: string | null; close?: string | null; closed: boolean }>;
  providers: {
    llm_provider: string;
    tts_provider: string;
    stt_provider: string;
    embedding_provider: string;
    email_notifications_enabled: boolean;
    google_calendar_enabled: boolean;
  };
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
  customer_phone: string;
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
  phone: string;
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

export interface DocumentSourceItem {
  id: string;
  title: string;
  source_type: 'file' | 'url' | 'qa_snippet' | string;
  source_uri: string;
  chunk_count: number;
  created_at: string;
}

export interface KnowledgeMissListItem {
  id: string;
  call_id?: string | null;
  query: string;
  status: 'unresolved' | 'resolved' | 'ignored' | string;
  resolved_at?: string | null;
  resolved_answer?: string | null;
  created_at: string;
}

export interface KnowledgeMissGroupItem {
  query: string;
  count: number;
  status: string;
  last_asked_at: string;
  sample_miss_id_str?: string;
  sample_miss_id?: string;
}

export interface JobStatusResponse {
  id: string;
  type: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | string;
  progress: number;
  result?: Record<string, any> | null;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

// ============================================================================
// Analytics & Team Schemas
// ============================================================================

export interface DailyCalls {
  date: string;
  total: number;
  answered: number;
  transferred: number;
  message_taken: number;
}

export interface TopServiceItem {
  service_id: string;
  name: string;
  booking_count: number;
  revenue: number;
}

export interface TopMissedQuestionItem {
  query: string;
  count: number;
  status: string;
}

export interface LatencyMetrics {
  median_ms: number;
  p95_ms: number;
  sample_count: number;
}

export interface HourDistribution {
  hour: number;
  call_count: number;
}

export interface AnalyticsOverviewResponse {
  date_range_start: string;
  date_range_end: string;
  timezone: string;
  total_calls: number;
  answered_count: number;
  transferred_count: number;
  message_taken_count: number;
  booking_conversion_rate: number;
  calls_per_day: DailyCalls[];
  top_services: TopServiceItem[];
  top_missed_questions: TopMissedQuestionItem[];
  latency_metrics: LatencyMetrics;
  busiest_hours: HourDistribution[];
}

export interface TeamMemberResponse {
  user_id: string;
  name: string;
  email: string;
  role: 'owner' | 'manager' | 'staff' | string;
  joined_at: string;
}

export interface InviteResponse {
  id: string;
  email: string;
  role: 'owner' | 'manager' | 'staff' | string;
  expires_at: string;
  created_at: string;
}

export interface AuditLogItem {
  id: string;
  user_id?: string | null;
  user_name?: string | null;
  user_email?: string | null;
  action: string;
  resource_type: string;
  resource_id?: string | null;
  changes?: Record<string, any> | null;
  ip_address?: string | null;
  created_at: string;
}


// ============================================================================
// Onboarding & Test Agent Schemas
// ============================================================================

export interface OnboardingSetupRequest {
  name: string;
  business_type: string;
  timezone: string;
  greeting: string;
  tone: string;
  hours?: Record<string, any>;
  transfer_number?: string | null;
  notification_email?: string | null;
  website_url?: string | null;
  retention_days?: number;
  services?: {
    name: string;
    duration_minutes: number;
    price: number;
    description?: string | null;
    is_active?: boolean;
  }[];
}

export interface OnboardingSetupResponse {
  business_id: string;
  name: string;
  job_id?: string | null;
  services_count: number;
  message: string;
}

export interface TestAgentRequest {
  message: string;
  call_id?: string | null;
}

export interface TestAgentResponse {
  call_id: string;
  reply: string;
  latency_ms: number;
}


// ============================================================================
// Phase 4: Telephony, Chat Widget & Usage Schemas
// ============================================================================

export interface PhoneNumberItem {
  id: string;
  business_id: string;
  e164_number: string;
  provider: 'livekit' | 'twilio' | 'sip' | string;
  label: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PhoneNumberCreate {
  e164_number: string;
  provider: string;
  label: string;
  is_active?: boolean;
}

export interface PhoneNumberUpdate {
  label?: string;
  is_active?: boolean;
}

export interface WidgetSettingsData {
  id: string;
  business_id: string;
  public_key: string;
  is_enabled: boolean;
  allowed_origins: string;
  primary_color: string;
  greeting_message: string;
  ask_lead_capture: boolean;
  require_lead_name: boolean;
  allow_booking: boolean;
  rate_limit_rpm: number;
  max_turns_per_session: number;
  created_at: string;
  updated_at: string;
}

export interface WidgetSettingsUpdate {
  is_enabled?: boolean;
  allowed_origins?: string;
  primary_color?: string;
  greeting_message?: string;
  ask_lead_capture?: boolean;
  require_lead_name?: boolean;
  allow_booking?: boolean;
  rate_limit_rpm?: number;
  max_turns_per_session?: number;
}

export interface WidgetPublicConfig {
  business_id: string;
  business_name: string;
  primary_color: string;
  greeting_message: string;
  ask_lead_capture: boolean;
  require_lead_name: boolean;
  allow_booking: boolean;
}

export interface UsageLimitsData {
  voice_minutes_per_month: number;
  chat_messages_per_month: number;
  max_concurrent_calls: number;
  max_call_duration_seconds: number;
  llm_tokens_per_month: number;
  hard_limit_enforced: boolean;
}

export interface CurrentMonthUsageData {
  voice_minutes: number;
  chat_messages: number;
  llm_tokens: number;
  total_cost_usd: number;
}

export interface DailyUsageItem {
  date: string;
  voice_minutes: number;
  chat_messages: number;
  total_cost_usd: number;
}

export interface UsageSummaryResponse {
  limits: UsageLimitsData;
  current_month: CurrentMonthUsageData;
  daily_usage: DailyUsageItem[];
  pricing_table: Record<string, any>;
}

export interface UsageRecordItem {
  id: string;
  call_id?: string | null;
  session_type: 'phone' | 'widget' | 'chat' | string;
  duration_seconds: number;
  stt_seconds: number;
  tts_characters: number;
  llm_input_tokens: number;
  llm_output_tokens: number;
  llm_provider?: string | null;
  llm_model?: string | null;
  estimated_cost_usd: number;
  created_at: string;
}

