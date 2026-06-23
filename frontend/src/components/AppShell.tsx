import React from 'react';
import { useAuth } from '../context/AuthContext';
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
} from 'lucide-react';

interface AppShellProps {
  children: React.ReactNode;
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export const AppShell: React.FC<AppShellProps> = ({ children, activeTab, setActiveTab }) => {
  const { user, logout, isAdmin } = useAuth();

  const menuItems = [
    { id: 'sources', label: 'Registered Sources', icon: Server },
    { id: 'targets', label: 'Target Catalog', icon: Database },
    { id: 'jobs', label: 'Pipeline Jobs', icon: Play },
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
    </div>
  );
};
