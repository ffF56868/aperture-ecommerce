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
  is_staff: boolean;
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

export type OrderStatus = "PENDING" | "PAID" | "CANCELLED" | "SHIPPED" | "REFUNDED";

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

export interface AgentCollaborationRole {
  key: string;
  label: string;
  responsibility: string;
}

export interface AfterSalesOrderSummary {
  id: string;
  status: OrderStatus;
  total_amount: string;
  items: Array<Pick<OrderItem, "product_name" | "quantity">>;
}

export interface AfterSalesConfirmation {
  id: string;
  status: "PENDING" | "REJECTED" | "EXPIRED" | "EXECUTED" | "FAILED";
  action_type: "REFUND_REQUEST" | "RETURN_REFUND_REQUEST" | "CANCEL_ORDER";
  action_label: string;
  policy_key: string;
  policy_name: string;
  reason: string;
  order: AfterSalesOrderSummary | null;
  expires_at: string;
  created_at: string;
}

export interface AfterSalesCase {
  id: string;
  case_number: string;
  case_type: string;
  case_type_label: string;
  status: string;
  status_label: string;
  priority: "LOW" | "NORMAL" | "HIGH" | "URGENT";
  reason: string;
  order: AfterSalesOrderSummary | null;
  created_at: string;
}

export type AfterSalesNotificationEvent =
  | "CASE_CREATED"
  | "CASE_APPROVED"
  | "CASE_REJECTED"
  | "NEED_CUSTOMER_INFO";

export type AfterSalesNotificationEmailStatus = "PENDING" | "SENT" | "SKIPPED" | "FAILED";

export interface AfterSalesNotification {
  id: string;
  event_type: AfterSalesNotificationEvent;
  title: string;
  message: string;
  action_url: string;
  is_read: boolean;
  read_at: string | null;
  email_status: AfterSalesNotificationEmailStatus;
  created_at: string;
  case_number: string | null;
}

export interface AfterSalesNotificationList {
  unread_count: number;
  notifications: AfterSalesNotification[];
}

export type AfterSalesCaseStatus =
  | "PENDING_REVIEW"
  | "IN_REVIEW"
  | "NEED_CUSTOMER_INFO"
  | "APPROVED"
  | "REJECTED"
  | "CLOSED"
  | "CANCELLED";

export interface StaffCustomer {
  id: number;
  username: string;
  phone_number: string;
}

export interface StaffAssignee {
  id: number;
  username: string;
}

export interface StaffConversationMessage extends AgentMessage {
  role: AgentMessageRole;
}

export interface StaffConversation {
  id: string;
  state: string;
  summary: string;
  messages: StaffConversationMessage[];
}

export interface StaffAfterSalesCase extends AfterSalesCase {
  status: AfterSalesCaseStatus;
  updated_at: string;
  resolved_at: string | null;
  agent_summary: string;
  staff_note: string;
  user: StaffCustomer;
  assigned_to: StaffAssignee | null;
  conversation?: StaffConversation | null;
}

export interface StaffAfterSalesCaseUpdatePayload {
  status?: AfterSalesCaseStatus;
  staff_note?: string;
}

export interface StaffOrderItem {
  product_name: string;
  unit_price: string;
  quantity: number;
  line_total: string;
}

export interface StaffOrder {
  id: string;
  status: OrderStatus;
  status_label: string;
  total_amount: string;
  shipping_address: string;
  user: StaffCustomer;
  items: StaffOrderItem[];
  created_at: string;
  updated_at: string;
}

export interface AgentConversationDetail {
  conversation_id: string;
  state: string;
  messages: AgentMessage[];
  collaboration_plan: AgentCollaborationRole[];
  pending_confirmation: AfterSalesConfirmation | null;
  recent_cases: AfterSalesCase[];
}

export interface SendAgentMessageResponse {
  conversation_id: string;
  state: string;
  assistant_message: string;
  tool_calls: AgentToolCall[];
  collaboration_plan: AgentCollaborationRole[];
  pending_confirmation: AfterSalesConfirmation | null;
  recent_cases: AfterSalesCase[];
}

export interface ConfirmationExecutionResponse {
  confirmation: AfterSalesConfirmation;
  after_sales_case: AfterSalesCase | null;
  already_executed: boolean;
  message: string;
}

export interface ConfirmationRejectionResponse {
  confirmation: AfterSalesConfirmation;
  message: string;
}

export type AgentRunStatus =
  | "RUNNING"
  | "SUCCEEDED"
  | "AWAITING_CONFIRMATION"
  | "ESCALATED"
  | "BLOCKED"
  | "FAILED";

export interface AgentRunUser {
  id: number;
  username: string;
  phone_number: string;
}

