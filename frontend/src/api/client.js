const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

let isRefreshing = false;
let refreshSubscribers = [];

const subscribeTokenRefresh = (cb) => {
  refreshSubscribers.push(cb);
};

const onTokenRefreshed = (token) => {
  refreshSubscribers.map((cb) => cb(token));
  refreshSubscribers = [];
};

export const apiClient = async (endpoint, { body, ...customConfig } = {}) => {
  const token = localStorage.getItem('token');
  const headers = { 'Content-Type': 'application/json' };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const config = {
    method: body ? 'POST' : 'GET',
    ...customConfig,
    headers: {
      ...headers,
      ...customConfig.headers,
    },
  };

  if (body) {
    if (body instanceof FormData) {
      delete config.headers['Content-Type'];
      config.body = body;
    } else {
      config.body = JSON.stringify(body);
    }
  }

  try {
    const response = await fetch(`${API_URL}${endpoint}`, config);
    const data = await response.json().catch(() => null);

    if (response.ok) {
      return data;
    }

    // Handle 401 Unauthorized
    if (response.status === 401 && !endpoint.includes('/auth/login') && !endpoint.includes('/auth/refresh')) {
      const refreshToken = localStorage.getItem('refreshToken');

      if (!refreshToken) {
        logout();
        throw new Error('Session expired');
      }

      if (!isRefreshing) {
        isRefreshing = true;
        try {
          const refreshResponse = await fetch(`${API_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: refreshToken }),
          });

          if (refreshResponse.ok) {
            const { access_token, refresh_token } = await refreshResponse.json();
            localStorage.setItem('token', access_token);
            localStorage.setItem('refreshToken', refresh_token);
            isRefreshing = false;
            onTokenRefreshed(access_token);

            config.headers.Authorization = `Bearer ${access_token}`;
            const retryResponse = await fetch(`${API_URL}${endpoint}`, config);
            return await retryResponse.json();
          } else {
            isRefreshing = false;
            logout();
            throw new Error('Session expired');
          }
        } catch (e) {
          isRefreshing = false;
          logout();
          throw e;
        }
      } else {
        // Wait for refresh to complete and retry
        const newToken = await new Promise((resolve) => {
          subscribeTokenRefresh((token) => resolve(token));
        });

        config.headers.Authorization = `Bearer ${newToken}`;
        const retryResponse = await fetch(`${API_URL}${endpoint}`, config);
        return await retryResponse.json();
      }
    }

    // Handle other errors
    let errorMessage = response.statusText || 'API Error';
    if (data?.detail) {
      if (typeof data.detail === 'string') {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail.map(e => `${e.loc[e.loc.length - 1]}: ${e.msg}`).join('; ');
      }
    }
    throw new Error(errorMessage);

  } catch (error) {
    if (error.message === 'Session expired') {
      logout();
    }
    throw error;
  }
};

const logout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('refreshToken');
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
};
