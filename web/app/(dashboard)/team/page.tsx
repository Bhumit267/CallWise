'use client';

import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  UserPlus,
  Shield,
  Clock,
  History,
  Trash2,
  Edit2,
  AlertCircle,
  RefreshCw,
  Mail,
} from 'lucide-react';
import { apiClient } from '@/lib/api';
import { TeamMemberResponse, InviteResponse } from '@/types/api';
import { InviteMemberModal } from '@/components/team/invite-member-modal';
import { EditRoleModal } from '@/components/team/edit-role-modal';
import { RemoveMemberModal } from '@/components/team/remove-member-modal';
import { AuditLogViewer } from '@/components/team/audit-log-viewer';

export default function TeamPage() {
  const [activeTab, setActiveTab] = useState<'members' | 'audit'>('members');
  const [members, setMembers] = useState<TeamMemberResponse[]>([]);
  const [invites, setInvites] = useState<InviteResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [showInviteModal, setShowInviteModal] = useState<boolean>(false);
  const [editingMember, setEditingMember] = useState<TeamMemberResponse | null>(null);
  const [removingMember, setRemovingMember] = useState<TeamMemberResponse | null>(null);

  // Revoking invite state
  const [revokingInviteId, setRevokingInviteId] = useState<string | null>(null);

  const fetchTeamData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [membersRes, invitesRes] = await Promise.all([
        apiClient<TeamMemberResponse[]>('/api/team/members'),
        apiClient<InviteResponse[]>('/api/team/invites'),
      ]);
      setMembers(membersRes);
      setInvites(invitesRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to load team data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTeamData();
  }, [fetchTeamData]);

  const handleRevokeInvite = async (inviteId: string) => {
    if (!confirm('Are you sure you want to cancel and revoke this invitation?')) return;
    setRevokingInviteId(inviteId);
    try {
      await apiClient(`/api/team/invites/${inviteId}`, { method: 'DELETE' });
      setInvites((prev) => prev.filter((i) => i.id !== inviteId));
    } catch (err: any) {
      alert(err?.message || 'Failed to revoke invite.');
    } finally {
      setRevokingInviteId(null);
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role.toLowerCase()) {
      case 'owner':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-100 text-purple-800 border border-purple-200">
            <Shield className="w-3 h-3" />
            Owner
          </span>
        );
      case 'manager':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            <Shield className="w-3 h-3" />
            Manager
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            Staff
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900">Team Management & Access Controls</h2>
          <p className="text-sm text-slate-500">
            Manage your team, invite colleagues with role-based access, and review security audit logs.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {activeTab === 'members' && (
            <button
              onClick={() => setShowInviteModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium transition-colors shadow-xs"
            >
              <UserPlus className="w-4 h-4" />
              Invite Member
            </button>
          )}
          <button
            onClick={() => fetchTeamData()}
            disabled={loading}
            className="p-2 border border-slate-200 bg-white rounded-lg hover:bg-slate-50 text-slate-600 transition-colors"
            title="Refresh team members"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchTeamData()}
            className="text-xs font-semibold underline hover:text-red-900"
          >
            Retry
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('members')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
              activeTab === 'members'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Users className="w-4 h-4" />
            Active Team & Invites
            <span className="ml-1 px-2 py-0.5 text-xs rounded-full bg-slate-100 text-slate-600">
              {members.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab('audit')}
            className={`py-3 px-1 border-b-2 font-medium text-sm flex items-center gap-2 transition-colors ${
              activeTab === 'audit'
                ? 'border-blue-600 text-blue-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <History className="w-4 h-4" />
            Audit Trail
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'members' ? (
        <div className="space-y-6">
          {/* Active Members Table */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Current Members</h3>
                <p className="text-xs text-slate-500">Users authorized to access this organization’s dashboard</p>
              </div>
            </div>

            {loading ? (
              <div className="p-8 text-center text-sm text-slate-400 animate-pulse">
                Loading team members...
              </div>
            ) : members.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-400">No active members found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50/75 border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Member</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Joined</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {members.map((member) => (
                      <tr key={member.user_id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="py-3.5 px-4">
                          <div className="font-medium text-slate-900">{member.name}</div>
                          <div className="text-xs text-slate-500 flex items-center gap-1 mt-0.5">
                            <Mail className="w-3 h-3" />
                            {member.email}
                          </div>
                        </td>
                        <td className="py-3.5 px-4">{getRoleBadge(member.role)}</td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          {new Date(member.joined_at).toLocaleDateString(undefined, {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <button
                              onClick={() => setEditingMember(member)}
                              className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                              title="Edit Role"
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setRemovingMember(member)}
                              className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                              title="Remove Member"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Pending Invitations Section */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-900">Pending Invitations</h3>
                <p className="text-xs text-slate-500">Invited users who haven't yet accepted</p>
              </div>
            </div>

            {loading ? (
              <div className="p-8 text-center text-sm text-slate-400 animate-pulse">
                Loading invites...
              </div>
            ) : invites.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-400">
                No pending invitations. All invited members have registered or expired.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-600">
                  <thead className="bg-slate-50/75 border-b border-slate-100 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    <tr>
                      <th className="py-3 px-4">Invited Email</th>
                      <th className="py-3 px-4">Role</th>
                      <th className="py-3 px-4">Expires</th>
                      <th className="py-3 px-4 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {invites.map((invite) => (
                      <tr key={invite.id} className="hover:bg-slate-50/50 transition-colors">
                        <td className="py-3.5 px-4 font-medium text-slate-900">{invite.email}</td>
                        <td className="py-3.5 px-4">{getRoleBadge(invite.role)}</td>
                        <td className="py-3.5 px-4 text-xs text-slate-500">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-slate-400" />
                            {new Date(invite.expires_at).toLocaleString(undefined, {
                              month: 'short',
                              day: 'numeric',
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => handleRevokeInvite(invite.id)}
                            disabled={revokingInviteId === invite.id}
                            className="text-xs font-semibold text-red-600 hover:text-red-800 disabled:opacity-50"
                          >
                            {revokingInviteId === invite.id ? 'Revoking...' : 'Revoke'}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Audit Log Viewer Tab */
        <AuditLogViewer />
      )}

      {/* Modals */}
      {showInviteModal && (
        <InviteMemberModal
          isOpen={showInviteModal}
          onClose={() => setShowInviteModal(false)}
          onSuccess={() => fetchTeamData()}
        />
      )}

      {editingMember && (
        <EditRoleModal
          isOpen={!!editingMember}
          userId={editingMember.user_id}
          userName={editingMember.name}
          currentRole={editingMember.role}
          onClose={() => setEditingMember(null)}
          onSuccess={() => fetchTeamData()}
        />
      )}

      {removingMember && (
        <RemoveMemberModal
          isOpen={!!removingMember}
          userId={removingMember.user_id}
          userName={removingMember.name}
          onClose={() => setRemovingMember(null)}
          onSuccess={() => fetchTeamData()}
        />
      )}
    </div>
  );
}
