import { apiClient } from "@/api/client";
import type { Category, PaginatedResponse, Product, ProductDetail } from "@/types";

export interface ProductListParams {
  category?: string;
  popular?: boolean;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  ordering?: string;
  search?: string;
  page?: number;
}

export const productsApi = {
  listCategories: async (): Promise<Category[]> => {
    const { data } = await apiClient.get<Category[]>("/categories/");
    return data;
  },

  getCategory: async (slug: string): Promise<Category> => {
    const { data } = await apiClient.get<Category>(`/categories/${slug}/`);
    return data;
  },

  listProducts: async (params: ProductListParams = {}): Promise<PaginatedResponse<Product>> => {
    const { data } = await apiClient.get<PaginatedResponse<Product>>("/products/", { params });
    return data;
  },

  getProduct: async (slug: string): Promise<ProductDetail> => {
    const { data } = await apiClient.get<ProductDetail>(`/products/${slug}/`);
    return data;
  },
};
