import React from 'react';
import GlassCard from '../components/GlassCard';
import { BarChart3, Link as LinkIcon } from 'lucide-react';

import ShortenForm from '../components/ShortenForm';

const Dashboard = () => {
  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
      
      {/* Top Section: Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
        <GlassCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ background: 'rgba(106, 0, 255, 0.2)', padding: '12px', borderRadius: '12px' }}>
              <LinkIcon size={24} color="var(--accent-color)" />
            </div>
            <div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>Total Links</p>
              <h3 style={{ fontSize: '28px', fontWeight: '700', margin: 0 }}>--</h3>
            </div>
          </div>
        </GlassCard>

        <GlassCard style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div style={{ background: 'rgba(0, 212, 255, 0.2)', padding: '12px', borderRadius: '12px' }}>
              <BarChart3 size={24} color="#00d4ff" />
            </div>
            <div>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px', marginBottom: '4px' }}>Total Clicks</p>
              <h3 style={{ fontSize: '28px', fontWeight: '700', margin: 0 }}>--</h3>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Middle Section: Shorten Form */}
      <ShortenForm />

      {/* Bottom Section: Links Table Placeholder (Step 5) */}
      <GlassCard>
        <h2 style={{ fontSize: '20px', marginBottom: '16px' }}>Your Links</h2>
        <div style={{ 
          height: '200px', 
          border: '1px dashed var(--glass-border)', 
          borderRadius: '8px', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          color: 'var(--text-secondary)'
        }}>
          Links Table (Coming in Step 5)
        </div>
      </GlassCard>
      
    </div>
  );
};

export default Dashboard;
