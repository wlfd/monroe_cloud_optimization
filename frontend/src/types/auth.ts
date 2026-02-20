export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: 'admin' | 'devops' | 'finance' | 'viewer';
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface LoginCredentials {
  email: string;
  password: string;
}
