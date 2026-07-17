import React, { useEffect, useState } from 'react';
import { useLinksStore } from '../state/linksStore';
import { apiFetch } from '../utils/api';
import { Link2, Sparkles, Key, AlertCircle, Plus } from 'lucide-react';

interface SyncPanelProps {
  scannedToken: string;
  clearScannedToken: () => void;
}

export const SyncPanel: React.FC<SyncPanelProps> = ({ scannedToken, clearScannedToken }) => {
  const { 
    entities, 
    fetchEntities, 
    addEntityLocally,
    syncLink, 
    syncStatus, 
    error, 
    clearError 
  } = useLinksStore();

  const [selectedEntityB, setSelectedEntityB] = useState<string>('');
  const [privateNotes, setPrivateNotes] = useState<string>('');
  const [issuedToken, setIssuedToken] = useState<string | null>(null);
  const [tokenEntityId, setTokenEntityId] = useState<string>('');
  const [newEntityLabel, setNewEntityLabel] = useState<string>('');
  const [isCreatingEntity, setIsCreatingEntity] = useState<boolean>(false);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  // Set default selection when entities load
  useEffect(() => {
    if (entities.length > 0 && !selectedEntityB) {
      setSelectedEntityB(entities[0].id);
    }
  }, [entities, selectedEntityB]);

  const handleSyncSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!scannedToken || !selectedEntityB) return;

    try {
      await syncLink(scannedToken, selectedEntityB, privateNotes);
      // Clean up inputs on success
      setPrivateNotes('');
      clearScannedToken();
    } catch (err) {
      // Error is caught by store and state updated, we just handle local UI here
    }
  };

  // Helper endpoint to generate a testing token
  const handleIssueToken = async () => {
    if (!tokenEntityId) return;
    try {
      const resp = await apiFetch<{ token: string }>('/api/state/tokens', {
        method: 'POST',
        body: JSON.stringify({ entity_id: tokenEntityId })
      });
      setIssuedToken(resp.token);
    } catch (err: any) {
      alert(`Token generation failed: ${err.message}`);
    }
  };

  const handleCreateEntity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newEntityLabel.trim()) return;

    try {
      const newEnt = await addEntityLocally(newEntityLabel);
      setNewEntityLabel('');
      setIsCreatingEntity(false);
      setSelectedEntityB(newEnt.id);
    } catch (err) {
      // Error handled by store
    }
  };

  return (
    <div className="panel animate-fadeIn" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
        <Link2 size={20} style={{ color: 'var(--primary-color)' }} />
        Synchronization Panel
      </h2>

      {/* Sync form */}
      <form onSubmit={handleSyncSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <div className="form-group">
          <label className="form-label">Step 1: Scanned Token</label>
          <input 
            type="text" 
            readOnly 
            value={scannedToken || 'No token scanned yet (use viewfinder above)'} 
            className="form-input"
            style={{ 
              backgroundColor: 'rgba(0,0,0,0.1)', 
              borderColor: scannedToken ? 'var(--accent-color)' : 'var(--surface-border)',
              color: scannedToken ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontFamily: scannedToken ? 'var(--font-mono)' : 'inherit',
              fontSize: '0.85rem'
            }}
          />
        </div>

        <div className="form-group">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <label className="form-label">Step 2: Link with Destination Entity</label>
            <button 
              type="button" 
              onClick={() => setIsCreatingEntity(!isCreatingEntity)}
              style={{ background: 'none', border: 'none', color: 'var(--accent-color)', fontSize: '0.8rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '2px' }}
            >
              <Plus size={12} />
              New Entity
            </button>
          </div>

          {isCreatingEntity ? (
            <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
              <input 
                type="text" 
                placeholder="Entity label (e.g. Node Omega)" 
                value={newEntityLabel}
                onChange={(e) => setNewEntityLabel(e.target.value)}
                className="form-input"
              />
              <button type="button" className="btn btn-primary" onClick={handleCreateEntity} style={{ width: 'auto' }}>Create</button>
              <button type="button" className="btn btn-secondary" onClick={() => setIsCreatingEntity(false)} style={{ width: 'auto' }}>Cancel</button>
            </div>
          ) : (
            <select 
              value={selectedEntityB} 
              onChange={(e) => setSelectedEntityB(e.target.value)}
              className="form-select"
            >
              {entities.map(e => (
                <option key={e.id} value={e.id}>
                  {e.label} (ID: {e.id.slice(0, 8)}...)
                </option>
              ))}
              {entities.length === 0 && (
                <option value="">No entities available. Create one above.</option>
              )}
            </select>
          )}
        </div>

        <div className="form-group">
          <label className="form-label">Step 3: Private Metadata Notes (Optional)</label>
          <input 
            type="text" 
            placeholder="Private notes (inaccessible to Admin role)" 
            value={privateNotes}
            onChange={(e) => setPrivateNotes(e.target.value)}
            className="form-input"
          />
        </div>

        {error && (
          <div style={{ 
            display: 'flex', 
            alignItems: 'flex-start', 
            gap: '8px', 
            padding: '12px', 
            background: 'var(--danger-glow)', 
            border: '1px solid rgba(255, 74, 90, 0.3)',
            borderRadius: '8px',
            color: 'var(--danger-color)',
            fontSize: '0.85rem'
          }}>
            <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', width: '100%' }}>
              <strong style={{ display: 'block' }}>Sync Error:</strong>
              <span>{error}</span>
              <button 
                type="button" 
                onClick={clearError} 
                style={{ 
                  alignSelf: 'flex-end', 
                  background: 'none', 
                  border: 'none', 
                  color: 'var(--danger-color)', 
                  textDecoration: 'underline', 
                  cursor: 'pointer',
                  fontSize: '0.75rem',
                  padding: 0
                }}
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        <button 
          type="submit" 
          disabled={!scannedToken || !selectedEntityB || syncStatus === 'pending' || syncStatus === 'optimistic'}
          className="btn btn-primary"
        >
          {syncStatus === 'optimistic' ? (
            <>
              <Sparkles className="animate-pulse" size={16} />
              Syncing Optimistically...
            </>
          ) : syncStatus === 'pending' ? (
            'Awaiting Server Conf...'
          ) : (
            'Establish Bidirectional Link'
          )}
        </button>
      </form>

      {/* Test Token Generator Utility */}
      <div style={{
        marginTop: '12px',
        padding: '12px',
        background: 'rgba(255,255,255,0.02)',
        borderRadius: '8px',
        border: '1px dashed var(--surface-border)'
      }}>
        <h3 style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
          <Key size={14} style={{ color: 'var(--warning-color)' }} />
          Local Test Token Generator
        </h3>
        <div style={{ display: 'flex', gap: '8px' }}>
          <select 
            value={tokenEntityId}
            onChange={(e) => setTokenEntityId(e.target.value)}
            className="form-select"
            style={{ fontSize: '0.8rem', padding: '6px 8px' }}
          >
            <option value="">Select entity A...</option>
            {entities.map(e => (
              <option key={e.id} value={e.id}>{e.label}</option>
            ))}
          </select>
          <button 
            type="button" 
            onClick={handleIssueToken} 
            disabled={!tokenEntityId}
            className="btn btn-secondary"
            style={{ width: 'auto', fontSize: '0.8rem', padding: '6px 12px' }}
          >
            Get Token
          </button>
        </div>

        {issuedToken && (
          <div style={{ marginTop: '8px' }}>
            <span style={{ fontSize: '0.75rem', display: 'block', color: 'var(--warning-color)', marginBottom: '4px' }}>
              Copy this token and paste it into the simulator input:
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <input 
                type="text" 
                readOnly 
                value={issuedToken} 
                className="form-input" 
                style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', padding: '4px 8px' }}
                onClick={(e) => (e.target as HTMLInputElement).select()}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
