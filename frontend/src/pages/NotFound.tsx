import { Link } from "react-router-dom";
import { Aperture } from "lucide-react";
import { Container } from "@/components/ui/Container";
import { Button } from "@/components/ui/Button";

export function NotFound() {
  return (
    <Container className="flex min-h-[calc(100vh-4rem)] flex-col items-center justify-center gap-4 text-center">
      <div className="relative flex h-20 w-20 items-center justify-center rounded-full border border-border-strong">
        <Aperture className="h-8 w-8 text-accent" strokeWidth={1.5} />
      </div>
      <h1 className="font-mono text-6xl font-semibold text-ink">404</h1>
      <p className="max-w-sm text-sm text-ink-muted">
        页面不存在，或已经移动到了其他位置。
      </p>
      <Link to="/">
        <Button>返回首页</Button>
      </Link>
    </Container>
  );
}
