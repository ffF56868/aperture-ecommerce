import { apiClient } from "@/api/client";

export interface ContactPayload {
  full_name: string;
  email: string;
  phone_number?: string;
  subject: string;
  message: string;
}

export const contactApi = {
  submit: async (payload: ContactPayload) => {
    const { data } = await apiClient.post("/contact/", payload);
    return data;
  },
};
