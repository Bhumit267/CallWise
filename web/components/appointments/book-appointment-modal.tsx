'use client';

import React, { useState, useEffect } from 'react';
import { apiClient } from '@/lib/api';
import { ServiceItem } from '@/types/api';
import { X, Calendar, Loader2, Clock, User, Phone, Mail, Sparkles } from 'lucide-react';

interface BookAppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function BookAppointmentModal({
  isOpen,
  onClose,
  onSuccess,
}: BookAppointmentModalProps) {
  const [services, setServices] = useState<ServiceItem[]>([]);
  const [selectedServiceId, setSelectedServiceId] = useState('');
  const [customerName, setCustomerName] = useState('');
  const [customerPhone, setCustomerPhone] = useState('');
  const [customerEmail, setCustomerEmail] = useState('');
  const [startTime, setStartTime] = useState('');
  const [loading, setLoading] = useState(false);
  const [fetchingServices, setFetchingServices] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen) return;

    const fetchServices = async () => {
      setFetchingServices(true);
      try {
        const data = await apiClient<ServiceItem[]>('/api/settings/services');
        setServices(data || []);
        if (data.length > 0) {
          setSelectedServiceId(data[0].id);
        }
      } catch (err) {
        // Fallback or empty
      } finally {
        setFetchingServices(false);
      }
    };

    fetchServices();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedServiceId || !customerName || !customerPhone || !startTime) {
      setError('Please fill in all required fields.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await apiClient('/api/appointments', {
        method: 'POST',
        body: JSON.stringify({
          service_id: selectedServiceId,
          customer_name: customerName.trim(),
          customer_phone: customerPhone.trim(),
          customer_email: customerEmail.trim() || undefined,
          start_time: new Date(startTime).toISOString(),
        }),
      });

      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to book appointment. Time slot may be unavailable.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="w-full max-w-lg bg-white brutal-border-3 brutal-shadow-xl overflow-hidden">
        {/* Header */}
        <div className="h-16 px-6 border-b-3 border-black flex items-center justify-between bg-[#ffe600]">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 bg-black text-[#ffe600] brutal-border flex items-center justify-center">
              <Calendar className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-black text-black uppercase tracking-tight">Book Appointment</h3>
              <p className="text-xs font-bold text-slate-800">Direct Frontdesk Scheduling</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 bg-black text-white brutal-border flex items-center justify-center hover:bg-slate-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-[#ff5a5a] text-black text-xs font-black brutal-border">
              {error}
            </div>
          )}

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Select Offering / Service <span className="text-red-600">*</span>
            </label>
            {fetchingServices ? (
              <div className="py-2 text-xs font-black uppercase text-slate-500 flex items-center">
                <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5 text-black" />
                Loading services...
              </div>
            ) : (
              <select
                required
                value={selectedServiceId}
                onChange={(e) => setSelectedServiceId(e.target.value)}
                className="w-full px-3 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
              >
                {services.map((svc) => (
                  <option key={svc.id} value={svc.id}>
                    {svc.name} ({svc.duration_minutes} min{svc.price ? ` - $${svc.price}` : ''})
                  </option>
                ))}
              </select>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-black uppercase text-black mb-1.5">
                Customer Name <span className="text-red-600">*</span>
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-black absolute left-3 top-3" />
                <input
                  type="text"
                  required
                  value={customerName}
                  onChange={(e) => setCustomerName(e.target.value)}
                  placeholder="John Smith"
                  className="w-full pl-9 pr-3 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-black uppercase text-black mb-1.5">
                Customer Phone <span className="text-red-600">*</span>
              </label>
              <div className="relative">
                <Phone className="w-4 h-4 text-black absolute left-3 top-3" />
                <input
                  type="tel"
                  required
                  value={customerPhone}
                  onChange={(e) => setCustomerPhone(e.target.value)}
                  placeholder="+1 (555) 234-5678"
                  className="w-full pl-9 pr-3 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
                />
              </div>
            </div>
          </div>

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Customer Email <span className="text-slate-500 font-bold">(Optional)</span>
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 text-black absolute left-3 top-3" />
              <input
                type="email"
                value={customerEmail}
                onChange={(e) => setCustomerEmail(e.target.value)}
                placeholder="john@example.com"
                className="w-full pl-9 pr-3 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-black uppercase text-black mb-1.5">
              Date & Start Time <span className="text-red-600">*</span>
            </label>
            <input
              type="datetime-local"
              required
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className="w-full px-3 py-2.5 bg-[#fbfaf6] brutal-border font-bold text-sm focus:bg-white focus:outline-hidden"
            />
          </div>

          <div className="flex items-center justify-end space-x-3 pt-4 border-t-2 border-black">
            <button
              type="button"
              onClick={onClose}
              className="bg-white text-black font-black uppercase text-xs px-4 py-2.5 brutal-border brutal-shadow-hover"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="bg-[#10b981] text-black font-black uppercase text-xs px-5 py-2.5 brutal-border brutal-shadow-hover flex items-center disabled:opacity-50"
            >
              {loading && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Confirm Booking
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
