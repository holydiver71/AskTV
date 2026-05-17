import Link from "next/link";

export function Nav() {
  return (
    <header className="border-b border-border px-4 py-3 shrink-0">
      <nav className="max-w-4xl mx-auto flex items-center justify-between">
        <Link
          href="/"
          className="text-sm font-bold tracking-tight hover:text-muted-foreground transition-colors"
        >
          The Friday Rock Show
        </Link>
        <div className="flex items-center gap-5 text-sm">
          <Link
            href="/chat"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            Ask TV
          </Link>
          <Link
            href="/registry"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            The Registry
          </Link>
          <Link
            href="/references"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            References
          </Link>
        </div>
      </nav>
    </header>
  );
}
