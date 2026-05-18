import Link from "next/link";
import Image from "next/image";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const metadata = {
  title: "AskTV — The Friday Rock Show Archive",
  description:
    "A searchable digital archive of Tommy Vance's Friday Rock Show on BBC Radio 1. Browse every episode, track, and session from 1980 — or ask TV.",
};

export default function Home() {
  return (
    <div className="flex flex-col flex-1 items-center justify-start md:justify-center px-4 pt-8 pb-10 md:py-16 text-center gap-6 md:gap-8">
      <div className="space-y-3">
        <p className="font-mono text-xs text-muted-foreground tracking-widest uppercase">
          BBC Radio 1 · 1978–1993
        </p>
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight whitespace-nowrap">
          The Friday Rock Show
        </h1>
        <p className="text-muted-foreground max-w-md mx-auto text-sm leading-relaxed">
          A high-fidelity digital archive of Tommy Vance&apos;s landmark rock show.
          Browse every episode, track, and session from the archives — or use Ask TV.
        </p>
        <p className="text-xs text-amber-300/90">
          Temporary note: only 1980 episodes are currently available to research.
        </p>
      </div>

      <div className="flex gap-3">
        <Link href="/chat" className={cn(buttonVariants({ size: "lg" }))}>Ask TV</Link>
        <Link href="/registry" className={cn(buttonVariants({ variant: "outline", size: "lg" }))}>The Registry</Link>
      </div>

      <div className="relative w-28 h-40 rounded-lg overflow-hidden shadow-2xl ring-1 ring-white/10 opacity-85">
        <Image
          src="/tommyvance.png"
          alt="Tommy Vance"
          fill
          sizes="112px"
          className="object-cover object-top"
          priority
        />
      </div>
    </div>
  );
}
