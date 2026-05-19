import { getEpisode } from "@/lib/db/episodes";
import { notFound } from "next/navigation";
import Link from "next/link";
import { formatTimestamp } from "@/lib/utils/citations";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  return {
    title: `${date} — The Friday Rock Show Archive`,
  };
}

export default async function EpisodeDetailPage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const episode = await getEpisode(date).catch(() => null);

  if (!episode) notFound();

  const d = new Date(episode.date + "T00:00:00");
  const weekday = d.toLocaleDateString("en-GB", { weekday: "long" });
  const dayMonth = d.toLocaleDateString("en-GB", { day: "numeric", month: "long" });
  const year = d.getFullYear().toString();

  const sessionArtists = new Set(
    episode.sessions.map((s) => s.artist.toLowerCase())
  );

  const hasSessions = episode.sessions.length > 0;
  const hasTracks = episode.tracks.length > 0;

  return (
    <>
      <div className="max-w-[1100px] mx-auto w-full px-4 sm:px-8 pt-10 pb-20">
        {/* Back link */}
        <Link
          href="/registry"
          className="text-[10px] font-bold tracking-[3px] uppercase text-[#888] hover:text-[#CC0000] transition-colors"
        >
          ← Registry
        </Link>

        {/* Giant display date */}
        <div
          className="mt-6 mb-5 font-black leading-[0.9]"
          style={{ fontSize: "clamp(3rem, 8vw, 6rem)", letterSpacing: "-4px" }}
        >
          <span className="block text-[#111]">
            {weekday}, <span className="text-[#CC0000]">{dayMonth}</span>
          </span>
          <span
            className="block text-[#888]"
            style={{ fontSize: "0.45em", letterSpacing: "-1px" }}
          >
            {year}
          </span>
        </div>

        {/* Meta bar */}
        <div className="flex flex-wrap items-baseline gap-8 mb-5">
          {hasTracks && (
            <div className="flex items-baseline gap-1.5">
              <span className="text-[2.2rem] font-black text-[#111] leading-none" style={{ letterSpacing: "-1px" }}>
                {episode.tracks.length}
              </span>
              <span className="text-[10px] font-bold tracking-[2px] uppercase text-[#888]">
                Tracks
              </span>
            </div>
          )}
          {hasSessions && (
            <div className="flex items-baseline gap-1.5">
              <span className="text-[2.2rem] font-black text-[#111] leading-none" style={{ letterSpacing: "-1px" }}>
                {episode.sessions.length}
              </span>
              <span className="text-[10px] font-bold tracking-[2px] uppercase text-[#888]">
                Sessions
              </span>
            </div>
          )}
          <div className="flex items-baseline gap-1.5">
            <span className="text-[1.1rem] font-black text-[#888] leading-none">
              Tommy Vance
            </span>
            <span className="text-[10px] font-bold tracking-[2px] uppercase text-[#888]">
              Presenter
            </span>
          </div>
        </div>

        {/* Notice bar */}
        {episode.comments && episode.comments.length > 0 && (
          <div className="inline-flex items-center gap-2 bg-[#FFD700] text-[#111] px-4 py-2.5 text-xs font-bold mb-10">
            ⚠ {episode.comments.join(" · ")}
          </div>
        )}

        {/* Heavy rule */}
        <div
          className={`h-1 bg-[#111] ${
            episode.comments && episode.comments.length > 0 ? "" : "mt-10"
          } mb-10`}
        />

        {/* Two-column layout */}
        <div
          className={`grid gap-14 items-start ${
            hasSessions && hasTracks ? "grid-cols-1 md:grid-cols-2" : "grid-cols-1"
          }`}
        >
          {/* Sessions */}
          {hasSessions && (
            <div>
              <div className="flex items-center gap-3.5 mb-5">
                <h3 className="text-[11px] font-bold tracking-[3px] uppercase text-[#CC0000] whitespace-nowrap">
                  Sessions
                </h3>
                <div className="flex-1 h-px bg-[#e0e0e0]" />
                <span className="bg-[#003087] text-[#FFD700] text-[9px] font-bold tracking-[2px] uppercase px-2.5 py-[3px]">
                  {episode.sessions.length}
                </span>
              </div>
              <div className="space-y-3.5">
                {episode.sessions.map((s) => (
                  <div
                    key={s.id}
                    className="pl-5 border-l-4 border-[#CC0000] bg-[#fafafa] py-4 pr-5"
                  >
                    <div className="text-base font-black text-[#111] mb-1">
                      {s.artist}
                    </div>
                    {s.details && (
                      <div className="text-[13px] text-[#666] leading-relaxed">
                        {s.details}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tracks */}
          {hasTracks && (
            <div>
              <div className="flex items-center gap-3.5 mb-5">
                <h3 className="text-[11px] font-bold tracking-[3px] uppercase text-[#CC0000] whitespace-nowrap">
                  Track Listing
                </h3>
                <div className="flex-1 h-px bg-[#e0e0e0]" />
                <span className="bg-[#003087] text-[#FFD700] text-[9px] font-bold tracking-[2px] uppercase px-2.5 py-[3px]">
                  {episode.tracks.length}
                </span>
              </div>
              <table className="w-full border-collapse">
                <thead>
                  <tr className="border-b-[3px] border-[#CC0000]">
                    <th className="py-2 px-2.5 text-[9px] font-bold tracking-[3px] uppercase text-[#888] text-left w-7">
                      #
                    </th>
                    <th className="py-2 px-2.5 text-[9px] font-bold tracking-[3px] uppercase text-[#888] text-left">
                      Artist
                    </th>
                    <th className="py-2 px-2.5 text-[9px] font-bold tracking-[3px] uppercase text-[#888] text-left">
                      Track
                    </th>
                    <th className="py-2 px-2.5 text-[9px] font-bold tracking-[3px] uppercase text-[#888] text-right">
                      Time
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {episode.tracks.map((t, i) => {
                    const isSession = sessionArtists.has(
                      t.artist.toLowerCase()
                    );
                    return (
                      <tr
                        key={t.id}
                        className={`border-b border-[#f0f0f0] ${
                          i % 2 === 1 ? "bg-[#fafafa]" : "bg-white"
                        }`}
                      >
                        <td className="py-2 px-2.5 text-[11px] font-bold text-[#ccc] w-7 align-middle">
                          {i + 1}
                        </td>
                        <td
                          className={`py-2 px-2.5 text-xs font-bold align-middle ${
                            isSession ? "text-[#CC0000]" : "text-[#111]"
                          }`}
                        >
                          {t.artist}
                        </td>
                        <td className="py-2 px-2.5 text-xs text-[#666] align-middle">
                          {t.track}
                        </td>
                        {t.verified_timestamp != null ? (
                          <td className="py-2 px-2.5 text-[11px] font-black text-white bg-[#003087] whitespace-nowrap text-right align-middle" style={{ letterSpacing: "0.5px" }}>
                            {formatTimestamp(t.verified_timestamp)}
                          </td>
                        ) : (
                          <td className="py-2 px-2.5 align-middle" />
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Fandom link */}
        {episode.url && (
          <div className="mt-10 pt-6 border-t border-[#e0e0e0]">
            <a
              href={episode.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] font-bold tracking-[3px] uppercase text-[#888] hover:text-[#CC0000] transition-colors"
            >
              Fandom Wiki ↗
            </a>
          </div>
        )}
      </div>

      {/* Episode footer */}
      <div className="bg-[#003087] border-t-4 border-[#CC0000] px-4 sm:px-8 py-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex gap-1">
          {(["B", "B", "C"] as const).map((l, i) => (
            <div
              key={i}
              className="bg-[#CC0000] text-white text-[11px] font-black w-[22px] h-[22px] flex items-center justify-center"
              style={{ fontFamily: "'Arial Black', Arial, sans-serif" }}
            >
              {l}
            </div>
          ))}
        </div>
        <div className="flex flex-col sm:flex-row gap-4 sm:gap-8">
          <Link
            href="/registry"
            className="text-[#FFD700] text-[11px] font-bold tracking-[2px] uppercase hover:text-white transition-colors"
          >
            ← Back to Registry
          </Link>
          <Link
            href={`/chat?q=Tell me about the ${episode.date} broadcast`}
            className="text-[#FFD700] text-[11px] font-bold tracking-[2px] uppercase hover:text-white transition-colors"
          >
            Ask TV about this episode →
          </Link>
        </div>
      </div>
    </>
  );
}
