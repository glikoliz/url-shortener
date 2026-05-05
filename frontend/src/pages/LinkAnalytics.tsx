import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ArrowLeft, MousePointerClick, Globe, Link2, RefreshCw, ChevronUp, ChevronDown, ArrowUpDown } from 'lucide-react';
import { apiClient } from '../api/client';
import GlassCard from '../components/GlassCard';
import LiveIndicator from '../components/LiveIndicator';
import { useSSESubscription, useSSEStatus } from '../context/SSEContext';
import { useDebounce } from '../hooks/useDebounce';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { LinkStats, ClicksResponse, SSEEvent, Click } from '../types';

const fmtDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

const parseUa = (ua: string | null) => {
  if (!ua) return 'Unknown';
  const browsers: [string, string][] = [
    ['Edg', 'Edge'],
    ['OPR', 'Opera'],
    ['Chrome', 'Chrome'],
    ['Firefox', 'Firefox'],
    ['Safari', 'Safari'],
  ];
  const uaString = ua as string;
  for (const [token, name] of browsers) {
    if (uaString.includes(token)) return name;
  }
  return 'Other';
};

const getFlagEmoji = (countryCode: string) => {
  if (!countryCode || countryCode === 'Unknown' || countryCode.length !== 2) return '🏳️';
  const codePoints = countryCode
    .toUpperCase()
    .split('')
    .map(char => 127397 + char.charCodeAt(0));
  return String.fromCodePoint(...codePoints);
};

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
}

const CustomTooltip = ({ active, payload, label }: CustomTooltipProps) => {
  if (!active || !payload?.length) return null;

  const formattedLabel = useMemo(() => {
    if (!label) return '';
    try {
      const date = new Date(label as string);
      if (isNaN(date.getTime())) return label as string;
      return date.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false
      });
    } catch (e) {
      return label;
    }
  }, [label]);

  return (
    <div
      style={{
        background: 'rgba(11,12,16,0.95)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderRadius: '8px',
        padding: '10px 14px',
        fontSize: '13px',
        color: '#fff',
      }}
    >
      <p style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>{formattedLabel}</p>
      <p style={{ color: 'var(--accent-color)', fontWeight: 600 }}>{payload[0].value} clicks</p>
    </div>
  );
};

interface StatCardProps {
  icon: any;
  label: string;
  value: string | number;
  color: string;
}

const StatCard = ({ icon: Icon, label, value, color }: StatCardProps) => (
  <div
    style={{
      background: 'rgba(255,255,255,0.03)',
      border: '1px solid rgba(255,255,255,0.08)',
      borderRadius: '16px',
      padding: '20px 24px',
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
    }}
  >
    <div
      style={{
        width: '44px',
        height: '44px',
        borderRadius: '12px',
        background: `${color}22`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
      }}
    >
      <Icon size={20} color={color} />
    </div>
    <div>
      <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '4px' }}>
        {label}
      </p>
      <p style={{ fontSize: '24px', fontWeight: '700' }}>{value}</p>
    </div>
  </div>
);

const ClickRow = ({ click }: { click: Click }) => (
  <tr
    style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}
    className="hover-row"
  >
    <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
      {fmtDate(click.clicked_at)}
    </td>
    <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: '13px' }}>
      {click.ip_address || '—'}
    </td>
    <td style={{ padding: '12px 16px', fontSize: '13px' }}>{parseUa(click.user_agent)}</td>
    <td
      style={{
        padding: '12px 16px',
        fontSize: '13px',
        maxWidth: '200px',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
        color: 'var(--text-secondary)',
      }}
    >
      {click.referer || 'Direct'}
    </td>
    <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '16px' }}>{getFlagEmoji(click.country || 'Unknown')}</span>
        {click.country || 'Unknown'}
        {click.is_unique && (
          <span style={{
            fontSize: '10px',
            background: 'rgba(16, 185, 129, 0.1)',
            color: '#10b981',
            padding: '2px 6px',
            borderRadius: '4px',
            fontWeight: '600',
            border: '1px solid rgba(16, 185, 129, 0.2)'
          }}>
            UNIQUE
          </span>
        )}
      </div>
    </td>
  </tr>
);

