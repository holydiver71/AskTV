export const metadata = {
  title: "References — The Friday Rock Show Archive",
};

const sources = [
  {
    href: "https://fridayrockshow.fandom.com/wiki",
    label: "Friday Rock Show Fandom Wiki",
    description:
      "The Fandom page and its contributors are foundational to this project. Without their careful documentation, this chat app would not be possible.",
  },
  {
    href: "https://www.dawtrina.com/music/frs/checklist.html",
    label: "Hal C. F. Astell's The Friday Rock Show",
    description:
      "A valuable source of episode information and broadcast history.",
  },
  {
    href: "https://www.facebook.com/groups/170443413007183",
    label: "Friday Rock Show Facebook Group",
    description:
      "A great place to talk and share your thoughts on The Friday Rock Show.",
  },
];

function SectionHead({ title }: { title: string }) {
  return (
    <div className="flex items-center gap-3.5 mb-6">
      <h2 className="text-[11px] font-bold tracking-[3px] uppercase text-[#CC0000] whitespace-nowrap">
        {title}
      </h2>
      <div className="flex-1 h-px bg-[#e0e0e0]" />
    </div>
  );
}

export default function ReferencesPage() {
  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 pt-10 pb-20">

      {/* Page title */}
      <div className="mb-10">
        <h1
          className="font-black text-[#111] leading-[0.9] mb-3"
          style={{ fontSize: "clamp(2rem, 5vw, 3.5rem)", letterSpacing: "-2px" }}
        >
          References
        </h1>
        <p className="text-sm text-[#555] leading-relaxed max-w-2xl">
          This archive is built on the work of dedicated Friday Rock Show fans
          and researchers. Thank you for preserving and sharing this history.
        </p>
      </div>

      <div className="h-1 bg-[#111] mb-10" />

      {/* Key Sources */}
      <section className="mb-12">
        <SectionHead title="Key Sources" />
        <ul className="space-y-0">
          {sources.map((s, i) => (
            <li
              key={s.href}
              className={`flex gap-5 py-5 ${i < sources.length - 1 ? "border-b border-[#f0f0f0]" : ""}`}
            >
              <span className="text-[11px] font-bold text-[#ccc] w-5 shrink-0 pt-0.5 text-right">
                {i + 1}
              </span>
              <div>
                <a
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm font-black text-[#003087] hover:text-[#CC0000] transition-colors"
                >
                  {s.label} ↗
                </a>
                <p className="mt-1 text-sm text-[#666] leading-relaxed">
                  {s.description}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      {/* What's in the knowledge base */}
      <section className="mb-12">
        <SectionHead title="What's in the Knowledge Base" />
        <div className="pl-5 border-l-4 border-[#CC0000] bg-[#fafafa] py-4 pr-5 space-y-3 text-sm text-[#444] leading-relaxed">
          <p>
            The Ask Tommy knowledge base is built entirely from Tommy&apos;s own
            words — nothing more, nothing less. Episode metadata and audio was
            sourced from the Fandom Wiki and Hal C.F. Astell&apos;s episode
            guide; the transcripts were generated directly from those audio
            recordings using Whisper.
          </p>
          <p>
            Song lyrics have been stripped out so the model focuses purely on
            Tommy&apos;s introductions, dedications, and commentary — the stuff
            that actually makes the show special.
          </p>
          <p>
            Tommy was famously generous about reading out listeners&apos; full
            home addresses on air — a wonderfully innocent pre-internet habit.
            Those addresses have been quietly removed. The towns and regions are
            kept (Tommy&apos;s shout-outs to Sutton Coldfield are sacred), but
            specific house numbers and street names are replaced with{" "}
            <code className="text-xs bg-[#003087] text-white px-1.5 py-0.5 font-mono">
              [redacted address]
            </code>
            . The spirit of the dedications lives on; the stalker-enabling parts
            do not.
          </p>
        </div>
      </section>

      {/* Chat persona */}
      <section>
        <SectionHead title="Chat Persona" />
        <div className="space-y-4 text-sm text-[#444] leading-relaxed">
          <p>
            Ask TV is styled after Tommy Vance, &quot;The Music Vendor,&quot;
            with a warm late-night broadcast tone, deep rock and metal
            knowledge, and understated humor. The aim is authenticity rather
            than parody.
          </p>
          <ul className="space-y-2">
            {[
              "Accuracy is prioritised over style.",
              "Archive-grounded claims require citations in the format [YYYY-MM-DD @ HH:MM:SS].",
              "Tracks, dates, guests, quotes, and timestamps are never invented.",
              "Signature Tommy-style phrases are used sparingly to keep the voice natural.",
            ].map((item) => (
              <li key={item} className="flex gap-3 items-baseline">
                <span className="shrink-0 w-1.5 h-1.5 rounded-full bg-[#CC0000] mt-1.5" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </section>

    </div>
  );
}
