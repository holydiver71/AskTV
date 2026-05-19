import { z } from "zod";

// Server-side only — do not import this from client components.
const schema = z.object({
  NEXT_PUBLIC_SUPABASE_URL: z
    .string()
    .url("NEXT_PUBLIC_SUPABASE_URL must be a valid URL"),
  NEXT_PUBLIC_SUPABASE_ANON_KEY: z
    .string()
    .min(1, "NEXT_PUBLIC_SUPABASE_ANON_KEY is required"),
  OPENAI_API_KEY: z.string().min(1, "OPENAI_API_KEY is required"),
  ASKTV_CHAT_SYSTEM_PROMPT: z.string().optional(),
  ASK_TV_THEME: z.string().optional().default("default"),
});

function validateEnv() {
  const result = schema.safeParse(process.env);
  if (!result.success) {
    if (!process.env.VERCEL) {
      console.warn(
        `[local] Missing env vars — layout/navigation only:\n` +
          JSON.stringify(result.error.flatten().fieldErrors, null, 2)
      );
      return {
        NEXT_PUBLIC_SUPABASE_URL: "",
        NEXT_PUBLIC_SUPABASE_ANON_KEY: "",
        OPENAI_API_KEY: "",
        ASKTV_CHAT_SYSTEM_PROMPT: undefined,
        ASK_TV_THEME: (process.env.ASK_TV_THEME as string) ?? "default",
      } as z.infer<typeof schema>;
    }
    throw new Error(
      `Missing or invalid environment variables:\n${JSON.stringify(
        result.error.flatten().fieldErrors,
        null,
        2
      )}`
    );
  }
  return result.data;
}

export const env = validateEnv();
