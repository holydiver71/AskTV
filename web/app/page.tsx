import Link from "next/link";
import Image from "next/image";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata = {
  title: "AskTV — The Friday Rock Show Revival",
  description:
    "A searchable digital archive of Tommy Vance's Friday Rock Show on BBC Radio 1. Browse every episode, track, and session from 1980 — or ask TV.",
};

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-start md:justify-center px-4 pt-4 pb-10 md:py-16 text-center gap-6 md:gap-8">
      <h1 className="text-[clamp(1rem,4.5vw,1.5rem)] font-black uppercase tracking-[2px] whitespace-nowrap">
        The Friday Rock Show
      </h1>

      <div className="relative w-56 h-72 sm:w-64 sm:h-80 md:w-72 md:h-96 rounded-xl overflow-hidden shadow-2xl ring-1 ring-white/10">
        <Image
          src="/tommyvance.png"
          alt="Tommy Vance"
          fill
          sizes="(max-width: 640px) 224px, (max-width: 768px) 256px, 288px"
          className="object-cover object-top"
          priority
        />
      </div>

      <div className="space-y-3">
        <p className="font-mono text-xs text-muted-foreground tracking-widest uppercase">
          BBC Radio 1 · 1978–1993
        </p>
        <p className="text-muted-foreground max-w-sm mx-auto text-sm leading-relaxed">
          Every track Tommy Vance ever played on the Friday Rock Show — catalogued, searchable, citable.
        </p>
        <p className="text-xs text-amber-300/90">
          Temporary note: only 1980 episodes are currently available to research.
        </p>
      </div>

      <div className="flex gap-3">
        <Link href="/chat" className={cn(buttonVariants({ size: "lg" }))}>Ask TV</Link>
        <Link href="/registry" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>The Music Vendor</Link>
      </div>
    </div>
  );
}
