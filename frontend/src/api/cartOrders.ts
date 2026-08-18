import { apiClient } from "@/api/client";
import type { Cart, Order, PaginatedResponse } from "@/types";

export const cartApi = {
  getCart: async (): Promise<Cart> => {
    const { data } = await apiClient.get<Cart>("/cart/");
    return data;
  },

  addItem: async (productId: string, quantity = 1): Promise<Cart> => {
    const { data } = await apiClient.post<Cart>("/cart/add/", { product_id: productId, quantity });
    return data;
  },

  updateItem: async (itemId: number, quantity: number): Promise<Cart> => {
    const { data } = await apiClient.patch<Cart>(`/cart/items/${itemId}/`, { quantity });
    return data;
  },

  removeItem: async (itemId: number): Promise<Cart> => {
    const { data } = await apiClient.delete<Cart>(`/cart/items/${itemId}/remove/`);
    return data;
  },

  clear: async (): Promise<Cart> => {
    const { data } = await apiClient.delete<Cart>("/cart/clear/");
    return data;
  },
};

export const ordersApi = {
  checkout: async (payload: {
    shipping_address: string;
    tax_rate?: string;
    shipping_amount?: string;
  }): Promise<Order> => {
    const { data } = await apiClient.post<Order>("/orders/checkout/", payload);
    return data;
  },

  listOrders: async (): Promise<PaginatedResponse<Order>> => {
    const { data } = await apiClient.get<PaginatedResponse<Order>>("/orders/");
    return data;
  },
};

export const paymentsApi = {
  initiate: async (
    orderId: string,
  ): Promise<{ transaction_id: string; amount: string; status: string; redirect_url: string }> => {
    const { data } = await apiClient.post("/payments/initiate/", { order_id: orderId });
    return data;
  },

  verify: async (
    transactionId: string,
    success = true,
  ): Promise<{ transaction_id: string; status: string; order_status: string }> => {
    const { data } = await apiClient.post("/payments/verify/", {
      transaction_id: transactionId,
      success,
    });
    return data;
  },
};
