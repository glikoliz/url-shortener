import React from 'react';

const GlassCard = ({ children, className = '', ...props }) => {
  return (
    <div 
      className={`glass-card ${className}`} 
      style={{
        background: 'var(--glass-bg)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        border: '1px solid var(--glass-border)',
        borderRadius: '16px',
        padding: '32px',
        boxShadow: '0 8px 32px 0 rgba(0, 0, 0, 0.3)',
      }}
      {...props}
    >
      {children}
    </div>
  );
};

export default GlassCard;
