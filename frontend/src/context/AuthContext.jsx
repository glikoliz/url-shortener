/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState } from 'react';
import { apiClient } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(() => localStorage.getItem('token'));
  const [user, setUser] = useState(() => {
    const t = localStorage.getItem('token');
    return t ? { token: t } : null;
  });
  const [loading] = useState(false);

  const login = async (username, password) => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);

    const data = await apiClient('/auth/login', {
      body: formData,
      method: 'POST',
    });

    setToken(data.access_token);
    setUser({ token: data.access_token });
    localStorage.setItem('token', data.access_token);
    return data;
  };

  const register = async (email, password) => {
    const data = await apiClient('/auth/register', {
      body: { email, password },
      method: 'POST',
    });
    return data;
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('token');
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
