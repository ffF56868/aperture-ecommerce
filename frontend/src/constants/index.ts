export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";

export const BRAND = {
  name: "Aperture",
  tagline: "Precision, made to order.",
} as const;

export const NAV_LINKS = [
  { label: "Shop", to: "/products" },
  { label: "About", to: "/about" },
  { label: "Contact", to: "/contact" },
] as const;

export const ORDER_STATUS_LABEL: Record<string, string> = {
  PENDING: "Pending",
  PAID: "Paid",
  CANCELLED: "Cancelled",
  SHIPPED: "Shipped",
};

export const ORDER_STATUS_COLOR: Record<string, string> = {
  PENDING: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  PAID: "text-success bg-success/10 border-success/20",
  CANCELLED: "text-danger bg-danger/10 border-danger/20",
  SHIPPED: "text-accent-soft bg-accent/10 border-accent/20",
};
