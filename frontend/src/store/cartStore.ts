import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Product, ProductDetail as ProductDetailType } from "@/types";

export type CartableProduct = Pick<Product | ProductDetailType, "id" | "name" | "slug" | "image" | "price">;

export interface GuestCartItem {
  productId: string;
  name: string;
  slug: string;
  image: string | null;
  price: string;
  quantity: number;
}

interface CartState {
  items: GuestCartItem[];
  addItem: (product: CartableProduct, quantity?: number) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  removeItem: (productId: string) => void;
  clear: () => void;
  subtotal: () => number;
  totalItems: () => number;
}

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      items: [],
      addItem: (product, quantity = 1) =>
        set((state) => {
          const existing = state.items.find((i) => i.productId === product.id);
          if (existing) {
            return {
              items: state.items.map((i) =>
                i.productId === product.id ? { ...i, quantity: i.quantity + quantity } : i,
              ),
            };
          }
          return {
            items: [
              ...state.items,
              {
                productId: product.id,
                name: product.name,
                slug: product.slug,
                image: product.image,
                price: product.price,
                quantity,
              },
            ],
          };
        }),
      updateQuantity: (productId, quantity) =>
        set((state) => ({
          items: state.items.map((i) => (i.productId === productId ? { ...i, quantity } : i)),
        })),
      removeItem: (productId) =>
        set((state) => ({ items: state.items.filter((i) => i.productId !== productId) })),
      clear: () => set({ items: [] }),
      subtotal: () => get().items.reduce((sum, i) => sum + parseFloat(i.price) * i.quantity, 0),
      totalItems: () => get().items.reduce((sum, i) => sum + i.quantity, 0),
    }),
    { name: "aperture-guest-cart" },
  ),
);
