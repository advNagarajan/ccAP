import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../utils/api';
import {
  LogOut,
  User,
  Server,
  Database,
  Play,
  FileCode,
  ShieldCheck,
  Shield,
  History,
  AlertTriangle,
  Bell,
  X,
  CheckCircle,
  Loader2,
  Sliders,
  KeyRound,
} from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const AppShell: React.FC<AppShellProps> = ({ children, activeTab, setActiveTab }) => {
  const { user, logout, isAdmin } = useAuth();

  const [isPrefModalOpen, setIsPrefModalOpen] = useState(false);
  const [optIn, setOptIn] = useState(false);
  const [subscribedTopics, setSubscribedTopics] = useState<string[]>([]);
  const [recipientId, setRecipientId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Tab control in preferences modal
  const [activeModalTab, setActiveModalTab] = useState<'notifications' | 'security'>('notifications');

  // Change Password Form State
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isPasswordChanging, setIsPasswordChanging] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!isPrefModalOpen || !user) return;

    const fetchPreferences = async () => {
      setIsLoading(true);
      try {
        const recipientsList = await api.get('/recipients');
        const userRec = recipientsList?.find((r: any) => r.email.toLowerCase() === user.email.toLowerCase());
        if (userRec) {
          setRecipientId(userRec.recipient_id);
          setSubscribedTopics(userRec.subscribed_topics || []);
          setOptIn(userRec.is_active);
        } else {
          setRecipientId(null);
          setSubscribedTopics(['job-completed', 'job-failed', 'fallback-requested', 'dead-letter', 'quality-check-completed']);
          setOptIn(false);
        }
      } catch (err) {
        console.error('Failed to fetch user notification preferences', err);
      } finally {
        setIsLoading(false);
      }
    };

    fetchPreferences();
  }, [isPrefModalOpen, user]);

  const handleSavePreferences = async () => {
    if (!user) return;
    setIsSaving(true);
    try {
      if (recipientId) {
        await api.patch(`/recipients/${recipientId}`, {
          subscribed_topics: optIn ? subscribedTopics : [],
          is_active: optIn,
        });
      } else {
        await api.post('/recipients', {
          email: user.email,
          subscribed_topics: optIn ? subscribedTopics : [],
          is_active: optIn,
        });
      }
      setIsPrefModalOpen(false);
    } catch (err) {
      console.error('Failed to save notification preferences', err);
      alert('Failed to save notification preferences.');
    } finally {
      setIsSaving(false);
    }
  };

  useEffect(() => {
    if (!isPrefModalOpen) {
      setActiveModalTab('notifications');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordError(null);
      setPasswordSuccess(null);
    }
  }, [isPrefModalOpen]);

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentPassword || !newPassword || !confirmPassword) return;

    if (newPassword !== confirmPassword) {
      setPasswordError("New passwords do not match.");
      return;
    }

    if (newPassword.length < 6) {
      setPasswordError("New password must be at least 6 characters long.");
      return;
    }

    setIsPasswordChanging(true);
    setPasswordError(null);
    setPasswordSuccess(null);

    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });

      setPasswordSuccess("Password changed successfully!");
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setPasswordError(err.message || "Failed to change password.");
    } finally {
      setIsPasswordChanging(false);
    }
  };

  const menuItems = [
    { id: 'sources', label: 'Registered Sources', icon: Server },
    { id: 'targets', label: 'Target Catalog', icon: Database },
    { id: 'jobs', label: 'Pipeline Jobs', icon: Play },
    { id: 'quality-jobs', label: 'Data Quality Jobs', icon: CheckCircle },
    { id: 'configurations', label: 'Configurations', icon: Sliders },
    { id: 'dlq', label: 'Dead Letter Queue', icon: AlertTriangle },
    { id: 'fallback', label: 'Fallback Approvals', icon: FileCode },
  ];

  const adminMenuItems = [
    { id: 'admin', label: 'Admin Console', icon: ShieldCheck },
    { id: 'audit', label: 'Audit Logs', icon: History },
  ];

  return (
    <div className="app-container">
      {/* Sidebar */}
      <aside
        style={{
          width: '260px',
          backgroundColor: '#18181b',
          borderRight: '1px solid #27272a',
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          position: 'sticky',
          top: 0,
          height: '100vh',
        }}
      >
        <div
          style={{
            padding: '24px 20px',
            borderBottom: '1px solid #27272a',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
          }}
        >
          <div
            style={{
              width: '32px',
              height: '32px',
              backgroundColor: 'rgba(14, 165, 233, 0.1)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Shield size={18} color="#0ea5e9" />
          </div>
          <div>
            <h1 style={{ fontSize: '15px', fontWeight: 600 }}>Data Intelligence</h1>
            <span style={{ fontSize: '11px', color: '#71717a' }}>Control Plane</span>
          </div>
        </div>

        {/* Navigation Items */}
        <nav
          style={{
            flex: 1,
            padding: '20px 12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            overflowY: 'auto',
          }}
        >
          {menuItems.map((item) => {
            const Icon = item.icon;
            const active = activeTab === item.id || (item.id === 'jobs' && activeTab.startsWith('review:'));
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: active ? '#27272a' : 'transparent',
                  color: active ? '#fafafa' : '#a1a1aa',
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontSize: '13px',
                  fontWeight: 500,
                  transition: 'background-color 0.15s',
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)';
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.backgroundColor = 'transparent';
                }}
              >
                <Icon size={16} style={{ flexShrink: 0 }} />
                <span>{item.label}</span>
              </button>
            );
          })}

          {isAdmin && (
            <>
              <div
                style={{
                  height: '1px',
                  backgroundColor: '#27272a',
                  margin: '12px 0',
                }}
              ></div>
              <span
                style={{
                  fontSize: '10px',
                  fontWeight: 600,
                  color: '#71717a',
                  paddingLeft: '12px',
                  marginBottom: '8px',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}
              >
                Admin Area
              </span>

              {adminMenuItems.map((item) => {
                const Icon = item.icon;
                const active = activeTab === item.id;
                return (
                  <button
                    key={item.id}
                    onClick={() => setActiveTab(item.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: active ? '#27272a' : 'transparent',
                      color: active ? '#fafafa' : '#a1a1aa',
                      cursor: 'pointer',
                      textAlign: 'left',
                      fontSize: '13px',
                      fontWeight: 500,
                      transition: 'background-color 0.15s',
                    }}
                    onMouseEnter={(e) => {
                      if (!active) e.currentTarget.style.backgroundColor = 'rgba(255,255,255,0.02)';
                    }}
                    onMouseLeave={(e) => {
                      if (!active) e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <Icon size={16} style={{ flexShrink: 0 }} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </>
          )}
        </nav>

        {/* User Footer */}
        {user && (
          <div
            style={{
              padding: '16px 20px',
              borderTop: '1px solid #27272a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '10px',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                minWidth: 0,
              }}
            >
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  backgroundColor: '#27272a',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <User size={16} color="#a1a1aa" />
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: '13px',
                    fontWeight: 500,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {user.email.split('@')[0]}
                </div>
                <div
                  style={{
                    fontSize: '10px',
                    color: '#71717a',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                  }}
                >
                  {user.role}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
              <button
                onClick={() => setIsPrefModalOpen(true)}
                title="Notification Preferences"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '6px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <Bell size={16} color="#a1a1aa" />
              </button>
              <button
                onClick={logout}
                title="Sign Out"
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '6px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <LogOut size={16} color="#a1a1aa" />
              </button>
            </div>
          </div>
        )}
      </aside>

      {/* Main Container */}
      <main className="main-content">
        {/* Header */}
        <header
          style={{
            height: '60px',
            borderBottom: '1px solid #27272a',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 32px',
            backgroundColor: '#18181b',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '13px', color: '#a1a1aa' }}>Organization /</span>
            <span style={{ fontSize: '13px', fontWeight: 500, color: '#fafafa' }}>Sutherland</span>
          </div>

          {user && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div
                style={{
                  backgroundColor:
                    user.role === 'OWNER'
                      ? 'rgba(14, 165, 233, 0.15)'
                      : user.role === 'ADMIN'
                      ? 'rgba(245, 158, 11, 0.15)'
                      : 'rgba(255, 255, 255, 0.05)',
                  color: user.role === 'OWNER' ? '#0ea5e9' : user.role === 'ADMIN' ? '#f59e0b' : '#a1a1aa',
                  border: `1px solid ${
                    user.role === 'OWNER'
                      ? 'rgba(14, 165, 233, 0.2)'
                      : user.role === 'ADMIN'
                      ? 'rgba(245, 158, 11, 0.2)'
                      : 'rgba(255, 255, 255, 0.1)'
                  }`,
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontWeight: 600,
                  fontSize: '10px',
                  textTransform: 'uppercase',
                }}
              >
                {user.role}
              </div>
              <span style={{ fontSize: '13px', color: '#a1a1aa' }}>{user.email}</span>
            </div>
          )}
        </header>

        {/* Content Body */}
        <div style={{ flex: 1, padding: '32px', overflowY: 'auto' }}>{children}</div>
      </main>

      {isPrefModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
          }}
        >
          <div
            style={{
              backgroundColor: '#18181b',
              border: '1px solid #27272a',
              borderRadius: '12px',
              padding: '30px',
              width: '450px',
              maxWidth: '90%',
              display: 'flex',
              flexDirection: 'column',
              gap: '20px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
            }}
          >
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <User size={20} color="#0ea5e9" />
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                  Account Settings
                </h3>
              </div>
              <button
                onClick={() => setIsPrefModalOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#71717a',
                  cursor: 'pointer',
                  padding: '4px',
                  borderRadius: '6px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#27272a')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <X size={16} />
              </button>
            </div>

            {/* Tab Navigation */}
            <div style={{ display: 'flex', borderBottom: '1px solid #27272a', marginBottom: '10px', gap: '8px' }}>
              <button
                type="button"
                onClick={() => setActiveModalTab('notifications')}
                style={{
                  padding: '8px 12px',
                  background: 'none',
                  border: 'none',
                  borderBottom: `2px solid ${activeModalTab === 'notifications' ? '#0ea5e9' : 'transparent'}`,
                  color: activeModalTab === 'notifications' ? '#fafafa' : '#71717a',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Bell size={14} />
                <span>Notifications</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveModalTab('security')}
                style={{
                  padding: '8px 12px',
                  background: 'none',
                  border: 'none',
                  borderBottom: `2px solid ${activeModalTab === 'security' ? '#0ea5e9' : 'transparent'}`,
                  color: activeModalTab === 'security' ? '#fafafa' : '#71717a',
                  cursor: 'pointer',
                  fontSize: '13px',
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <KeyRound size={14} />
                <span>Security</span>
              </button>
            </div>

            {/* Tab content */}
            {activeModalTab === 'notifications' ? (
              <>
                {/* Description */}
                <p style={{ color: '#a1a1aa', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
                  Select which notifications you would like to receive. Opt-in to start receiving alerts at <strong>{user?.email}</strong>.
                </p>

                {isLoading ? (
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px 0', color: '#a1a1aa', gap: '10px' }}>
                    <Loader2 className="animate-spin" size={20} />
                    <span style={{ fontSize: '13px' }}>Loading notification preferences...</span>
                  </div>
                ) : (
                  <>
                    {/* Opt-in Toggle */}
                    <label
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        cursor: 'pointer',
                        fontSize: '14px',
                        color: '#fafafa',
                        fontWeight: 500,
                        padding: '12px',
                        backgroundColor: 'rgba(255,255,255,0.02)',
                        border: '1px solid #27272a',
                        borderRadius: '6px',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={optIn}
                        onChange={(e) => setOptIn(e.target.checked)}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                      <span>Enable Email Alerts</span>
                    </label>

                    {/* Topics Checkboxes */}
                    {optIn && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', paddingLeft: '8px' }}>
                        <span style={{ fontSize: '12px', fontWeight: 600, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                          Subscribed Topics
                        </span>
                        {[
                          { id: 'job-completed', label: 'Job Completed' },
                          { id: 'job-failed', label: 'Job Failed' },
                          { id: 'fallback-requested', label: 'Fallback Requested' },
                          { id: 'dead-letter', label: 'Dead Letter Queue Alert' },
                          { id: 'quality-check-completed', label: 'Quality Check Completed' },
                        ].map((topic) => {
                          const checked = subscribedTopics.includes(topic.id);
                          return (
                            <label
                              key={topic.id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '10px',
                                fontSize: '13px',
                                color: '#a1a1aa',
                                cursor: 'pointer',
                              }}
                            >
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => {
                                  if (checked) {
                                    setSubscribedTopics(subscribedTopics.filter((t) => t !== topic.id));
                                  } else {
                                    setSubscribedTopics([...subscribedTopics, topic.id]);
                                  }
                                }}
                                style={{ cursor: 'pointer' }}
                              />
                              <span style={{ color: checked ? '#fafafa' : '#a1a1aa' }}>{topic.label}</span>
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </>
                )}

                {/* Actions */}
                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setIsPrefModalOpen(false)}
                    disabled={isSaving}
                    className="btn-secondary"
                    style={{
                      height: '36px',
                      padding: '0 16px',
                      fontSize: '13px',
                      borderRadius: '6px',
                      border: '1px solid #27272a',
                      backgroundColor: 'transparent',
                      color: '#fafafa',
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleSavePreferences}
                    disabled={isSaving || (optIn && subscribedTopics.length === 0)}
                    className="btn"
                    style={{
                      height: '36px',
                      padding: '0 16px',
                      fontSize: '13px',
                      borderRadius: '6px',
                      backgroundColor: '#0ea5e9',
                      color: '#fff',
                      border: 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="animate-spin" size={14} />
                        <span>Saving...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle size={14} />
                        <span>Save Settings</span>
                      </>
                    )}
                  </button>
                </div>
              </>
            ) : (
              <form onSubmit={handleChangePassword} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <p style={{ color: '#a1a1aa', fontSize: '13px', margin: 0, lineHeight: '1.5' }}>
                  Update your account password.
                </p>

                {passwordError && (
                  <div style={{ color: '#ef4444', backgroundColor: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.2)', padding: '10px', borderRadius: '6px', fontSize: '12px' }}>
                    {passwordError}
                  </div>
                )}
                {passwordSuccess && (
                  <div style={{ color: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '10px', borderRadius: '6px', fontSize: '12px' }}>
                    {passwordSuccess}
                  </div>
                )}

                <div>
                  <label htmlFor="curr-pass" style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '6px' }}>Current Password</label>
                  <input
                    id="curr-pass"
                    type="password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    required
                    style={{ width: '100%', height: '36px', fontSize: '13px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '6px', color: '#fafafa', padding: '8px 12px', outline: 'none' }}
                  />
                </div>

                <div>
                  <label htmlFor="new-pass" style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '6px' }}>New Password</label>
                  <input
                    id="new-pass"
                    type="password"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    required
                    style={{ width: '100%', height: '36px', fontSize: '13px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '6px', color: '#fafafa', padding: '8px 12px', outline: 'none' }}
                  />
                </div>

                <div>
                  <label htmlFor="conf-pass" style={{ display: 'block', fontSize: '12px', color: '#a1a1aa', marginBottom: '6px' }}>Confirm New Password</label>
                  <input
                    id="conf-pass"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    style={{ width: '100%', height: '36px', fontSize: '13px', backgroundColor: '#09090b', border: '1px solid #27272a', borderRadius: '6px', color: '#fafafa', padding: '8px 12px', outline: 'none' }}
                  />
                </div>

                <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', marginTop: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setIsPrefModalOpen(false)}
                    className="btn-secondary"
                    style={{
                      height: '36px',
                      padding: '0 16px',
                      fontSize: '13px',
                      borderRadius: '6px',
                      border: '1px solid #27272a',
                      backgroundColor: 'transparent',
                      color: '#fafafa',
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={isPasswordChanging || !currentPassword || !newPassword || !confirmPassword}
                    className="btn"
                    style={{
                      height: '36px',
                      padding: '0 16px',
                      fontSize: '13px',
                      borderRadius: '6px',
                      backgroundColor: '#0ea5e9',
                      color: '#fff',
                      border: 'none',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '6px',
                    }}
                  >
                    {isPasswordChanging ? (
                      <>
                        <Loader2 className="animate-spin" size={14} />
                        <span>Updating...</span>
                      </>
                    ) : (
                      <span>Update Password</span>
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
