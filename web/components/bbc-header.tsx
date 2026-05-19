import Link from "next/link";
import Image from "next/image";
import { ChatResetLink } from "@/components/chat-reset-link";

const navLinks = [
  { href: "/registry", label: "The Music Vendor" },
  { href: "/references", label: "References" },
];

export function BBCHeader() {
  return (
    <header className="shrink-0">
      {/* Blue show header */}
      <div className="bg-[#003087] border-b-[6px] border-[#FFD700] px-4 md:px-6 py-4 md:py-5 flex items-center justify-between gap-3">
        <div className="min-w-0 flex-1">
          <Link href="/">
            <h1 className="text-white font-black text-[clamp(1.2rem,5vw,2rem)] uppercase tracking-[2px] leading-none hover:opacity-80 transition-opacity">
              <span className="md:hidden">FRS Revival</span>
              <span className="hidden md:inline">The Friday Rock Show Revival</span>
            </h1>
          </Link>
          <p className="text-[#FFD700] text-[11px] font-bold tracking-[1px] mt-2 leading-snug">
            On 275 and 285, the spirit of Tommy Vance lives on
          </p>
        </div>
        <Link href="/" className="shrink-0 hover:opacity-80 transition-opacity">
          <Image
            src="/Radio1-275-285.jpg"
            alt="BBC Radio 1 — 275 285 — Home"
            width={70}
            height={70}
            className="object-contain"
            priority
          />
        </Link>
      </div>

      {/* Dark nav bar with red bottom border */}
      <nav className="bg-[#222] border-b-[3px] border-[#CC0000]">
        <div className="flex items-center">
          <ChatResetLink className="flex-1 text-center px-2 md:px-6 py-2 md:py-3 text-[10px] md:text-[11px] font-bold tracking-[1px] md:tracking-[2px] uppercase text-[#999] border-r border-[#333] hover:bg-[#CC0000] hover:text-white transition-colors">
            Ask TV
          </ChatResetLink>
          <Link
            href="/registry"
            className="flex-1 text-center px-2 md:px-6 py-2 md:py-3 text-[10px] md:text-[11px] font-bold tracking-[1px] md:tracking-[2px] uppercase text-[#999] border-r border-[#333] hover:bg-[#CC0000] hover:text-white transition-colors"
          >
            The Music Vendor
          </Link>
          <Link
            href="/references"
            className="flex-1 text-center px-2 md:px-6 py-2 md:py-3 text-[10px] md:text-[11px] font-bold tracking-[1px] md:tracking-[2px] uppercase text-[#999] border-r border-[#333] hover:bg-[#CC0000] hover:text-white transition-colors"
          >
            References
          </Link>
        </div>
      </nav>
    </header>
  );
}
