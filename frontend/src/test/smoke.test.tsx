import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { formatPrice } from "@/utils/format";
import { cn } from "@/utils/cn";

describe("formatPrice", () => {
  it("formats a string decimal as USD currency", () => {
    expect(formatPrice("29.99")).toBe("$29.99");
  });

  it("formats a numeric value as USD currency", () => {
    expect(formatPrice(1500)).toBe("$1,500.00");
  });
});

describe("cn", () => {
  it("merges and dedupes conflicting Tailwind classes", () => {
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });
});

describe("Button", () => {
  it("renders children and responds to click", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Add to cart</Button>);
    fireEvent.click(screen.getByText("Add to cart"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("disables interaction while loading", () => {
    render(<Button isLoading>Submit</Button>);
    expect(screen.getByRole("button")).toBeDisabled();
  });
});

describe("Badge", () => {
  it("renders its label text", () => {
    render(<Badge>In stock</Badge>);
    expect(screen.getByText("In stock")).toBeInTheDocument();
  });
});
