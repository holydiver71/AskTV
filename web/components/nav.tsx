import Link from "next/link";
import { ChatResetLink } from "@/components/chat-reset-link";

const navLinks = [
  { href: "/registry", label: "The Music Vendor" },
  { href: "/references", label: "References" },
];

export function Nav() {
  return (
    <header className="bg-secondary text-secondary-foreground border-b border-primary/40 px-4 py-3 shrink-0">
      <nav className="max-w-4xl mx-auto flex items-center justify-between relative">
        <Link
          href="/"
          className="text-sm font-bold tracking-tight whitespace-nowrap text-secondary-foreground hover:text-secondary-foreground/70 transition-colors"
        >
          The Friday Rock Show
        </Link>

        <div className="hidden md:flex items-center gap-5 text-sm">
          <ChatResetLink className="text-secondary-foreground/70 hover:text-secondary-foreground transition-colors">
            Ask TV
          </ChatResetLink>
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-secondary-foreground/70 hover:text-secondary-foreground transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </div>

        <details className="md:hidden">
          <summary className="list-none h-9 w-9 rounded-md border border-secondary-foreground/20 flex items-center justify-center cursor-pointer hover:bg-secondary-foreground/10 transition-colors [&::-webkit-details-marker]:hidden">
            <span aria-hidden>☰</span>
            <span className="sr-only">Open menu</span>
          </summary>
          <div className="absolute right-0 top-full mt-2 w-44 rounded-md border border-border bg-background p-2 shadow-lg z-50">
            <div className="flex flex-col text-sm">
              <ChatResetLink className="rounded-sm px-2 py-2 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                Ask TV
              </ChatResetLink>
              {navLinks.map((link) => (
                <Link
                  key={`mobile-${link.href}`}
                  href={link.href}
                  className="rounded-sm px-2 py-2 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
                >
                  {link.label}
                </Link>
              ))}
            </div>
          </div>
        </details>
      </nav>
    </header>
  );
}
