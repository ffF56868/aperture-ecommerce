import { apiClient } from "@/api/client";
import type {
  AgentConversationDetail,
  AfterSalesCase,
  ConfirmationExecutionResponse,
  ConfirmationRejectionResponse,
  SendAgentMessageResponse,
} from "@/types";

interface SendAgentMessagePayload {
  message: string;
  conversation_id?: string | null;
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
