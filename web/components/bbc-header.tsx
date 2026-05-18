import Link from "next/link";
import Image from "next/image";

const navLinks = [
  { href: "/chat", label: "Ask TV" },
  { href: "/registry", label: "The Registry" },
  { href: "/references", label: "References" },
];

export function BBCHeader() {
  return (
    <header className="shrink-0">
      {/* Blue show header */}
      <div className="bg-[#003087] border-b-[6px] border-[#FFD700] px-6 py-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-white font-black text-[clamp(1rem,3vw,2rem)] uppercase tracking-[2px] leading-none whitespace-nowrap">
            The Friday Rock Show Revival
          </h1>
          <p className="text-[#FFD700] text-[11px] font-bold tracking-[3px] uppercase mt-2">
            On 275 and 285, the spirit of Tommy Vance lives on
          </p>
        </div>
        <Image
          src="/Radio1-275-285.jpg"
          alt="BBC Radio 1 — 275 285"
          width={80}
          height={80}
          className="shrink-0 object-contain"
          priority
        />
      </div>

      {/* Dark nav bar with red bottom border */}
      <nav className="bg-[#222] border-b-[3px] border-[#CC0000]">
        <div className="flex items-center">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="px-6 py-3 text-[11px] font-bold tracking-[2px] uppercase text-[#999] border-r border-[#333] hover:bg-[#CC0000] hover:text-white transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </div>
      </nav>
    </header>
  );
}
