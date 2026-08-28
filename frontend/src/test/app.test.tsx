import { describe, expect, it, vi, beforeAll } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { App } from "@/App";

vi.mock("@/api/products", () => ({
  productsApi: {
    listCategories: vi.fn().mockResolvedValue([]),
    listProducts: vi.fn().mockResolvedValue({
      count: 0,
      total_pages: 0,
      current_page: 1,
      page_size: 12,
      next: null,
      previous: null,
      results: [],
    }),
    getCategory: vi.fn(),
    getProduct: vi.fn(),
  },
}));

beforeAll(() => {
  // framer-motion's useInView / layout code paths touch matchMedia in jsdom
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
});

function renderAtRoute(route: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("App", () => {
  it("renders the home page without crashing", async () => {
    renderAtRoute("/");
    expect(await screen.findAllByText(/聚焦好物/i)).not.toHaveLength(0);
  });

  it("renders the 404 page for an unknown route", () => {
    renderAtRoute("/this-route-does-not-exist");
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("renders the login page", () => {
    renderAtRoute("/login");
    expect(screen.getByText("欢迎回来")).toBeInTheDocument();
  });

  it("renders the register page", () => {
    renderAtRoute("/register");
    expect(screen.getByText("创建账户")).toBeInTheDocument();
  });
});
