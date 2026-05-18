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
      {/* BBC red topbar */}
      <div className="bg-[#CC0000] flex items-center justify-between px-6 h-[52px]">
        <div className="flex items-center gap-1">
          <span className="bg-white text-[#CC0000] text-[13px] font-black w-[28px] h-[28px] flex items-center justify-center font-sans">B</span>
          <span className="bg-white text-[#CC0000] text-[13px] font-black w-[28px] h-[28px] flex items-center justify-center font-sans">B</span>
          <span className="bg-white text-[#CC0000] text-[13px] font-black w-[28px] h-[28px] flex items-center justify-center font-sans">C</span>
          <span className="text-white text-[15px] font-black ml-2 tracking-widest">RADIO 1</span>
        </div>
        <span className="text-[#ffaaaa] text-[11px] font-bold tracking-[3px]">MW 275 · 285</span>
      </div>

      {/* Blue show header */}
      <div className="bg-[#003087] border-b-[6px] border-[#FFD700] px-6 py-5 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-white font-black text-[clamp(1.6rem,4vw,2.6rem)] uppercase tracking-[2px] leading-none">
            Friday Rock Show
          </h1>
          <p className="text-[#FFD700] text-[11px] font-bold tracking-[3px] uppercase mt-2">
            Presented by Tommy Vance · BBC Radio 1 · Archive
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
