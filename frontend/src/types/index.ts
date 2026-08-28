export interface Category {
  id: string;
  name: string;
  slug: string;
  description: string;
  image: string | null;
  ordering: number;
  is_active: boolean;
  product_count: number;
}

export interface Product {
  id: string;
  category: string;
  category_name: string;
  name: string;
  slug: string;
  short_description: string;
  image: string | null;
  price: string;
  in_stock: boolean;
  is_featured: boolean;
}

export interface ProductDetail {
  id: string;
  category: Category;
  name: string;
  slug: string;
  short_description: string;
  full_description: string;
  image: string | null;
  price: string;
  stock_quantity: number;
  delivery_estimate_days: number;
  is_available: boolean;
  is_featured: boolean;
  in_stock: boolean;
  created_at: string;
  updated_at: string;
}

export interface PaginatedResponse<T> {
  count: number;
  total_pages: number;
  current_page: number;
  page_size: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface User {
  id: number;
  username: string;
  phone_number: string;
  email: string | null;
  is_phone_verified: boolean;
  created_at: string;
}

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface LoginResponse extends AuthTokens {
  user: User;
}

export interface CartItem {
  id: number;
  product_name: string;
  product_slug: string;
  product_image: string | null;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface Cart {
  id: number;
  items: CartItem[];
  subtotal: string;
  total_items: number;
  updated_at: string;
}

export interface OrderItem {
  id: number;
  product: string | null;
  product_name: string;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export type OrderStatus = "PENDING" | "PAID" | "CANCELLED" | "SHIPPED";

export interface Order {
  id: string;
  status: OrderStatus;
  subtotal: string;
  tax_amount: string;
  shipping_amount: string;
  total_amount: string;
  shipping_address: string;
  items: OrderItem[];
  created_at: string;
}

export interface ApiError {
  detail?: string;
  [key: string]: unknown;
}

export type AgentMessageRole = "USER" | "ASSISTANT";

export interface AgentMessage {
  id: number | string;
  role: AgentMessageRole;
  content: string;
  created_at: string;
}

export interface AgentToolCall {
  tool_name: string;
  ok: boolean;
}

export interface AgentConversationDetail {
  conversation_id: string;
  state: string;
  messages: AgentMessage[];
}

export interface SendAgentMessageResponse {
  conversation_id: string;
  state: string;
  assistant_message: string;
  tool_calls: AgentToolCall[];
}
