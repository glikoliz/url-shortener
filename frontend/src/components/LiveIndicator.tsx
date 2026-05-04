
interface LiveIndicatorProps {
  isConnected: boolean;
  error: boolean;
}

const LiveIndicator = ({ isConnected, error }: LiveIndicatorProps) => {
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      padding: '6px 12px',
      background: 'rgba(255, 255, 255, 0.05)',
      borderRadius: '20px',
      border: '1px solid var(--glass-border)',
      fontSize: '12px',
      fontWeight: '600',
      color: error ? 'var(--error-color)' : (isConnected ? '#00ff88' : 'var(--text-secondary)'),
      transition: 'all 0.3s ease'
    }}>
      <div style={{
        width: '8px',
        height: '8px',
        borderRadius: '50%',
        background: error ? 'var(--error-color)' : (isConnected ? '#00ff88' : '#666'),
        boxShadow: isConnected && !error ? '0 0 10px #00ff88' : 'none',
        animation: isConnected && !error ? 'pulse 2s infinite' : 'none'
      }} />
      <span>{error ? 'DISCONNECTED' : (isConnected ? 'LIVE' : 'CONNECTING...')}</span>

      <style>{`
        @keyframes pulse {
          0% { opacity: 1; transform: scale(1); }
          50% { opacity: 0.5; transform: scale(1.2); }
          100% { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
};

export default LiveIndicator;
