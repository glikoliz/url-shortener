import { useState, useEffect, useCallback, useMemo } from 'react';
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
import {
  ArrowLeft,
  MousePointerClick,
  Globe,
  Link2,
  RefreshCw,
  ChevronUp,
  ChevronDown,
  ArrowUpDown,
} from 'lucide-react';
import { apiClient } from '../api/client';
import GlassCard from '../components/GlassCard';


const fmtDate = (iso) =>
  new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

const parseUa = (ua) => {
  if (!ua) return 'Unknown';
  const browsers = [
    ['Edg', 'Edge'],
    ['OPR', 'Opera'],
    ['Chrome', 'Chrome'],
    ['Firefox', 'Firefox'],
    ['Safari', 'Safari'],
  ];
  for (const [token, name] of browsers) {
    if (ua.includes(token)) return name;
  }
  return 'Other';
};


const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
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
      <p style={{ color: 'var(--text-secondary)', marginBottom: '4px' }}>{label}</p>
      <p style={{ color: 'var(--accent-color)', fontWeight: 600 }}>{payload[0].value} clicks</p>
    </div>
  );
};


const StatCard = ({ icon: Icon, label, value, color }) => (
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


const ClickRow = ({ click }) => (
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
      {click.country || 'Unknown'}
    </td>
  </tr>
);


const LinkAnalytics = () => {
  const { code } = useParams();
  const navigate = useNavigate();

  const [stats, setStats] = useState(null);
  const [clicks, setClicks] = useState([]);
  const [loadingStats, setLoadingStats] = useState(true);
  const [loadingClicks, setLoadingClicks] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [sortConfig, setSortConfig] = useState({ key: 'clicked_at', direction: 'desc' });
  const [selectedGranularity, setSelectedGranularity] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalClicks, setTotalClicks] = useState(0);
  const [ipFilter, setIpFilter] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const CLICKS_PER_PAGE = 25;

  const fetchAll = useCallback(async (gran = selectedGranularity, page = currentPage, ip = ipFilter, country = countryFilter) => {
    try {
      const skip = (page - 1) * CLICKS_PER_PAGE;
      const statsUrl = gran ? `/links/${code}/stats?granularity=${gran}` : `/links/${code}/stats`;
      const clicksUrl = `/links/${code}/clicks?limit=${CLICKS_PER_PAGE}&skip=${skip}&ip=${ip}&country=${country}`;

      const [s, cData] = await Promise.all([
        apiClient(statsUrl),
        apiClient(clicksUrl),
      ]);
      setStats(s);
      setClicks(cData.items);
      setTotalClicks(cData.total);
    } catch {
      /* handled by apiClient */
    } finally {
      setLoadingStats(false);
      setLoadingClicks(false);
      setRefreshing(false);
    }
  }, [code, selectedGranularity, currentPage, ipFilter, countryFilter]);

  useEffect(() => {
    const timer = setTimeout(() => {
      fetchAll();
    }, 400);
    return () => clearTimeout(timer);
  }, [fetchAll, ipFilter, countryFilter, currentPage]);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchAll();
  };

  const topCountry = stats?.top_countries?.[0]?.country || 'Unknown';
  const uniqueIps = new Set(clicks.map((c) => c.ip_address)).size;

  const requestSort = (key) => {
    let direction = 'asc';
    if (sortConfig.key === key && sortConfig.direction === 'asc') {
      direction = 'desc';
    }
    setSortConfig({ key, direction });
  };

  const sortedClicks = useMemo(() => {
    let sortableItems = [...clicks];
    if (sortConfig.key !== null) {
      sortableItems.sort((a, b) => {
        let aVal = a[sortConfig.key] || '';
        let bVal = b[sortConfig.key] || '';

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

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return <ArrowUpDown size={14} style={{ opacity: 0.3 }} />;
    return sortConfig.direction === 'asc' ? <ChevronUp size={14} color="var(--accent-color)" /> : <ChevronDown size={14} color="var(--accent-color)" />;
  };

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
          <h1 style={{ fontSize: '22px', fontWeight: '700' }}>
            Analytics —{' '}
            <span style={{ color: 'var(--accent-color)' }}>{code}</span>
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Click statistics for your short link
          </p>
        </div>

        <button
          onClick={handleRefresh}
          disabled={refreshing}
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
            opacity: refreshing ? 0.6 : 1,
          }}
        >
          <RefreshCw size={15} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
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
          <StatCard icon={Globe} label="Unique IPs" value={uniqueIps} color="#60a5fa" />
          <StatCard icon={Link2} label="Top Country" value={topCountry} color="#34d399" />
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
        ) : stats?.clicks_by_day?.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={stats.clicks_by_day} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="clicksGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="var(--accent-color)" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="var(--accent-color)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: '#8b8e98' }} />
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
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
        {/* Top Referers */}
        <GlassCard>
          <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>Top Sources</h2>
          {stats?.top_referers?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={stats.top_referers.slice(0, 6)}
                layout="vertical"
                margin={{ top: 0, right: 10, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#8b8e98' }} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="referer"
                  width={80}
                  tick={{ fontSize: 11, fill: '#8b8e98' }}
                  tickFormatter={(v) => (v.length > 12 ? v.slice(0, 12) + '…' : v)}
                />
                <Tooltip
                  formatter={(v) => [v, 'clicks']}
                  contentStyle={{ background: 'rgba(11,12,16,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '13px' }}
                />
                <Bar dataKey="clicks" fill="#60a5fa" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>
              No data yet
            </div>
          )}
        </GlassCard>

        {/* Top Countries */}
        <GlassCard>
          <h2 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '16px' }}>Top Countries</h2>
          {stats?.top_countries?.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart
                data={stats.top_countries.slice(0, 6)}
                layout="vertical"
                margin={{ top: 0, right: 10, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#8b8e98' }} allowDecimals={false} />
                <YAxis
                  type="category"
                  dataKey="country"
                  width={70}
                  tick={{ fontSize: 11, fill: '#8b8e98' }}
                />
                <Tooltip
                  formatter={(v) => [v, 'clicks']}
                  contentStyle={{ background: 'rgba(11,12,16,0.95)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontSize: '13px' }}
                />
                <Bar dataKey="clicks" fill="#34d399" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: '200px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', fontSize: '14px' }}>
              No data yet
            </div>
          )}
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
              {stats?.top_countries?.map(c => (
                <option
                  key={c.country || 'null'}
                  value={c.country || 'null'}
                  style={{ background: '#1e293b', color: '#fff' }}
                >
                  {c.country || 'Unknown'}
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

            {(totalClicks > CLICKS_PER_PAGE || currentPage > 1) && (
              <div style={{ padding: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid rgba(255,255,255,0.04)' }}>
                <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                  Showing {Math.min(totalClicks, (currentPage - 1) * CLICKS_PER_PAGE + 1)}-{Math.min(totalClicks, currentPage * CLICKS_PER_PAGE)} of {totalClicks}
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
                    disabled={currentPage * CLICKS_PER_PAGE >= totalClicks}
                    onClick={() => setCurrentPage(p => p + 1)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid rgba(255,255,255,0.1)',
                      background: 'rgba(255,255,255,0.05)',
                      color: currentPage * CLICKS_PER_PAGE >= totalClicks ? 'rgba(255,255,255,0.2)' : '#fff',
                      cursor: currentPage * CLICKS_PER_PAGE >= totalClicks ? 'default' : 'pointer',
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
      `}</style>
    </div>
  );
};

export default LinkAnalytics;
