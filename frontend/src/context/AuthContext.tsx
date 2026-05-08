import { createContext, useContext, type ReactNode } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../api/client';
import type { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<any>;
  register: (email: string, password: string) => Promise<any>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient();

  // Fetch user profile
  const { data: user, isLoading: loading, refetch: checkAuth } = useQuery({
    queryKey: ['user'],
    queryFn: async () => {
      try {
        return await apiClient('/auth/me');
      } catch {
        return null;
      }
    },
    staleTime: 5 * 60 * 1000, // Re-check user profile every 5 minutes
    gcTime: Infinity,
  });

  const loginMutation = useMutation({
    mutationFn: async ({ email, password }: any) => {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      return await apiClient('/auth/login', {
        body: formData,
        method: 'POST',
      });
    },
    onSuccess: () => {
      // Invalidate and refetch user profile after login
      queryClient.invalidateQueries({ queryKey: ['user'] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      await apiClient('/auth/logout', { method: 'POST' });
    },
    onSuccess: () => {
      queryClient.setQueryData(['user'], null);
      window.location.href = '/';
    },
  });

  const registerMutation = useMutation({
    mutationFn: async ({ email, password }: any) => {
      return await apiClient('/auth/register', {
        body: { email, password },
        method: 'POST',
      });
    },
  });

  const login = async (email: string, password: string) => {
    return loginMutation.mutateAsync({ email, password });
  };

  const register = async (email: string, password: string) => {
    await registerMutation.mutateAsync({ email, password });
    return login(email, password);
  };

  const logout = () => {
    logoutMutation.mutate();
  };

  return (
    <AuthContext.Provider value={{
      user: user ?? null,
      loading,
      login,
      register,
      logout,
      checkAuth: async () => { await checkAuth(); }
    }}>
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
