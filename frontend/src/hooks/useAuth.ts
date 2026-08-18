import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import { mergeGuestCartIntoBackend } from "@/hooks/useCart";
import { toast } from "@/store/toastStore";
import { getErrorMessage } from "@/api/client";

export function useAuth() {
  const { user, isAuthenticated, loginSuccess, clearAuth, refreshToken } = useAuthStore();
  const navigate = useNavigate();

  const loginMutation = useMutation({
    mutationFn: authApi.login,
    onSuccess: async (data) => {
      loginSuccess(data.user, data.access, data.refresh);
      await mergeGuestCartIntoBackend();
      toast.success(`Welcome back, ${data.user.username}.`);
      navigate("/");
    },
    onError: (err) => toast.error(getErrorMessage(err, "Invalid username or password.")),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (refreshToken) await authApi.logout(refreshToken);
    },
    onSettled: () => {
      clearAuth();
      toast.info("You've been signed out.");
      navigate("/");
    },
  });

  return {
    user,
    isAuthenticated,
    login: loginMutation.mutate,
    isLoggingIn: loginMutation.isPending,
    logout: logoutMutation.mutate,
  };
}
