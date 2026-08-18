import { apiClient } from "@/api/client";
import type { LoginResponse, User } from "@/types";

export const authApi = {
  register: async (payload: { username: string; phone_number: string; password: string }) => {
    const { data } = await apiClient.post<{ detail: string; phone_number: string }>(
      "/auth/register/",
      payload,
    );
    return data;
  },

  verifyOtp: async (payload: { phone_number: string; code: string }): Promise<User> => {
    const { data } = await apiClient.post<User>("/auth/verify-otp/", payload);
    return data;
  },

  login: async (payload: { username: string; password: string }): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>("/auth/login/", payload);
    return data;
  },

  logout: async (refresh: string) => {
    await apiClient.post("/auth/logout/", { refresh });
  },

  getProfile: async (): Promise<User> => {
    const { data } = await apiClient.get<User>("/profile/");
    return data;
  },

  changeUsername: async (username: string): Promise<User> => {
    const { data } = await apiClient.patch<User>("/profile/change-username/", { username });
    return data;
  },

  changePassword: async (payload: { current_password: string; new_password: string }) => {
    const { data } = await apiClient.post<{ detail: string }>("/profile/change-password/", payload);
    return data;
  },
};
