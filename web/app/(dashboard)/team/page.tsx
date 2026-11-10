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
import { useAuth } from '@/contexts/auth-context';
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

  const { role } = useAuth();
  const isManagerOrOwner = role === 'owner' || role === 'manager';

  const fetchTeamData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (isManagerOrOwner) {
        const [membersRes, invitesRes] = await Promise.all([
          apiClient<TeamMemberResponse[]>('/api/team/members'),
          apiClient<InviteResponse[]>('/api/team/invites'),
        ]);
        setMembers(membersRes);
        setInvites(invitesRes);
      } else {
        const membersRes = await apiClient<TeamMemberResponse[]>('/api/team/members');
        setMembers(membersRes);
        setInvites([]);
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load team data.');
    } finally {
      setLoading(false);
    }
  }, [isManagerOrOwner]);

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

  const getRoleBadge = (userRole: string) => {
    switch (userRole.toLowerCase()) {
      case 'owner':
        return (
          <span className="brutal-badge bg-[#fef9c3] text-amber-950">
            <Shield className="w-3 h-3 mr-1" /> Owner
          </span>
        );
      case 'manager':
        return (
          <span className="brutal-badge bg-[#f3e8ff] text-purple-950">
            <Shield className="w-3 h-3 mr-1" /> Manager
          </span>
        );
      default:
        return (
          <span className="brutal-badge bg-[#dbeafe] text-blue-950">
            Staff
          </span>
        );
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-2xl font-black uppercase tracking-tight text-black">
              Team & Access Controls
            </h2>
            <span className="bg-[#a3e635] text-black text-[10px] font-black uppercase px-2 py-0.5 rounded brutal-border brutal-shadow-xs">
              RBAC Guarded
            </span>
          </div>
          <p className="text-xs font-semibold text-neutral-600">
            Manage your team, invite colleagues with role-based access, and review security audit logs.
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          {activeTab === 'members' && isManagerOrOwner && (
            <button
              onClick={() => setShowInviteModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-500 text-xs font-black uppercase tracking-wider brutal-border brutal-shadow brutal-shadow-hover"
            >
              <UserPlus className="w-4 h-4" /> Invite Member
            </button>
          )}
          <button
            onClick={() => fetchTeamData()}
            disabled={loading}
            className="p-2.5 bg-white brutal-border rounded-xl brutal-shadow-xs brutal-shadow-hover text-black"
            title="Refresh team members"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-600' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-rose-100 border-2 border-black rounded-xl text-rose-950 text-xs font-black uppercase flex items-center justify-between brutal-shadow-xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            onClick={() => fetchTeamData()}
            className="text-xs font-black underline hover:text-black"
          >
            Retry
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white p-2 rounded-2xl brutal-border-3 brutal-shadow inline-flex gap-2">
        <button
          onClick={() => setActiveTab('members')}
          className={`py-2 px-4 rounded-xl font-black text-xs uppercase tracking-wider flex items-center gap-2 transition-all ${
            activeTab === 'members'
              ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
              : 'text-neutral-600 hover:text-black hover:bg-neutral-100'
          }`}
        >
          <Users className="w-4 h-4" />
          Active Team & Invites ({members.length})
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={`py-2 px-4 rounded-xl font-black text-xs uppercase tracking-wider flex items-center gap-2 transition-all ${
            activeTab === 'audit'
              ? 'bg-[#ffe600] text-black brutal-border brutal-shadow-xs'
              : 'text-neutral-600 hover:text-black hover:bg-neutral-100'
          }`}
        >
          <History className="w-4 h-4" />
          Audit Trail
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'members' ? (
        <div className="space-y-6">
          {/* Active Members Table */}
          <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
            <div className="p-4 sm:p-5 border-b-2 border-black flex items-center justify-between bg-neutral-50">
              <div>
                <h3 className="text-base font-black uppercase text-black">Current Members</h3>
                <p className="text-xs font-semibold text-neutral-600">Users authorized to access this organization&apos;s dashboard</p>
              </div>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs font-bold text-neutral-500 animate-pulse">
                Loading team members...
              </div>
            ) : members.length === 0 ? (
              <div className="p-8 text-center text-xs font-bold text-neutral-500">No active members found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-neutral-100 border-b-2 border-black text-xs font-black uppercase tracking-wider text-black">
                    <tr>
                      <th className="py-3.5 px-5">Member</th>
                      <th className="py-3.5 px-5">Role</th>
                      <th className="py-3.5 px-5">Joined</th>
                      <th className="py-3.5 px-5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y-2 divide-black/10">
                    {members.map((member) => (
                      <tr key={member.user_id} className="hover:bg-amber-50/40 transition-colors">
                        <td className="py-4 px-5">
                          <div className="font-black text-black">{member.name}</div>
                          <div className="text-xs font-mono text-neutral-600 flex items-center gap-1 mt-0.5">
                            <Mail className="w-3 h-3 text-neutral-400" />
                            {member.email}
                          </div>
                        </td>
                        <td className="py-4 px-5">{getRoleBadge(member.role)}</td>
                        <td className="py-4 px-5 text-xs font-mono font-bold text-neutral-600">
                          {new Date(member.joined_at).toLocaleDateString([], {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </td>
                        <td className="py-4 px-5 text-right">
                          {isManagerOrOwner ? (
                            <div className="flex items-center justify-end gap-2">
                              <button
                                onClick={() => setEditingMember(member)}
                                className="p-1.5 bg-white brutal-border rounded-lg text-neutral-700 hover:text-black brutal-shadow-xs"
                                title="Edit role"
                              >
                                <Edit2 className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setRemovingMember(member)}
                                className="p-1.5 bg-rose-50 brutal-border rounded-lg text-rose-700 hover:text-rose-900 brutal-shadow-xs"
                                title="Remove member"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : (
                            <span className="text-neutral-400 text-xs font-bold uppercase">&mdash;</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Pending Invitations Section (Manager / Owner only) */}
          {isManagerOrOwner && (
            <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg overflow-hidden">
              <div className="p-4 sm:p-5 border-b-2 border-black flex items-center justify-between bg-[#fef9c3]">
                <div>
                  <h3 className="text-base font-black uppercase text-black">Pending Invitations</h3>
                  <p className="text-xs font-semibold text-neutral-700">Invited teammates who have not completed signup</p>
                </div>
              </div>

              {invites.length === 0 ? (
                <div className="p-8 text-center text-xs font-bold text-neutral-500">
                  No pending invitations.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-neutral-100 border-b-2 border-black text-xs font-black uppercase tracking-wider text-black">
                      <tr>
                        <th className="py-3.5 px-5">Email</th>
                        <th className="py-3.5 px-5">Role Assigned</th>
                        <th className="py-3.5 px-5">Expires</th>
                        <th className="py-3.5 px-5 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y-2 divide-black/10">
                      {invites.map((invite) => (
                        <tr key={invite.id} className="hover:bg-amber-50/40 transition-colors">
                          <td className="py-4 px-5 font-bold font-mono text-black">{invite.email}</td>
                          <td className="py-4 px-5">{getRoleBadge(invite.role)}</td>
                          <td className="py-4 px-5 text-xs font-mono font-bold text-neutral-600">
                            {new Date(invite.expires_at).toLocaleDateString([], {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </td>
                          <td className="py-4 px-5 text-right">
                            <button
                              onClick={() => handleRevokeInvite(invite.id)}
                              disabled={revokingInviteId === invite.id}
                              className="px-2.5 py-1 text-xs font-black uppercase text-rose-700 bg-rose-50 brutal-border brutal-shadow-xs rounded-lg hover:bg-rose-100 disabled:opacity-50"
                            >
                              Revoke
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      ) : (
        /* Audit Log Trail */
        <div className="bg-white rounded-2xl brutal-border-3 brutal-shadow-lg p-6">
          <AuditLogViewer />
        </div>
      )}

      {/* Modals */}
      <InviteMemberModal
        isOpen={showInviteModal}
        onClose={() => setShowInviteModal(false)}
        onSuccess={() => fetchTeamData()}
      />

      {editingMember && (
        <EditRoleModal
          isOpen={Boolean(editingMember)}
          userId={editingMember.user_id}
          userName={editingMember.name}
          currentRole={editingMember.role}
          onClose={() => setEditingMember(null)}
          onSuccess={() => {
            setEditingMember(null);
            fetchTeamData();
          }}
        />
      )}

      {removingMember && (
        <RemoveMemberModal
          isOpen={Boolean(removingMember)}
          userId={removingMember.user_id}
          userName={removingMember.name}
          onClose={() => setRemovingMember(null)}
          onSuccess={() => {
            setRemovingMember(null);
            fetchTeamData();
          }}
        />
      )}
    </div>
  );
}
