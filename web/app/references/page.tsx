export const metadata = {
  title: "References — The Friday Rock Show Archive",
};

export default function ReferencesPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">References</h1>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This archive and chat experience are built on the work of dedicated
          Friday Rock Show fans and researchers. Thank you for preserving and
          sharing this history.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Key Sources
        </h2>

        <ul className="space-y-4">
          <li className="space-y-1">
            <a
              href="https://fridayrockshow.fandom.com/wiki"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-primary hover:underline"
            >
              Friday Rock Show Fandom Wiki ↗
            </a>
            <p className="text-sm text-muted-foreground leading-relaxed">
              The Fandom page and its contributors are foundational to this
              project. Without their careful documentation, this chat app would
              not be possible.
            </p>
          </li>

          <li className="space-y-1">
            <a
              href="https://www.dawtrina.com/music/frs/checklist.html"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-primary hover:underline"
            >
              Hal C. F. Astell's The Friday Rock Show ↗
            </a>
            <p className="text-sm text-muted-foreground leading-relaxed">
              A valuable source of episode information and broadcast history.
            </p>
          </li>

          <li className="space-y-1">
            <a
              href="https://www.facebook.com/groups/170443413007183"
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-primary hover:underline"
            >
              Friday Rock Show Facebook Group ↗
            </a>
            <p className="text-sm text-muted-foreground leading-relaxed">
              A great place to talk and share your thoughts on The Friday Rock
              Show.
            </p>
          </li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          What&apos;s in the Knowledge Base
        </h2>

        <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
          <p>
            The Ask Tommy knowledge base is built entirely from Tommy&apos;s own
            words — nothing more, nothing less. Episode metadata was sourced from
            the Fandom Wiki and Hal C.F. Astell&apos;s episode guide; the transcripts were
            generated directly from the original broadcast recordings using
            Whisper.
          </p>
          <p>
            Song lyrics have been stripped out so the model focuses purely on
            Tommy&apos;s introductions, dedications, and commentary — the stuff that
            actually makes the show special.
          </p>
          <p>
            Tommy was famously generous about reading out listeners&apos; full home
            addresses on air — a wonderfully innocent pre-internet habit. Those
            addresses have been quietly removed. The towns and regions are kept
            (Tommy&apos;s shout-outs to Sutton Coldfield are sacred), but specific
            house numbers and street names are replaced with{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">
              [redacted address]
            </code>
            . The spirit of the dedications lives on; the stalker-enabling parts
            do not.
          </p>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Chat Persona
        </h2>

        <div className="space-y-3 text-sm text-muted-foreground leading-relaxed">
          <p>
            Ask Tommy is styled after Tommy Vance, known as "The Music
            Vendor," with a warm late-night broadcast tone, deep rock and
            metal knowledge, and understated humor.
          </p>
          <p>
            The aim is authenticity rather than parody. Replies are written to
            feel like classic Friday Rock Show presentation while staying clear,
            grounded, and useful.
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Accuracy is prioritized over style.</li>
            <li>
              Archive-grounded claims require citations in the format
              [YYYY-MM-DD @ HH:MM:SS].
            </li>
            <li>Tracks, dates, guests, quotes, and timestamps are never invented.</li>
            <li>
              Signature Tommy-style phrases are used sparingly to keep the voice
              natural.
            </li>
          </ul>
        </div>
      </section>
    </div>
  );
}