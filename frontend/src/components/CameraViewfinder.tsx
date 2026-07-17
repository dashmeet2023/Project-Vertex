import React, { useEffect, useRef, useState } from 'react';
import { Camera, RefreshCw, AlertTriangle, Check, Info } from 'lucide-react';

interface CameraViewfinderProps {
  onScanSuccess: (token: string) => void;
}

export const CameraViewfinder: React.FC<CameraViewfinderProps> = ({ onScanSuccess }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [facingMode, setFacingMode] = useState<'user' | 'environment'>('environment');
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [hasCamera, setHasCamera] = useState<boolean>(true);
  const [detectorSupported, setDetectorSupported] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [scanning, setScanning] = useState<boolean>(false);
  const [scannedVal, setScannedVal] = useState<string | null>(null);
  const [manualToken, setManualToken] = useState<string>('');

  // Check BarcodeDetector support
  useEffect(() => {
    if (typeof window !== 'undefined' && 'BarcodeDetector' in window) {
      setDetectorSupported(true);
    }
  }, []);

  // Start the video stream
  const startCamera = async () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
    }

    setErrorMsg(null);
    try {
      const constraints = {
        video: {
          facingMode: facingMode,
          width: { ideal: 640 },
          height: { ideal: 480 }
        },
        audio: false
      };

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      setStream(mediaStream);
      setHasPermission(true);
      setHasCamera(true);

      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err: any) {
      console.error('Camera stream access failed:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setHasPermission(false);
        setErrorMsg('Camera permission denied. Please allow camera access in browser settings.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setHasCamera(false);
        setErrorMsg('No camera hardware detected on this device.');
      } else {
        setErrorMsg(`Camera error: ${err.message || 'Unknown error'}`);
      }
    }
  };

  useEffect(() => {
    startCamera();
    return () => {
      if (stream) {
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, [facingMode]);

  // Barcode Detection loop
  useEffect(() => {
    if (!stream || !detectorSupported || !videoRef.current) return;

    let active = true;
    let detector: any;

    try {
      // @ts-ignore
      detector = new window.BarcodeDetector({
        formats: ['qr_code', 'code_128', 'code_39', 'ean_13']
      });
    } catch (e) {
      console.warn('BarcodeDetector instantiation failed:', e);
      return;
    }

    const checkFrame = async () => {
      if (!active || !videoRef.current) return;

      try {
        if (videoRef.current.readyState === videoRef.current.HAVE_ENOUGH_DATA) {
          const barcodes = await detector.detect(videoRef.current);
          if (barcodes.length > 0 && active) {
            const token = barcodes[0].rawValue;
            setScannedVal(token);
            onScanSuccess(token);
            // Visual scan feedback
            setScanning(false);
            active = false; // stop scanning once found
          }
        }
      } catch (err) {
        // Suppress repeated frame errors
      }

      if (active) {
        requestAnimationFrame(checkFrame);
      }
    };

    setScanning(true);
    requestAnimationFrame(checkFrame);

    return () => {
      active = false;
    };
  }, [stream, detectorSupported, onScanSuccess]);

  // Toggle camera direction
  const toggleFacingMode = () => {
    setFacingMode(prev => (prev === 'environment' ? 'user' : 'environment'));
  };

  // Mock scanner trigger for local developer convenience
  const handleMockScan = () => {
    if (!manualToken.trim()) return;
    setScannedVal(manualToken);
    onScanSuccess(manualToken);
  };

  return (
    <div className="panel animate-fadeIn" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '8px', margin: 0 }}>
          <Camera size={20} className="animate-pulse" style={{ color: 'var(--accent-color)' }} />
          Token Scanner
        </h2>
        {hasCamera && hasPermission && (
          <button 
            type="button"
            className="btn btn-secondary" 
            onClick={toggleFacingMode}
            style={{ width: 'auto', padding: '6px 12px', fontSize: '0.8rem' }}
          >
            <RefreshCw size={12} />
            Flip ({facingMode === 'environment' ? 'Back' : 'Front'})
          </button>
        )}
      </div>

      {/* Viewfinder area */}
      <div className="viewfinder-container">
        {hasPermission && hasCamera ? (
          <>
            <video 
              ref={videoRef} 
              autoPlay 
              playsInline 
              muted 
              className="viewfinder-video"
            />
            <div className="viewfinder-overlay">
              <div className="viewfinder-target">
                {scanning && <div className="viewfinder-scan-line" />}
              </div>
            </div>
          </>
        ) : (
          <div style={{
            height: '100%',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '24px',
            backgroundColor: 'rgba(0,0,0,0.4)',
            color: 'var(--text-secondary)',
            textAlign: 'center'
          }}>
            <AlertTriangle size={32} style={{ color: 'var(--danger-color)', marginBottom: '12px' }} />
            <p style={{ fontSize: '0.9rem', marginBottom: '8px' }}>
              {errorMsg || 'Camera initialization failed'}
            </p>
            <button className="btn btn-secondary" onClick={startCamera} style={{ width: 'auto', marginTop: '12px' }}>
              Retry Camera Connection
            </button>
          </div>
        )}
      </div>

      {/* Native BarcodeDetector feedback */}
      {!detectorSupported && (
        <div style={{
          display: 'flex',
          gap: '8px',
          alignItems: 'flex-start',
          padding: '10px 14px',
          background: 'rgba(255, 159, 28, 0.08)',
          borderRadius: '8px',
          border: '1px solid rgba(255, 159, 28, 0.2)',
          fontSize: '0.8rem',
          lineHeight: '1.4'
        }}>
          <Info size={16} style={{ color: 'var(--warning-color)', flexShrink: 0, marginTop: '2px' }} />
          <span>
            <strong>BarcodeDetector API is not supported on this browser.</strong> Use the manual validation simulator below to emulate capturing reference tokens.
          </span>
        </div>
      )}

      {/* Manual Input / Mock Scanner Controls */}
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column', 
        gap: '10px',
        padding: '12px',
        backgroundColor: 'rgba(0, 0, 0, 0.2)',
        borderRadius: '8px',
        border: '1px solid var(--surface-border)'
      }}>
        <div className="form-group" style={{ margin: 0 }}>
          <label className="form-label" style={{ fontSize: '0.8rem' }}>Token Validation Simulator</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input 
              type="text" 
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              placeholder="Paste reference token (e.g. from state/tokens)"
              className="form-input"
              style={{ fontSize: '0.85rem' }}
            />
            <button 
              type="button"
              className="btn btn-primary"
              onClick={handleMockScan}
              disabled={!manualToken.trim()}
              style={{ width: 'auto', whiteSpace: 'nowrap' }}
            >
              Simulate Scan
            </button>
          </div>
        </div>
      </div>

      {scannedVal && (
        <div style={{ 
          display: 'flex', 
          alignItems: 'center', 
          gap: '8px', 
          padding: '8px 12px', 
          background: 'rgba(46, 196, 182, 0.1)', 
          border: '1px solid rgba(46, 196, 182, 0.3)',
          color: 'var(--success-color)',
          borderRadius: '8px',
          fontSize: '0.85rem'
        }}>
          <Check size={16} />
          <span style={{ wordBreak: 'break-all' }}>
            <strong>Scanned:</strong> {scannedVal}
          </span>
        </div>
      )}
    </div>
  );
};
