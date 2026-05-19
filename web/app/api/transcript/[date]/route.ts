import { createSupabaseServer } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: "invalid_request" }, { status: 400 });
  }

  const supabase = await createSupabaseServer();

  const { data: episode } = await supabase
    .from("episodes")
    .select("id")
    .eq("date", date)
    .single();

  if (!episode) {
    return NextResponse.json({ segments: [] });
  }

  const { data: segments, error } = await supabase
    .from("transcript_segments")
    .select("id, chunk_start, chunk_end, text")
    .eq("episode_id", episode.id)
    .order("chunk_start");

  if (error) {
    console.error("[transcript]", error);
    return NextResponse.json({ error: "retrieval_failed" }, { status: 500 });
  }

  return NextResponse.json({ segments: segments ?? [] });
}
