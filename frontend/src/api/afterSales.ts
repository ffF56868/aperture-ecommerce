import { apiClient } from "@/api/client";
import type { AgentConversationDetail, SendAgentMessageResponse } from "@/types";

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
};
