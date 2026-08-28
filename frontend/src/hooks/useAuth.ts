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
      toast.success(`欢迎回来，${data.user.username}。`);
      navigate("/");
    },
    onError: (err) => toast.error(getErrorMessage(err, "用户名或密码不正确。")),
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (refreshToken) await authApi.logout(refreshToken);
    },
    onSettled: () => {
      clearAuth();
      toast.info("你已退出登录。 ");
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
