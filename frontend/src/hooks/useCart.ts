import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cartApi } from "@/api/cartOrders";
import { useAuthStore } from "@/store/authStore";
import { useCartStore, type CartableProduct } from "@/store/cartStore";
import { toast } from "@/store/toastStore";
import { getErrorMessage } from "@/api/client";

const CART_QUERY_KEY = ["cart"];

export function useCart() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const queryClient = useQueryClient();
  const guest = useCartStore();

  const cartQuery = useQuery({
    queryKey: CART_QUERY_KEY,
    queryFn: cartApi.getCart,
    enabled: isAuthenticated,
    staleTime: 0,
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: CART_QUERY_KEY });

  const addMutation = useMutation({
    mutationFn: ({ productId, quantity }: { productId: string; quantity: number }) =>
      cartApi.addItem(productId, quantity),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, "Could not add item to cart.")),
  });

  const updateMutation = useMutation({
    mutationFn: ({ itemId, quantity }: { itemId: number; quantity: number }) =>
      cartApi.updateItem(itemId, quantity),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, "Could not update quantity.")),
  });

  const removeMutation = useMutation({
    mutationFn: (itemId: number) => cartApi.removeItem(itemId),
    onSuccess: invalidate,
    onError: (err) => toast.error(getErrorMessage(err, "Could not remove item.")),
  });

  const clearMutation = useMutation({
    mutationFn: cartApi.clear,
    onSuccess: invalidate,
  });

  const addItem = (product: CartableProduct, quantity = 1) => {
    if (isAuthenticated) {
      addMutation.mutate({ productId: product.id, quantity });
    } else {
      guest.addItem(product, quantity);
    }
    toast.success(`Added "${product.name}" to cart.`);
  };

  if (isAuthenticated) {
    const cart = cartQuery.data;
    return {
      items: cart?.items ?? [],
      subtotal: cart ? parseFloat(cart.subtotal) : 0,
      totalItems: cart?.total_items ?? 0,
      isLoading: cartQuery.isLoading,
      addItem,
      updateQuantity: (itemId: number | string, quantity: number) =>
        updateMutation.mutate({ itemId: Number(itemId), quantity }),
      removeItem: (itemId: number | string) => removeMutation.mutate(Number(itemId)),
      clear: () => clearMutation.mutate(),
      isAuthenticated: true as const,
    };
  }

  return {
    items: guest.items.map((i) => ({
      id: i.productId as number | string,
      product_name: i.name,
      product_slug: i.slug,
      product_image: i.image,
      unit_price: i.price,
      quantity: i.quantity,
      line_total: (parseFloat(i.price) * i.quantity).toFixed(2),
    })),
    subtotal: guest.subtotal(),
    totalItems: guest.totalItems(),
    isLoading: false,
    addItem,
    updateQuantity: (productId: number | string, quantity: number) =>
      guest.updateQuantity(String(productId), quantity),
    removeItem: (productId: number | string) => guest.removeItem(String(productId)),
    clear: () => guest.clear(),
    isAuthenticated: false as const,
  };
}

/** Merges the guest's locally-held cart into the backend cart right after login. */
export async function mergeGuestCartIntoBackend() {
  const guest = useCartStore.getState();
  if (guest.items.length === 0) return;

  await Promise.all(guest.items.map((item) => cartApi.addItem(item.productId, item.quantity)));
  guest.clear();
}
