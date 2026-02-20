import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
} from 'react';
import type { ReactNode } from 'react';
import api, { setAccessToken } from '@/services/api';
import type { User, LoginCredentials } from '@/types/auth';

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, attempt to restore session via /auth/me (uses refresh cookie if access token expired)
  useEffect(() => {
    api
      .get<User>('/auth/me')
      .then(({ data }) => setUser(data))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async ({ email, password }: LoginCredentials) => {
    // OAuth2PasswordRequestForm requires application/x-www-form-urlencoded
    const formData = new URLSearchParams();
    formData.append('username', email); // FastAPI OAuth2 uses 'username' field
    formData.append('password', password);

    const { data: tokenData } = await api.post<{ access_token: string }>(
      '/auth/login',
      formData,
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    );
    setAccessToken(tokenData.access_token);

    // Fetch user profile to populate context
    const { data: profile } = await api.get<User>('/auth/me');
    setUser(profile);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } finally {
      setAccessToken(null);
      setUser(null);
    }
  }, []);

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
