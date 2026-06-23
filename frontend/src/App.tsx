import React, { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './pages/Login';
import { AppShell } from './components/AppShell';

const AppContent: React.FC = () => {
  const { token, loading } = useAuth();
  const [activeTab, setActiveTab] = useState('sources');

  if (loading) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          backgroundColor: '#09090b',
          color: '#fafafa',
          fontFamily: 'sans-serif',
        }}
      >
        <span>Loading session...</span>
      </div>
    );
  }

  if (!token) {
    return <Login />;
  }

  // Render placeholders for Phase 3 pages during Phase 2 scaffolding
  const renderContent = () => {
    switch (activeTab) {
      case 'sources':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Registered Sources</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for Registered Sources Management & Ingest triggers (Phase 3).</p>
          </div>
        );
      case 'targets':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Target Catalog</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for Destination schemas and table registrations (Phase 3).</p>
          </div>
        );
      case 'jobs':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Pipeline Jobs</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for active jobs progress, retries, kills, and lineage mapping (Phase 3).</p>
          </div>
        );
      case 'dlq':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Dead Letter Queue</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for failed queue items and manual recovery hooks (Phase 3).</p>
          </div>
        );
      case 'fallback':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Fallback Approvals</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for pending drift fallback SQL DDL approvals (Phase 3).</p>
          </div>
        );
      case 'admin':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Admin Console</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for user role promotions, demotions, deletions, and channel alerts (Phase 3).</p>
          </div>
        );
      case 'audit':
        return (
          <div>
            <h2 style={{ fontSize: '20px', marginBottom: '8px' }}>Audit Logs</h2>
            <p style={{ color: '#a1a1aa' }}>Placeholder for viewing system-wide manual operations history (Phase 3).</p>
          </div>
        );
      default:
        return <div>Tab not found</div>;
    }
  };

  return (
    <AppShell activeTab={activeTab} setActiveTab={setActiveTab}>
      {renderContent()}
    </AppShell>
  );
};

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
