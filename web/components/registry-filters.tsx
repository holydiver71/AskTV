"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function RegistryFilters({ artist }: { artist?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const [value, setValue] = useState(artist ?? "");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (value.trim()) params.set("artist", value.trim());
    router.push(`${pathname}?${params.toString()}`);
  }

  function handleClear() {
    setValue("");
    router.push(pathname);
  }

  return (
    <form onSubmit={handleSearch} className="flex gap-2 flex-wrap">
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Filter by artist…"
        className="max-w-xs h-11"
      />
      <Button type="submit" variant="secondary" className="h-11 px-4">
        Search
      </Button>
      {artist && (
        <Button type="button" variant="ghost" className="h-11 px-4" onClick={handleClear}>
          Clear
        </Button>
      )}
    </form>
  );
}
