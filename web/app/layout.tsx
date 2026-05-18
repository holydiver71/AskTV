import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";
import { Nav } from "@/components/nav";
import { BBCHeader } from "@/components/bbc-header";
import { Footer } from "@/components/footer";
import { Toaster } from "@/components/ui/sonner";
import { env } from "@/lib/env";
import { getThemeClasses } from "@/lib/theme";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AskTV — The Friday Rock Show Archive",
  description:
    "A searchable digital archive of Tommy Vance's Friday Rock Show on BBC Radio 1. Browse every episode, track, and session from 1980.",
};

const themeClasses = getThemeClasses(env.ASK_TV_THEME);

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={[
        geistSans.variable,
        geistMono.variable,
        "h-full antialiased",
        ...themeClasses,
      ].join(" ")}
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        {env.ASK_TV_THEME === "radio1" ? <BBCHeader /> : <Nav />}
        <Analytics />
        <main className="flex flex-col flex-1 min-h-0">{children}</main>
        <Footer />
        <Toaster />
      </body>
    </html>
  );
}
