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

  const menuItems = [
    { id: 'sources', label: 'Registered Sources', icon: Server },
    { id: 'targets', label: 'Target Catalog', icon: Database },
    { id: 'jobs', label: 'Pipeline Jobs', icon: Play },
    { id: 'quality-jobs', label: 'Data Quality Jobs', icon: CheckCircle },
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
                <Bell size={20} color="#f59e0b" />
                <h3 style={{ fontSize: '18px', fontWeight: 600, color: '#fafafa', margin: 0 }}>
                  Notification Settings
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
          </div>
        </div>
      )}
    </div>
  );
};
