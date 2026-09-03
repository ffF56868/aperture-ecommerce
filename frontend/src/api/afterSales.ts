import { apiClient } from "@/api/client";
import type {
  AgentConversationDetail,
  AfterSalesCase,
  AfterSalesNotification,
  AfterSalesNotificationList,
  AgentRunDetail,
  AgentRunListResponse,
  ConfirmationExecutionResponse,
  ConfirmationRejectionResponse,
  SendAgentMessageResponse,
  StaffAfterSalesCase,
  StaffAfterSalesCaseUpdatePayload,
  StaffOrder,
} from "@/types";

interface SendAgentMessagePayload {
  message: string;
  conversation_id?: string | null;
}

export interface StaffCaseFilters {
  status?: string;
  priority?: string;
  search?: string;
}

export interface StaffOrderFilters {
  status?: string;
  search?: string;
}

export interface AgentRunFilters {
  status?: string;
  intent?: string;
  search?: string;
}

export const afterSalesApi = {
  sendMessage: async (payload: SendAgentMessagePayload): Promise<SendAgentMessageResponse> => {
    const { data } = await apiClient.post<SendAgentMessageResponse>("/after-sales/conversations/", payload);
    return data;
  },

  getConversation: async (conversationId: string): Promise<AgentConversationDetail> => {
    const { data } = await apiClient.get<AgentConversationDetail>(`/after-sales/conversations/${conversationId}/`);
    return data;
  },

  getCases: async (): Promise<AfterSalesCase[]> => {
    const { data } = await apiClient.get<AfterSalesCase[]>("/after-sales/cases/");
    return data;
  },

  listNotifications: async (): Promise<AfterSalesNotificationList> => {
    const { data } = await apiClient.get<AfterSalesNotificationList>("/after-sales/notifications/");
    return data;
  },

  markNotificationRead: async (notificationId: string): Promise<AfterSalesNotification> => {
    const { data } = await apiClient.post<AfterSalesNotification>(
      `/after-sales/notifications/${notificationId}/read/`,
    );
    return data;
  },

  markAllNotificationsRead: async (): Promise<{ updated_count: number; read_at: string }> => {
    const { data } = await apiClient.post<{ updated_count: number; read_at: string }>(
      "/after-sales/notifications/read-all/",
    );
    return data;
  },

  listStaffCases: async (filters: StaffCaseFilters = {}): Promise<StaffAfterSalesCase[]> => {
    const { data } = await apiClient.get<StaffAfterSalesCase[]>("/after-sales/staff/cases/", {
      params: filters,
    });
    return data;
  },

  getStaffCase: async (caseId: string): Promise<StaffAfterSalesCase> => {
    const { data } = await apiClient.get<StaffAfterSalesCase>(`/after-sales/staff/cases/${caseId}/`);
    return data;
  },

  updateStaffCase: async (
    caseId: string,
    payload: StaffAfterSalesCaseUpdatePayload,
  ): Promise<StaffAfterSalesCase> => {
    const { data } = await apiClient.patch<StaffAfterSalesCase>(
      `/after-sales/staff/cases/${caseId}/`,
      payload,
    );
    return data;
  },

  shipStaffCaseOrder: async (caseId: string): Promise<StaffAfterSalesCase> => {
    const { data } = await apiClient.post<StaffAfterSalesCase>(
      `/after-sales/staff/cases/${caseId}/ship-order/`,
    );
    return data;
  },

  refundStaffCaseOrder: async (caseId: string): Promise<StaffAfterSalesCase> => {
    const { data } = await apiClient.post<StaffAfterSalesCase>(
      `/after-sales/staff/cases/${caseId}/refund-order/`,
    );
    return data;
  },

  listStaffOrders: async (filters: StaffOrderFilters = {}): Promise<StaffOrder[]> => {
    const { data } = await apiClient.get<StaffOrder[]>("/after-sales/staff/orders/", {
      params: filters,
    });
    return data;
  },

  shipStaffOrder: async (orderId: string): Promise<StaffOrder> => {
    const { data } = await apiClient.post<StaffOrder>(`/after-sales/staff/orders/${orderId}/ship/`);
    return data;
  },

  listStaffAgentRuns: async (filters: AgentRunFilters = {}): Promise<AgentRunListResponse> => {
    const { data } = await apiClient.get<AgentRunListResponse>("/after-sales/staff/agent-runs/", {
      params: filters,
    });
    return data;
  },

  getStaffAgentRun: async (runId: string): Promise<AgentRunDetail> => {
    const { data } = await apiClient.get<AgentRunDetail>(`/after-sales/staff/agent-runs/${runId}/`);
    return data;
  },

  confirmConfirmation: async (confirmationId: string): Promise<ConfirmationExecutionResponse> => {
    const { data } = await apiClient.post<ConfirmationExecutionResponse>(
      `/after-sales/confirmations/${confirmationId}/confirm/`,
    );
    return data;
  },

  rejectConfirmation: async (confirmationId: string): Promise<ConfirmationRejectionResponse> => {
    const { data } = await apiClient.post<ConfirmationRejectionResponse>(
      `/after-sales/confirmations/${confirmationId}/reject/`,
    );
    return data;
  },
};
