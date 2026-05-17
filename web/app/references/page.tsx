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
              Friday Rock Show Episode Guide ↗
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
    </div>
  );
}