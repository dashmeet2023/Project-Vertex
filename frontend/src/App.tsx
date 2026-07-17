import React, { useState } from 'react';
import { Header } from './components/Header';
import { CameraViewfinder } from './components/CameraViewfinder';
import { SyncPanel } from './components/SyncPanel';
import { LinksDirectory } from './components/LinksDirectory';

function App() {
  const [scannedToken, setScannedToken] = useState<string>('');

  const handleScanSuccess = (token: string) => {
    setScannedToken(token);
  };

  const handleClearToken = () => {
    setScannedToken('');
  };

  return (
    <div className="app-container">
      <Header />
      
      <main style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
        <CameraViewfinder onScanSuccess={handleScanSuccess} />
        
        <SyncPanel 
          scannedToken={scannedToken} 
          clearScannedToken={handleClearToken} 
        />
        
        <LinksDirectory />
      </main>

      <footer style={{
        textAlign: 'center',
        padding: '24px 0 12px 0',
        fontSize: '0.75rem',
        color: 'var(--text-secondary)',
        borderTop: '1px solid var(--surface-border)',
        marginTop: '32px'
      }}>
        Project Vertex &bull; Keyset State Sync &bull; Secure RLS Architecture
      </footer>
    </div>
  );
}

export default App;

