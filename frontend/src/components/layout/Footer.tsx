import { Link } from "react-router-dom";
import { Container } from "@/components/ui/Container";
import { BRAND } from "@/constants";

const columns = [
  {
    title: "选购",
    links: [
      { label: "全部商品", to: "/products" },
      { label: "热门推荐", to: "/products?popular=true" },
    ],
  },
  {
    title: "品牌",
    links: [
      { label: "关于我们", to: "/about" },
      { label: "联系我们", to: "/contact" },
    ],
  },
  {
    title: "账户",
    links: [
      { label: "登录", to: "/login" },
      { label: "订单记录", to: "/profile" },
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
            &copy; {new Date().getFullYear()} {BRAND.name}。保留所有权利。
          </span>
          <span className="font-mono">为细节而生。</span>
        </Container>
      </div>
    </footer>
  );
}