export interface AgentRunListItem {
  id: string;
  conversation_id: string | null;
  user: AgentRunUser | null;
  model_name: string;
  current_intent: string;
  input_preview: string;
  status: AgentRunStatus;
  status_label: string;
  tool_rounds: number;
  tool_call_count: number;
  successful_tool_count: number;
  failed_tool_count: number;
  denied_tool_count: number;
  total_tokens: number | null;
  duration_ms: number | null;
  started_at: string;
  finished_at: string | null;
}

export interface AgentRunSummary {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  blocked_runs: number;
  escalated_runs: number;
  awaiting_confirmation_runs: number;
  success_rate: number;
  average_duration_ms: number;
  total_tool_calls: number;
  failed_tool_calls: number;
  denied_tool_calls: number;
  total_tokens: number | null;
}

export interface AgentRunListResponse {
  summary: AgentRunSummary;
  runs: AgentRunListItem[];
}

export interface AgentRunEvent {
  id: string;
  event_type: string;
  status: string;
  sequence: number;
  name: string;
  detail: Record<string, unknown>;
  duration_ms: number | null;
  created_at: string;
}

export interface AgentRunToolExecution {
  id: string;
  tool_name: string;
  agent_role: string;
  action_kind: string;
  status: string;
  initiated_by: string;
  sanitized_arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  error_code: string;
  duration_ms: number | null;
  created_at: string;
}

export interface AgentRunDetail extends AgentRunListItem {
  input_message: string;
  assistant_message: string;
  agent_roles: Array<Record<string, string>>;
  failure_code: string;
  failure_message: string;
  response_id: string;
  confirmation_request_id: string | null;
  events: AgentRunEvent[];
  tool_executions: AgentRunToolExecution[];
}

export interface AgentEvaluationMetric {
  passed?: number;
  total?: number;
  failed?: number;
  rate?: number;
  value?: number;
  unit?: string;
}

export interface AgentEvaluationCaseResult {
  id: string;
  case_id: string;
  category: string;
  description: string;
  message: string;
  expected_intent: string;
  actual_intent: string;
  expected_tools: string[];
  actual_tools: string[];
  expected_arguments: Array<Record<string, unknown>>;
  actual_arguments: Array<Record<string, unknown>>;
  passed: boolean;
  intent_passed: boolean;
  tool_selection_passed: boolean;
  parameter_applicable: boolean;
  parameter_passed: boolean | null;
  authorization_passed: boolean;
  unauthorized_case: boolean;
  unauthorized_blocked: boolean;
  dangerous_case: boolean;
  dangerous_blocked: boolean;
  response_compliance_passed: boolean;
  human_escalated: boolean;
  failed: boolean;
  response_time_ms: number;
  actual_error_codes: string[];
  assistant_message: string;
  failures: string[];
}

export interface AgentEvaluationRunListItem {
  id: string;
  status: string;
  status_label: string;
  trigger: string;
  trigger_label: string;
  mode: string;
  started_at: string;
  finished_at: string | null;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  average_response_ms: number;
}

export interface AgentEvaluationRunListResponse {
  summary: {
    total_runs: number;
    latest_run_id: string | null;
    latest_started_at: string | null;
  };
  runs: AgentEvaluationRunListItem[];
}

export interface AgentEvaluationRunDetail extends AgentEvaluationRunListItem {
  metrics: Record<string, AgentEvaluationMetric>;
  cases: AgentEvaluationCaseResult[];
  error_message: string;
}

export type KnowledgeDocumentSourceType = "TEXT" | "FILE" | "WEBPAGE";
export type KnowledgeDocumentIndexStatus = "PENDING" | "PROCESSING" | "READY" | "DEGRADED" | "FAILED";

export interface StaffKnowledgeDocument {
  id: string;
  title: string;
  slug: string;
  category: string;
  source_label: string;
  source_type: KnowledgeDocumentSourceType;
  source_type_label: string;
  source_url: string;
  file_name: string;
  file_url: string | null;
  content_preview: string;
  product: { id: string; name: string } | null;
  product_category: { id: string; name: string } | null;
  is_published: boolean;
  index_status: KnowledgeDocumentIndexStatus;
  index_status_label: string;
  index_error: string;
  chunk_count: number;
  indexed_at: string | null;
  uploaded_by: { id: number; username: string } | null;
  created_at: string;
  updated_at: string;
}

export interface StaffKnowledgeDocumentListResponse {
  summary: { total: number; ready: number; degraded: number; pending: number; processing: number; failed: number };
  documents: StaffKnowledgeDocument[];
}

export interface StaffKnowledgeMatch {
  document_id: string;
  chunk_id: string;
  title: string;
  source_label: string;
  source_type: KnowledgeDocumentSourceType;
  source_url: string;
  category: string;
  excerpt: string;
  similarity: number;
  sequence: number;
}

export interface StaffKnowledgeSearchResponse {
  question: string;
  matches: StaffKnowledgeMatch[];
  requires_human_escalation: boolean;
  message: string;
}
