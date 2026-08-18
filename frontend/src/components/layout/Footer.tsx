import { Link } from "react-router-dom";
import { Container } from "@/components/ui/Container";
import { BRAND } from "@/constants";

const columns = [
  {
    title: "Shop",
    links: [
      { label: "All products", to: "/products" },
      { label: "Featured", to: "/products?popular=true" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", to: "/about" },
      { label: "Contact", to: "/contact" },
    ],
  },
  {
    title: "Account",
    links: [
      { label: "Sign in", to: "/login" },
      { label: "Order history", to: "/profile" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-24 border-t border-border">
      <Container className="grid grid-cols-2 gap-10 py-14 md:grid-cols-5">
        <div className="col-span-2">
          <span className="font-display text-lg font-semibold">{BRAND.name}</span>
          <p className="mt-2 max-w-xs text-sm text-ink-muted">{BRAND.tagline}</p>
        </div>
        {columns.map((col) => (
          <div key={col.title}>
            <h4 className="font-mono text-xs uppercase tracking-wider text-ink-faint">{col.title}</h4>
            <ul className="mt-3 space-y-2">
              {col.links.map((link) => (
                <li key={link.to}>
                  <Link to={link.to} className="text-sm text-ink-muted hover:text-ink transition-colors">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Container>
      <div className="border-t border-border py-6">
        <Container className="flex flex-col items-center justify-between gap-2 text-xs text-ink-faint sm:flex-row">
          <span>
            &copy; {new Date().getFullYear()} {BRAND.name}. All rights reserved.
          </span>
          <span className="font-mono">Built with precision.</span>
        </Container>
      </div>
    </footer>
  );
}
