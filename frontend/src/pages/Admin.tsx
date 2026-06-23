import React, { useState, useEffect } from 'react';
import { api } from '../utils/api';
import { useAuth } from '../context/AuthContext';
import {
  Users,
  Shield,
  Trash2,
  AlertTriangle,
  Plus,
  Loader2,
  Mail,
  CheckCircle,
  Bell,
} from 'lucide-react';

interface User {
  user_id: string;
  email: string;
  role: string;
  created_at: string;
}

interface Recipient {
  recipient_id: string;
  email: string;
  subscribed_topics: string[];
  is_active: boolean;
  created_at: string;
}

export const Admin: React.FC = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [recipients, setRecipients] = useState<Recipient[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add Alert Recipient Form State
  const [newEmail, setNewEmail] = useState('');
  const [selectedTopics, setSelectedTopics] = useState<string[]>([]);
  const [submittingRecipient, setSubmittingRecipient] = useState(false);

  // Loading indicator for actions
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  const availableTopics = [
    { id: 'job-completed', label: 'Job Completed' },
    { id: 'job-failed', label: 'Job Failed' },
    { id: 'fallback-requested', label: 'Fallback Requested' },
    { id: 'dead-letter', label: 'Dead Letter Queue Alert' },
  ];

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const fetchAdminData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [usersList, recipientsList] = await Promise.all([
        api.get('/auth/users'),
        api.get('/recipients'),
      ]);
      setUsers(usersList || []);
      setRecipients(recipientsList || []);
    } catch (err: any) {
      setError(err.message || 'Failed to load administrative settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  const handleUpdateRole = async (userId: string, currentRole: string, targetRole: string) => {
    if (currentRole === 'OWNER') {
      showNotification('Cannot modify the Owner account role.', 'error');
      return;
    }
    if (userId === currentUser?.user_id) {
      showNotification('You cannot change your own role.', 'error');
      return;
    }

    setActioningId(userId);
    try {
      await api.patch(`/auth/users/${userId}/role`, { role: targetRole });
      showNotification('User role updated successfully.');
      fetchAdminData();
    } catch (err: any) {
      showNotification(err.message || 'Failed to update role', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const handleDeleteUser = async (userId: string, userRole: string, email: string) => {
    if (userRole === 'OWNER') {
      showNotification('Cannot delete the Owner account.', 'error');
      return;
    }
    if (userId === currentUser?.user_id) {
      showNotification('You cannot delete your own account.', 'error');
      return;
    }

    if (!confirm(`Are you sure you want to permanently delete user: ${email}?`)) return;

    setActioningId(userId);
    try {
      await api.delete(`/auth/users/${userId}`);
      showNotification(`Deleted user ${email}`);
      fetchAdminData();
    } catch (err: any) {
      showNotification(err.message || 'Failed to delete user', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const handleAddRecipient = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEmail) return;

    setSubmittingRecipient(true);
    try {
      await api.post('/recipients', {
        email: newEmail,
        subscribed_topics: selectedTopics,
      });

      showNotification('Notification subscriber added successfully.');
      setNewEmail('');
      setSelectedTopics([]);
      fetchAdminData();
    } catch (err: any) {
      showNotification(err.message || 'Failed to add alert subscriber', 'error');
    } finally {
      setSubmittingRecipient(false);
    }
  };

  const handleToggleTopicSubscription = async (recipient: Recipient, topicId: string) => {
    const isSubscribed = recipient.subscribed_topics.includes(topicId);
    let updatedTopics = [...recipient.subscribed_topics];

    if (isSubscribed) {
      updatedTopics = updatedTopics.filter((t) => t !== topicId);
    } else {
      updatedTopics.push(topicId);
    }

    setActioningId(recipient.recipient_id);
    try {
      await api.patch(`/recipients/${recipient.recipient_id}`, {
        subscribed_topics: updatedTopics,
      });
      showNotification(`Updated alert subscriptions for ${recipient.email}`);
      fetchAdminData();
    } catch (err: any) {
      showNotification(err.message || 'Failed to update subscription', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const handleDeleteRecipient = async (recipientId: string, email: string) => {
    if (!confirm(`Remove ${email} from notification lists entirely?`)) return;

    setActioningId(recipientId);
    try {
      await api.delete(`/recipients/${recipientId}`);
      showNotification(`Removed alert recipient ${email}`);
      fetchAdminData();
    } catch (err: any) {
      showNotification(err.message || 'Failed to delete alert recipient', 'error');
    } finally {
      setActioningId(null);
    }
  };

  const handleTopicSelectionToggle = (topicId: string) => {
    if (selectedTopics.includes(topicId)) {
      setSelectedTopics(selectedTopics.filter((t) => t !== topicId));
    } else {
      setSelectedTopics([...selectedTopics, topicId]);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* Page Header */}
      <div>
        <h2 style={{ fontSize: '22px', fontWeight: 600, color: '#fafafa', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Shield size={22} color="#0ea5e9" />
          Admin Console
        </h2>
        <p style={{ color: '#a1a1aa', fontSize: '14px', marginTop: '4px' }}>
          Configure user authorization access levels and notification subscription distribution groups.
        </p>
      </div>

      {notification && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            backgroundColor: notification.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${notification.type === 'success' ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
            borderRadius: '6px',
            padding: '12px 16px',
            fontSize: '14px',
            color: notification.type === 'success' ? '#10b981' : '#ef4444',
          }}
        >
          {notification.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          <span>{notification.message}</span>
        </div>
      )}

      {loading && users.length === 0 ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0', color: '#a1a1aa' }}>
          <Loader2 className="animate-spin" size={32} />
          <span style={{ marginLeft: '12px', fontSize: '15px' }}>Loading administrative catalog...</span>
        </div>
      ) : error ? (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            backgroundColor: 'rgba(239, 68, 68, 0.05)',
            border: '1px solid rgba(239, 68, 68, 0.1)',
            color: '#ef4444',
            padding: '16px',
            borderRadius: '6px',
          }}
        >
          <AlertTriangle size={20} />
          <span>{error}</span>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '32px' }}>
          
          {/* Section 1: User Management */}
          <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', padding: '24px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={18} color="#0ea5e9" />
              User Authorization Directory
            </h3>
            <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
              Control user privileges. Owner accounts have absolute permission defaults.
            </p>

            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ backgroundColor: '#27272a', color: '#fafafa', borderBottom: '1px solid #27272a' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>User Email</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>User UUID</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Created At</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600 }}>Role Context</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => {
                  const isOwner = u.role === 'OWNER';
                  const isSelf = u.user_id === currentUser?.user_id;
                  const disabled = isOwner || isSelf || actioningId !== null;

                  return (
                    <tr key={u.user_id} style={{ borderBottom: '1px solid #27272a' }}>
                      <td style={{ padding: '14px 16px', color: '#fafafa', fontWeight: 500 }}>
                        {u.email}
                        {isSelf && <span style={{ marginLeft: '6px', fontSize: '10px', color: '#0ea5e9', backgroundColor: 'rgba(14, 165, 233, 0.1)', padding: '1px 6px', borderRadius: '4px' }}>You</span>}
                      </td>
                      <td style={{ padding: '14px 16px', color: '#71717a', fontFamily: 'monospace', fontSize: '11px' }}>
                        {u.user_id}
                      </td>
                      <td style={{ padding: '14px 16px', color: '#a1a1aa' }}>
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        {isOwner ? (
                          <span style={{ fontSize: '11px', fontWeight: 700, backgroundColor: 'rgba(14, 165, 233, 0.1)', color: '#0ea5e9', padding: '2px 8px', borderRadius: '4px' }}>
                            OWNER
                          </span>
                        ) : (
                          <select
                            value={u.role}
                            disabled={disabled}
                            onChange={(e) => handleUpdateRole(u.user_id, u.role, e.target.value)}
                            style={{
                              backgroundColor: '#09090b',
                              border: '1px solid #27272a',
                              borderRadius: '4px',
                              color: '#fafafa',
                              padding: '2px 8px',
                              fontSize: '12px',
                              cursor: disabled ? 'not-allowed' : 'pointer',
                            }}
                          >
                            <option value="USER">USER</option>
                            <option value="ADMIN">ADMIN</option>
                          </select>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        {!isOwner && !isSelf && (
                          <button
                            onClick={() => handleDeleteUser(u.user_id, u.role, u.email)}
                            disabled={disabled}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#ef4444',
                              cursor: disabled ? 'not-allowed' : 'pointer',
                              padding: '6px',
                              borderRadius: '4px',
                              opacity: disabled ? 0.3 : 1,
                            }}
                            title="Delete User"
                            onMouseEnter={(e) => { if (!disabled) e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                          >
                            {actioningId === u.user_id ? (
                              <Loader2 className="animate-spin" size={14} />
                            ) : (
                              <Trash2 size={14} />
                            )}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Section 2: Alert Channels Subscriptions */}
          <div style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '28px', alignItems: 'flex-start' }}>
            
            {/* List alert recipients */}
            <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', padding: '24px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#fafafa', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Bell size={18} color="#f59e0b" />
                Email Notification Distribution Matrix
              </h3>
              <p style={{ color: '#a1a1aa', fontSize: '13px', marginBottom: '20px' }}>
                Configure which notification channels alert recipients receive.
              </p>

              {recipients.length === 0 ? (
                <div style={{ border: '1px dashed #27272a', borderRadius: '6px', padding: '30px 10px', textAlign: 'center', color: '#a1a1aa' }}>
                  No notification alert recipients registered yet.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid #27272a', color: '#71717a' }}>
                        <th style={{ padding: '8px 12px', fontWeight: 600 }}>Recipient Email</th>
                        {availableTopics.map((t) => (
                          <th key={t.id} style={{ padding: '8px 12px', fontWeight: 600, textAlign: 'center' }}>
                            {t.label.split(' ')[0]}
                          </th>
                        ))}
                        <th style={{ padding: '8px 12px', fontWeight: 600, textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recipients.map((r) => (
                        <tr key={r.recipient_id} style={{ borderBottom: '1px solid #27272a' }}>
                          <td style={{ padding: '12px', color: '#fafafa', fontWeight: 500 }}>
                            {r.email}
                          </td>
                          {availableTopics.map((t) => {
                            const isSub = r.subscribed_topics.includes(t.id);
                            return (
                              <td key={t.id} style={{ padding: '12px', textAlign: 'center' }}>
                                <input
                                  type="checkbox"
                                  checked={isSub}
                                  disabled={actioningId !== null}
                                  onChange={() => handleToggleTopicSubscription(r, t.id)}
                                  style={{ cursor: 'pointer' }}
                                />
                              </td>
                            );
                          })}
                          <td style={{ padding: '12px', textAlign: 'right' }}>
                            <button
                              onClick={() => handleDeleteRecipient(r.recipient_id, r.email)}
                              disabled={actioningId !== null}
                              style={{
                                background: 'none',
                                border: 'none',
                                color: '#ef4444',
                                cursor: 'pointer',
                                padding: '4px',
                                borderRadius: '4px',
                              }}
                              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)')}
                              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                            >
                              <Trash2 size={12} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Register alert recipient */}
            <div style={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px', padding: '24px' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 600, color: '#fafafa', marginBottom: '4px' }}>
                Add Alert Recipient
              </h3>
              <p style={{ color: '#a1a1aa', fontSize: '12px', marginBottom: '16px' }}>
                Register a new email and check channels to alert.
              </p>

              <form onSubmit={handleAddRecipient} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <label htmlFor="rec-email">Recipient Email Address *</label>
                  <div style={{ position: 'relative' }}>
                    <Mail
                      size={14}
                      color="#71717a"
                      style={{
                        position: 'absolute',
                        left: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                      }}
                    />
                    <input
                      id="rec-email"
                      type="email"
                      placeholder="alerts@company.com"
                      value={newEmail}
                      onChange={(e) => setNewEmail(e.target.value)}
                      required
                      style={{ paddingLeft: '32px', fontSize: '13px', height: '36px' }}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 600, color: '#71717a' }}>Select Alert Channels</span>
                  {availableTopics.map((topic) => {
                    const isSelected = selectedTopics.includes(topic.id);
                    return (
                      <label
                        key={topic.id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          fontSize: '12px',
                          color: '#fafafa',
                          cursor: 'pointer',
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleTopicSelectionToggle(topic.id)}
                        />
                        <span>{topic.label}</span>
                      </label>
                    );
                  })}
                </div>

                <button
                  type="submit"
                  disabled={submittingRecipient || !newEmail}
                  className="btn"
                  style={{
                    width: '100%',
                    height: '36px',
                    fontSize: '13px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    marginTop: '4px',
                  }}
                >
                  {submittingRecipient ? (
                    <Loader2 className="animate-spin" size={14} />
                  ) : (
                    <>
                      <Plus size={14} />
                      <span>Subscribe Email</span>
                    </>
                  )}
                </button>
              </form>
            </div>

          </div>

        </div>
      )}
    </div>
  );
};