const LinkAnalytics = () => {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [sortConfig, setSortConfig] = useState<{ key: string, direction: 'asc' | 'desc' }>({ key: 'clicked_at', direction: 'desc' });
  const [selectedGranularity, setSelectedGranularity] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [ipFilter, setIpFilter] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const CLICKS_PER_PAGE = 25;

  const debouncedIp = useDebounce(ipFilter, 500);
  const debouncedCountry = useDebounce(countryFilter, 500);

  // Stats Query
  const {
    data: stats,
    isLoading: loadingStats,
    isError: isStatsError,
    error: statsError
  } = useQuery<LinkStats>({
    queryKey: ['linkStats', code, selectedGranularity],
    queryFn: () => apiClient(selectedGranularity ? `/links/i/${code}/stats?granularity=${selectedGranularity}` : `/links/i/${code}/stats`),
    enabled: !!code,
    retry: false, // Don't retry on 403/404
  });

  // Clicks Query
  const skip = (currentPage - 1) * CLICKS_PER_PAGE;
  const {
    data: clicksData,
    isLoading: loadingClicks,
    isError: isClicksError,
    error: clicksError
  } = useQuery<ClicksResponse>({
    queryKey: ['linkClicks', code, currentPage, debouncedIp, debouncedCountry],
    queryFn: () => apiClient(`/links/i/${code}/clicks?limit=${CLICKS_PER_PAGE}&skip=${skip}&ip=${debouncedIp}&country=${debouncedCountry}`),
    enabled: !!code,
    retry: false,
  });

  const clicks = clicksData?.items || [];
  const totalClicksCount = clicksData?.total || 0;

  // Real-time updates
  const { isConnected, error: sseError } = useSSEStatus();

  useSSESubscription((data: SSEEvent) => {
    if (data.type === 'link_updated' && data.short_code === code) {
      queryClient.invalidateQueries({ queryKey: ['linkStats', code] });
      queryClient.invalidateQueries({ queryKey: ['linkClicks', code] });
    }
  });

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['linkStats', code] });
    queryClient.invalidateQueries({ queryKey: ['linkClicks', code] });
  };

  const combinedError = (statsError as any)?.message || (clicksError as any)?.message;
  const isForbidden = (isStatsError || isClicksError) && (
    combinedError?.toLowerCase().includes('not your link') ||
    combinedError?.toLowerCase().includes('forbidden') ||
    combinedError?.toLowerCase().includes('access denied') ||
    combinedError?.toLowerCase().includes('permission')
  );
  const isNotFound = (isStatsError || isClicksError) && combinedError?.toLowerCase().includes('not found');

  const topCountries = useMemo(() => {
    return stats?.top_countries?.map(c => ({
      ...c,
      country: c.country || 'Unknown'
    })) || [];
  }, [stats]);

  const topSources = useMemo(() => {
    return stats?.top_referers?.map(r => {
      const name = r.referer || 'Direct';
      let displayName = name;
      let domain = '';
      if (name !== 'Direct') {
        try {
          const url = new URL(name.startsWith('http') ? name : `https://${name}`);
          domain = url.hostname;
          displayName = url.hostname.replace('www.', '');
        } catch (e) {
          displayName = name;
        }
      }
      return { ...r, displayName, domain };
    }) || [];
  }, [stats]);

  const topCountry = topCountries[0]?.country || 'Unknown';
  const totalUniqueClicks = stats?.unique_ips || 0;

  const requestSort = (key: string) => {
    let direction: 'asc' | 'desc' = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sortedClicks = useMemo(() => {
    let sortableItems = [...clicks];
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let aVal = (a as any)[sortConfig.key] || '';
        let bVal = (b as any)[sortConfig.key] || '';

        if (sortConfig.key === 'user_agent') {
          aVal = parseUa(aVal);
          bVal = parseUa(bVal);
        }

        if (aVal < bVal) {
          return sortConfig.direction === 'asc' ? -1 : 1;
        }
        if (aVal > bVal) {
          return sortConfig.direction === 'asc' ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableItems;
  }, [clicks, sortConfig]);

  const getSortIcon = (key: string) => {
    if (sortConfig.key !== key) return <ArrowUpDown size={14} style={{ opacity: 0.3 }} />;
    return sortConfig.direction === 'asc' ? <ChevronUp size={14} color="var(--accent-color)" /> : <ChevronDown size={14} color="var(--accent-color)" />;
  };

  // 1. Check for Forbidden first
  if (isForbidden) {
    return (
      <div style={{ padding: '60px 20px', display: 'flex', justifyContent: 'center' }} className="animate-fade-in">
        <GlassCard style={{ maxWidth: '500px', width: '100%', textAlign: 'center', padding: '48px 32px' }}>
          <div style={{
            width: '80px',
            height: '80px',
            background: 'rgba(244, 63, 94, 0.1)',
            borderRadius: '24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 24px'
          }}>
            <div style={{ color: 'var(--error-color)' }}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
          </div>
          <h1 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Access Denied</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '32px', lineHeight: '1.6' }}>
            You don't have permission to view analytics for this link. Only the creator of the link can access its detailed statistics.
          </p>
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'var(--accent-color)',
              color: '#000',
              border: 'none',
              padding: '12px 24px',
              borderRadius: '12px',
              fontWeight: '600',
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              transition: 'transform 0.2s'
            }}
            onMouseOver={e => e.currentTarget.style.transform = 'translateY(-2px)'}
            onMouseOut={e => e.currentTarget.style.transform = 'translateY(0)'}
          >
            <ArrowLeft size={18} /> Back to Dashboard
          </button>
        </GlassCard>
      </div>
    );
  }

  // 2. Check for Not Found
  if (isNotFound) {
     return (
      <div style={{ padding: '60px 20px', display: 'flex', justifyContent: 'center' }} className="animate-fade-in">
        <GlassCard style={{ maxWidth: '500px', width: '100%', textAlign: 'center', padding: '48px 32px' }}>
          <h1 style={{ fontSize: '24px', fontWeight: '700', marginBottom: '12px' }}>Link Not Found</h1>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '32px' }}>
            The link you are looking for does not exist or has been deleted.
          </p>
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'var(--accent-color)',
              color: '#000',
              padding: '12px 24px',
              borderRadius: '12px',
              fontWeight: '600'
            }}
          >
            Back to Dashboard
          </button>
        </GlassCard>
      </div>
    );
  }

  // 3. Show global loading state if we have no data and no error yet
  if ((loadingStats || loadingClicks) && !stats && clicks.length === 0) {
    return (
      <div style={{ padding: '100px 20px', textAlign: 'center', color: 'var(--text-secondary)' }} className="animate-fade-in">
        <div className="loader" style={{ marginBottom: '20px' }}>
           <RefreshCw size={40} className="animate-spin" style={{ animation: 'spin 1s linear infinite', margin: '0 auto' }} />
        </div>
        <p>Loading analytics data...</p>
      </div>
    );
  }

  return (
    <div style={{ padding: '32px', maxWidth: '1100px', margin: '0 auto' }} className="animate-fade-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '32px' }}>
        <button
          onClick={() => navigate('/')}
          style={{
            background: 'rgba(255,255,255,0.05)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '10px',
            padding: '8px 12px',
            color: 'var(--text-secondary)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '14px',
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => (e.currentTarget.style.color = '#fff')}
          onMouseOut={(e) => (e.currentTarget.style.color = 'var(--text-secondary)')}
        >
          <ArrowLeft size={16} /> Dashboard
        </button>

        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: '22px', fontWeight: '700', display: 'flex', alignItems: 'center', gap: '12px' }}>
            Analytics —{' '}
            <span style={{ color: 'var(--accent-color)' }}>{code}</span>
            <LiveIndicator isConnected={isConnected} error={sseError} />
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Click statistics for your short link
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={loadingStats || loadingClicks}
          style={{
            background: 'rgba(56,189,248,0.1)',
            border: '1px solid rgba(56,189,248,0.2)',
            borderRadius: '10px',
            padding: '8px 14px',
            color: 'var(--accent-color)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '14px',
            transition: 'all 0.2s',
            opacity: (loadingStats || loadingClicks) ? 0.6 : 1,
          }}
        >
          <RefreshCw size={15} style={{ animation: (loadingStats || loadingClicks) ? 'spin 1s linear infinite' : 'none' }} />
          Refresh
        </button>
      </div>

      {/* Stat cards */}
      {!loadingStats && stats && (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '16px',
            marginBottom: '28px',
          }}
        >
          <StatCard icon={MousePointerClick} label="Total Clicks" value={stats.total_clicks} color="var(--accent-color)" />
          <StatCard icon={MousePointerClick} label="Unique Clicks" value={stats.unique_clicks} color="#fbbf24" />
          <StatCard icon={Globe} label="Unique IPs" value={totalUniqueClicks} color="#60a5fa" />
          <StatCard
            icon={() => <span style={{ fontSize: '20px' }}>{getFlagEmoji(topCountry)}</span>}
            label="Top Country"
            value={topCountry}
            color="#34d399"
          />
        </div>
      )}

      {/* Clicks over time chart */}
      <GlassCard style={{ marginBottom: '20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: '600' }}>Clicks over Time</h2>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            {['day', 'hour', 'minute'].map((g) => (
              <button
                key={g}
                onClick={() => setSelectedGranularity(g === selectedGranularity ? null : g)}
                style={{
                  fontSize: '11px',
                  background: selectedGranularity === g ? 'var(--accent-color)' : 'rgba(255,255,255,0.05)',
                  color: selectedGranularity === g ? '#000' : 'var(--text-secondary)',
                  border: 'none',
                  padding: '3px 10px',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  fontWeight: selectedGranularity === g ? '600' : '400',
                  transition: 'all 0.2s',
                  textTransform: 'capitalize'
                }}
              >
                {g}
              </button>
            ))}
            {stats?.granularity && !selectedGranularity && (
              <span style={{ fontSize: '11px', color: 'var(--accent-color)', opacity: 0.8, marginLeft: '8px', fontStyle: 'italic' }}>
                Auto: {stats.granularity}
              </span>
            )}
          </div>
        </div>
        {loadingStats ? (
          <div style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
            Loading…
          </div>
        ) : (stats?.clicks_by_day?.length ?? 0) > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart
              data={stats?.clicks_by_day || []}
              margin={{ top: 5, right: 10, left: -20, bottom: 0 }}
              style={{ outline: 'none' }}
            >
              <defs>
                <linearGradient id="clicksGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-color)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-color)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#8b8e98' }}
                tickFormatter={(val) => {
                  if (!val) return '';
                  try {
                    const date = new Date(val as string);
                    if (isNaN(date.getTime())) return val as string;
                    const granularity = selectedGranularity || stats?.granularity || 'day';
                    if (granularity === 'minute') {
                      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
                    }
                    if (granularity === 'hour') {
                      return date.toLocaleString([], { month: 'numeric', day: 'numeric', hour: '2-digit', hour12: false });
                    }
                    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
                  } catch (e) {
                    return val;
                  }
                }}
              />
              <YAxis tick={{ fontSize: 11, fill: '#8b8e98' }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} />
              <Area
                type="monotone"
                dataKey="clicks"
                stroke="var(--accent-color)"
                strokeWidth={2}
                fill="url(#clicksGrad)"
                animationDuration={600}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>
            No clicks yet — share your link to start collecting data!
          </div>
        )}
      </GlassCard>

      {/* Bottom row: referers + countries */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px', marginBottom: '20px' }}>
        {/* Top Sources */}
        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600' }}>Top Sources</h2>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Clicks</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {topSources.length > 0 ? topSources.slice(0, 10).map((source, i) => {
              const percentage = stats?.total_clicks ? (source.clicks / stats.total_clicks) * 100 : 0;
              return (
                <div key={i} style={{ position: 'relative', overflow: 'hidden', borderRadius: '8px', background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: `${percentage}%`,
                    background: 'linear-gradient(90deg, rgba(56,189,248,0.1) 0%, rgba(56,189,248,0.05) 100%)',
                    zIndex: 0,
                    transition: 'width 1s ease-out'
                  }} />
                  <div style={{ position: 'relative', zIndex: 1, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0 }}>
                      <div style={{ width: '24px', height: '24px', borderRadius: '6px', background: 'rgba(255,255,255,0.05)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                        {source.domain ? (
                          <img
                            src={`https://www.google.com/s2/favicons?domain=${source.domain}&sz=32`}
                            alt=""
                            style={{ width: '14px', height: '14px' }}
                            onError={(e) => (e.currentTarget.style.display = 'none')}
                          />
                        ) : <MousePointerClick size={14} color="var(--text-secondary)" />}
                      </div>
                      <span style={{ fontSize: '14px', fontWeight: '500', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={source.referer || 'Direct'}>
                        {source.displayName}
                      </span>
                    </div>
                    <span style={{ fontSize: '14px', fontWeight: '600', color: 'var(--accent-color)', marginLeft: '12px' }}>{source.clicks}</span>
                  </div>
                </div>
              );
            }) : (
              <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>No data yet</div>
            )}
          </div>
        </GlassCard>

        {/* Top Countries */}
        <GlassCard>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: '600' }}>Top Countries</h2>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Clicks</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {topCountries.length > 0 ? topCountries.slice(0, 10).map((c, i) => {
              const percentage = stats?.total_clicks ? (c.clicks / stats.total_clicks) * 100 : 0;
              return (
                <div key={i} style={{ position: 'relative', overflow: 'hidden', borderRadius: '8px', background: 'rgba(255,255,255,0.02)' }}>
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: `${percentage}%`,
                    background: 'linear-gradient(90deg, rgba(52,211,153,0.1) 0%, rgba(52,211,153,0.05) 100%)',
                    zIndex: 0,
                    transition: 'width 1s ease-out'
                  }} />
                  <div style={{ position: 'relative', zIndex: 1, padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <span style={{ fontSize: '20px', width: '24px', textAlign: 'center' }}>
                        {getFlagEmoji(c.country)}
                      </span>
                      <span style={{ fontSize: '14px', fontWeight: '500' }}>{c.country}</span>
                    </div>
                    <span style={{ fontSize: '14px', fontWeight: '600', color: '#34d399' }}>{c.clicks}</span>
                  </div>
                </div>
              );
            }) : (
              <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>No data yet</div>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Clicks log table */}
      <GlassCard>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: '600' }}>Detailed Click Logs</h2>
          <div style={{ display: 'flex', gap: '12px' }}>
            <input
              type="text"
              placeholder="Filter IP..."
              value={ipFilter}
              onChange={(e) => { setIpFilter(e.target.value); setCurrentPage(1); }}
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '13px',
                color: '#fff',
                width: '140px'
              }}
            />
            <select
              value={countryFilter}
              onChange={(e) => { setCountryFilter(e.target.value); setCurrentPage(1); }}
              style={{
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '13px',
                color: '#fff',
                cursor: 'pointer',
                outline: 'none'
              }}
            >
              <option value="" style={{ background: '#1e293b', color: '#fff' }}>All Countries</option>
              {topCountries.map(c => (
                <option
                  key={c.country}
                  value={c.country === 'Unknown' ? 'null' : c.country}
                  style={{ background: '#1e293b', color: '#fff' }}
                >
                  {c.country}
                </option>
              ))}
            </select>
          </div>
        </div>

        {loadingClicks ? (
          <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-secondary)' }}>Loading…</div>
        ) : clicks.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.08)', fontSize: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  <th
                    onClick={() => requestSort('clicked_at')}
                    style={{ padding: '10px 16px', fontWeight: '500', cursor: 'pointer', userSelect: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Time {getSortIcon('clicked_at')}
                    </div>
                  </th>
                  <th
                    onClick={() => requestSort('ip_address')}
                    style={{ padding: '10px 16px', fontWeight: '500', cursor: 'pointer', userSelect: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      IP Address {getSortIcon('ip_address')}
                    </div>
                  </th>
                  <th
                    onClick={() => requestSort('user_agent')}
                    style={{ padding: '10px 16px', fontWeight: '500', cursor: 'pointer', userSelect: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Browser {getSortIcon('user_agent')}
                    </div>
                  </th>
                  <th
                    onClick={() => requestSort('referer')}
                    style={{ padding: '10px 16px', fontWeight: '500', cursor: 'pointer', userSelect: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Referer {getSortIcon('referer')}
                    </div>
                  </th>
                  <th
                    onClick={() => requestSort('country')}
                    style={{ padding: '10px 16px', fontWeight: '500', cursor: 'pointer', userSelect: 'none' }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Country {getSortIcon('country')}
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedClicks.map((click) => (
                  <ClickRow key={click.id} click={click} />
                ))}
              </tbody>
            </table>

            {(totalClicksCount > CLICKS_PER_PAGE || currentPage > 1) && (
              <div style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Showing {Math.min(totalClicksCount, (currentPage - 1) * CLICKS_PER_PAGE + 1)}-{Math.min(totalClicksCount, currentPage * CLICKS_PER_PAGE)} of {totalClicksCount}
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    disabled={currentPage === 1}
                    onClick={() => setCurrentPage(p => p - 1)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      background: 'rgba(255,255,255,0.05)',
                      color: currentPage === 1 ? 'rgba(255,255,255,0.2)' : '#fff',
                      cursor: currentPage === 1 ? 'default' : 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Previous
                  </button>
                  <button
                    disabled={currentPage * CLICKS_PER_PAGE >= totalClicksCount}
                    onClick={() => setCurrentPage(p => p + 1)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      background: 'rgba(255,255,255,0.05)',
                      color: currentPage * CLICKS_PER_PAGE >= totalClicksCount ? 'rgba(255,255,255,0.2)' : '#fff',
                      cursor: currentPage * CLICKS_PER_PAGE >= totalClicksCount ? 'default' : 'pointer',
                      fontSize: '12px'
                    }}
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ textAlign: 'center', padding: '32px', color: 'var(--text-secondary)', fontSize: '14px' }}>
            No matching logs found.
          </div>
        )}
      </GlassCard>

      <style>{`
        .hover-row:hover { background: rgba(255,255,255,0.02); }
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .recharts-wrapper:focus { outline: none !important; }
        .recharts-surface:focus { outline: none !important; }
      `}</style>
    </div>
  );
};

export default LinkAnalytics;
