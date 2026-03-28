import axios, { AxiosError } from "axios";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

// Access token stored in memory only — never localStorage or sessionStorage
let _accessToken: string | null = null;

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true, // Sends HttpOnly refresh_token cookie automatically
});

// Attach access token to every request
api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

// On 401, attempt a single token refresh then retry the original request
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as typeof error.config & { _retry?: boolean };
    if (
      error.response?.status === 401 &&
      originalRequest &&
      !originalRequest._retry &&
      !originalRequest.url?.includes("/auth/refresh") &&
      !originalRequest.url?.includes("/auth/login")
    ) {
      originalRequest._retry = true;
      try {
        const { data } = await api.post<{ access_token: string }>("/auth/refresh");
        setAccessToken(data.access_token);
        originalRequest.headers!["Authorization"] = `Bearer ${data.access_token}`;
        return api(originalRequest);
      } catch {
        // Refresh failed — clear token, caller handles redirect
        setAccessToken(null);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
