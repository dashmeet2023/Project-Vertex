import React, { useEffect, useRef } from 'react';
import { useLinksStore } from '../state/linksStore';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Network, Database, ChevronRight, EyeOff, Lock } from 'lucide-react';

export const LinksDirectory: React.FC = () => {
  const { 
    links, 
    fetchLinks, 
    hasMore, 
    isLoadingLinks,
    syncStatus
  } = useLinksStore();

  const parentRef = useRef<HTMLDivElement>(null);

  // Initial load
  useEffect(() => {
    fetchLinks(true);
  }, [fetchLinks]);

  // Virtualizer setup
  const rowVirtualizer = useVirtualizer({
    count: links.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => 100, // estimated height of each link card
    overscan: 5,
  });

  const virtualItems = rowVirtualizer.getVirtualItems();

  // Scroll handler to load more items when close to bottom
  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const target = e.currentTarget;
    const threshold = 100; // px from bottom
    const isCloseToBottom = 
      target.scrollHeight - target.scrollTop - target.clientHeight < threshold;

    if (isCloseToBottom && hasMore && !isLoadingLinks) {
      fetchLinks();
    }
  };

  const currentRole = localStorage.getItem('vertex_role') || 'user';

  return (
    <div className="panel animate-fadeIn" style={{ display: 'flex', flexDirection: 'column', gap: '12px', flex: 1 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
          <Database size={20} style={{ color: 'var(--accent-color)' }} />
          Bidirectional Links Directory
        </h2>
        {isLoadingLinks && (
          <span className="badge badge-neutral animate-pulse" style={{ fontSize: '0.75rem' }}>
            Syncing...
          </span>
        )}
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
        A virtualized stream of active node handshakes. Keyset-paginated on the server.
      </p>

      {/* Virtualized Container */}
      <div 
        ref={parentRef}
        onScroll={handleScroll}
        style={{
          height: '400px',
          width: '100%',
          overflowY: 'auto',
          border: '1px solid var(--surface-border)',
          borderRadius: '8px',
          backgroundColor: 'rgba(0, 0, 0, 0.25)',
          position: 'relative'
        }}
      >
        {links.length > 0 ? (
          <div
            style={{
              height: `${rowVirtualizer.getTotalSize()}px`,
              width: '100%',
              position: 'relative'
            }}
          >
            {virtualItems.map((virtualRow) => {
              const link = links[virtualRow.index];
              const isOptimistic = link.id.startsWith('temp-');

              return (
                <div
                  key={virtualRow.key}
                  style={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    width: '100%',
                    height: `${virtualRow.size}px`,
                    transform: `translateY(${virtualRow.start}px)`,
                    padding: '8px 12px',
                    boxSizing: 'border-box'
                  }}
                >
                  <div 
                    style={{
                      height: '100%',
                      background: isOptimistic 
                        ? 'rgba(170, 59, 255, 0.08)' 
                        : 'rgba(31, 40, 51, 0.5)',
                      border: isOptimistic 
                        ? '1px dashed var(--primary-color)' 
                        : '1px solid var(--surface-border)',
                      borderRadius: '8px',
                      padding: '8px 12px',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      transition: 'all 0.2s ease-in-out',
                      position: 'relative'
                    }}
                  >
                    {/* Top Row: Nodes relationship */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ 
                          fontSize: '0.85rem', 
                          fontWeight: 600, 
                          color: 'var(--text-primary)',
                          background: 'rgba(255,255,255,0.05)',
                          padding: '2px 6px',
                          borderRadius: '4px'
                        }}>
                          {link.entity_a?.label || 'Resolving Entity A...'}
                        </span>
                        <ChevronRight size={14} style={{ color: 'var(--primary-color)' }} />
                        <span style={{ 
                          fontSize: '0.85rem', 
                          fontWeight: 600, 
                          color: 'var(--text-primary)',
                          background: 'rgba(255,255,255,0.05)',
                          padding: '2px 6px',
                          borderRadius: '4px'
                        }}>
                          {link.entity_b?.label || 'Destination Entity'}
                        </span>
                      </div>

                      {/* Sync handshake status */}
                      <div>
                        {isOptimistic ? (
                          <span className="badge badge-optimistic">
                            Optimistic
                          </span>
                        ) : (
                          <span className="badge badge-confirmed">
                            Confirmed
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Bottom Row: Metadata info */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px' }}>
                      <div style={{ 
                        fontSize: '0.75rem', 
                        color: 'var(--text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        maxWidth: '75%'
                      }}>
                        {currentRole === 'admin' ? (
                          <span style={{ 
                            color: 'var(--danger-color)', 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '4px',
                            backgroundColor: 'rgba(255,74,90,0.05)',
                            padding: '2px 6px',
                            borderRadius: '4px'
                          }}>
                            <Lock size={10} />
                            Private Notes: Blocked via RLS
                          </span>
                        ) : (
                          <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>
                            <strong>Notes:</strong> {link.private_notes || '—'}
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                        {new Date(link.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-secondary)',
            padding: '20px',
            textAlign: 'center'
          }}>
            <Network size={36} style={{ color: 'var(--surface-border)', marginBottom: '8px' }} />
            <span style={{ fontSize: '0.9rem' }}>No link relationships active.</span>
            <span style={{ fontSize: '0.75rem', marginTop: '4px' }}>Scan a reference token above to link nodes.</span>
          </div>
        )}
      </div>

      {hasMore && !isLoadingLinks && (
        <button 
          className="btn btn-secondary" 
          onClick={() => fetchLinks()}
          style={{ width: 'auto', alignSelf: 'center', fontSize: '0.8rem', padding: '6px 16px' }}
        >
          Load More Handshakes
        </button>
      )}
    </div>
  );
};
