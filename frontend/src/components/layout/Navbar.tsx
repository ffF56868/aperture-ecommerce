import { useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { Menu, Search, ShoppingBag, User, X } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";
import { BRAND, NAV_LINKS } from "@/constants";
import { useCart } from "@/hooks/useCart";
import { useAuth } from "@/hooks/useAuth";
import { cn } from "@/utils/cn";

export function Navbar() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const { totalItems } = useCart();
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const submitSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim()) {
      navigate(`/products?search=${encodeURIComponent(query.trim())}`);
      setSearchOpen(false);
      setQuery("");
    }
  };

  return (
    <header className="sticky top-0 z-50 glass">
      <Container className="flex h-16 items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2 shrink-0" aria-label={`${BRAND.name} home`}>
          <svg viewBox="0 0 32 32" className="h-7 w-7" fill="none">
            <path d="M6 11V6H11" stroke="#7B61FF" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M21 6H26V11" stroke="#7B61FF" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M26 21V26H21" stroke="#FF7A59" strokeWidth="2.4" strokeLinecap="round" />
            <path d="M11 26H6V21" stroke="#FF7A59" strokeWidth="2.4" strokeLinecap="round" />
            <circle cx="16" cy="16" r="4.5" stroke="#F5F5F7" strokeWidth="1.6" />
          </svg>
          <span className="font-display text-lg font-semibold tracking-tight">{BRAND.name}</span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                cn(
                  "rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive ? "text-ink" : "text-ink-muted hover:text-ink",
                )
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-1.5">
          <div className="hidden sm:block">
            {searchOpen ? (
              <form onSubmit={submitSearch} className="flex items-center">
                <input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onBlur={() => !query && setSearchOpen(false)}
                  placeholder="Search products…"
                  className="h-9 w-56 rounded-md border border-border-strong bg-bg-surface px-3 text-sm outline-none focus:border-accent"
                />
              </form>
            ) : (
              <Button variant="ghost" size="icon" onClick={() => setSearchOpen(true)} aria-label="Search">
                <Search className="h-4.5 w-4.5" />
              </Button>
            )}
          </div>

          <Link to={isAuthenticated ? "/profile" : "/login"}>
            <Button variant="ghost" size="icon" aria-label="Account">
              <User className="h-4.5 w-4.5" />
            </Button>
          </Link>

          <Link to="/cart" className="relative">
            <Button variant="ghost" size="icon" aria-label="Cart">
              <ShoppingBag className="h-4.5 w-4.5" />
            </Button>
            {totalItems > 0 && (
              <span className="absolute -right-0.5 -top-0.5 flex h-4.5 min-w-4.5 items-center justify-center rounded-full bg-coral px-1 font-mono text-[10px] font-semibold text-white">
                {totalItems}
              </span>
            )}
          </Link>

          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Menu"
          >
            {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </Container>

      {mobileOpen && (
        <div className="border-t border-border md:hidden">
          <Container className="flex flex-col gap-1 py-3">
            {NAV_LINKS.map((link) => (
              <NavLink
                key={link.to}
                to={link.to}
                onClick={() => setMobileOpen(false)}
                className="rounded-md px-3 py-2.5 text-sm font-medium text-ink-muted hover:bg-white/[0.04] hover:text-ink"
              >
                {link.label}
              </NavLink>
            ))}
          </Container>
        </div>
      )}
    </header>
  );
}
