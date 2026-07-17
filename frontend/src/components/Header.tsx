import React, { useState, useEffect } from 'react';
import { useLinksStore } from '../state/linksStore';
import { Shield, User, RefreshCw, Wifi, WifiOff } from 'lucide-react';

export const Header: React.FC = () => {
  const [role, setRole] = useState<string>(localStorage.getItem('vertex_role') || 'user');
  const { fetchLinks, networkStatus, setNetworkStatus } = useLinksStore();

  const handleRoleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newRole = e.target.value;
    localStorage.setItem('vertex_role', newRole);
    setRole(newRole);
    // Reload links directory to reflect column-level RLS privilege changes immediately
    fetchLinks(true);
  };

  // Monitor online status
  useEffect(() => {
    const handleOnline = () => setNetworkStatus('online');
    const handleOffline = () => setNetworkStatus('offline');

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Initial check
    if (!navigator.onLine) {
      setNetworkStatus('offline');
    }

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, [setNetworkStatus]);

  return (
    <header className="panel animate-fadeIn" style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      marginTop: '20px',
      padding: '12px 18px',
      borderBottom: '1px solid var(--surface-border)',
      background: 'rgba(31, 40, 51, 0.6)'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <div style={{
          width: '32px',
          height: '32px',
          borderRadius: '8px',
          background: 'linear-gradient(135deg, var(--primary-color), var(--accent-color))',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontWeight: 'bold',
          color: 'white',
          fontSize: '1.2rem'
        }}>
          V
        </div>
        <div>
          <h1 style={{ fontSize: '1.1rem', margin: 0, fontWeight: 700 }}>Project Vertex</h1>
          <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>Track C Sync Engine</span>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        {/* Network status badge */}
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {networkStatus === 'online' ? (
            <span className="badge badge-neutral" style={{ gap: '4px', background: 'rgba(46, 196, 182, 0.1)', color: 'var(--success-color)' }}>
              <Wifi size={12} />
              Online
            </span>
          ) : (
            <span className="badge badge-error" style={{ gap: '4px' }}>
              <WifiOff size={12} />
              Offline
            </span>
          )}
        </div>

        {/* Dynamic Role Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', backgroundColor: 'rgba(0,0,0,0.2)', padding: '4px 10px', borderRadius: '8px', border: '1px solid var(--surface-border)' }}>
          {role === 'admin' ? (
            <Shield size={16} style={{ color: 'var(--danger-color)' }} />
          ) : (
            <User size={16} style={{ color: 'var(--accent-color)' }} />
          )}
          <select 
            value={role} 
            onChange={handleRoleChange}
            className="form-select"
            style={{
              padding: '2px 4px',
              background: 'transparent',
              border: 'none',
              color: 'var(--text-primary)',
              fontSize: '0.85rem',
              fontWeight: 500,
              cursor: 'pointer',
              outline: 'none',
              width: 'auto'
            }}
          >
            <option value="user" style={{ backgroundColor: 'var(--surface-color)' }}>App User</option>
            <option value="admin" style={{ backgroundColor: 'var(--surface-color)' }}>App Admin (RLS Restricted)</option>
          </select>
        </div>
      </div>
    </header>
  );
};
