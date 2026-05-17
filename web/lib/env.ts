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
});

function validateEnv() {
  const result = schema.safeParse(process.env);
  if (!result.success) {
    const errors = result.error.flatten().fieldErrors;
    throw new Error(
      `Missing or invalid environment variables:\n${JSON.stringify(errors, null, 2)}`
    );
  }
  return result.data;
}

export const env = validateEnv();
