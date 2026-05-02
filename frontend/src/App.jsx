import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import Login from './pages/Login';
import Register from './pages/Register';

const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" />;
  }

  return children;
};

const DashboardPlaceholder = () => {
  const { logout } = useAuth();
  return (
    <div style={{ padding: '40px', textAlign: 'center' }}>
      <h1>Dashboard (Under Construction)</h1>
      <button
        onClick={logout}
        style={{
          marginTop: '20px',
          padding: '10px 20px',
          background: 'var(--error-color)',
          color: 'white',
          borderRadius: '8px'
        }}
      >
        Logout
      </button>
    </div>
  );
};

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardPlaceholder />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
