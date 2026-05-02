const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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
    // If body is FormData, let browser set Content-Type
    if (body instanceof FormData) {
      delete config.headers['Content-Type'];
      config.body = body;
    } else {
      config.body = JSON.stringify(body);
    }
  }

  const response = await fetch(`${API_URL}${endpoint}`, config);
  const data = await response.json().catch(() => null);

  if (response.ok) {
    return data;
  }

  // Auto logout on 401
  if (response.status === 401) {
    localStorage.removeItem('token');
    window.location.reload();
  }

  throw new Error(data?.detail || response.statusText || 'API Error');
};
