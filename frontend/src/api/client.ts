import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { API_BASE_URL } from "@/constants";
import { useAuthStore } from "@/store/authStore";

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use((config) => {
  const { accessToken } = useAuthStore.getState();
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// Refresh is coalesced: if multiple requests 401 at once, only one refresh
// call is made and the rest wait on the same in-flight promise.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const { refreshToken, setTokens, clearAuth } = useAuthStore.getState();
  if (!refreshToken) return null;

  try {
    const { data } = await axios.post<{ access: string }>(`${API_BASE_URL}/auth/token/refresh/`, {
      refresh: refreshToken,
    });
    setTokens(data.access, refreshToken);
    return data.access;
  } catch {
    clearAuth();
    return null;
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableConfig | undefined;

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      originalRequest._retry = true;

      refreshPromise ??= refreshAccessToken().finally(() => {
        refreshPromise = null;
      });

      const newAccessToken = await refreshPromise;
      if (newAccessToken) {
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
        return apiClient(originalRequest);
      }
    }

    return Promise.reject(error);
  },
);

export function getErrorMessage(
  error: unknown,
  fallback = "操作失败，请稍后重试。",
): string {
  if (axios.isAxiosError(error)) {
    const rawData = error.response?.data;
    if (typeof rawData === "string") {
      try {
        const parsed = JSON.parse(rawData) as Record<string, unknown>;
        if (typeof parsed.detail === "string") return parsed.detail;
      } catch {
        // HTML and plain-text server errors are not safe user-facing messages.
      }
      return fallback;
    }
    const data = rawData as Record<string, unknown> | undefined;
    if (!data) return fallback;
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data) && typeof data[0] === "string") return data[0];
    const firstKey = Object.keys(data)[0];
    if (firstKey) {
      const value = data[firstKey];
      if (Array.isArray(value) && typeof value[0] === "string") return value[0];
      if (typeof value === "string") return value;
    }
  }
  return fallback;
}
