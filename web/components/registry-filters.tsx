"use client";

import { useRouter, usePathname } from "next/navigation";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function RegistryFilters({
  artist,
  year,
  availableYears,
}: {
  artist?: string;
  year?: string;
  availableYears: string[];
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [value, setValue] = useState(artist ?? "");
  const [yearValue, setYearValue] = useState(year ?? "");

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const params = new URLSearchParams();
    if (value.trim()) params.set("artist", value.trim());
    if (yearValue) params.set("year", yearValue);
    router.push(`${pathname}?${params.toString()}`);
  }

  function handleClear() {
    setValue("");
    setYearValue("");
    router.push(pathname);
  }

  const hasActiveFilters = Boolean((artist ?? "").trim()) || Boolean(year);

  return (
    <form onSubmit={handleSearch} className="flex gap-2 flex-wrap items-stretch">
      <label htmlFor="registry-year" className="sr-only">
        Filter by year
      </label>
      <div className="relative w-full sm:w-40">
        <select
          id="registry-year"
          value={yearValue}
          onChange={(e) => setYearValue(e.target.value)}
          className="h-11 w-full appearance-none rounded-lg border border-input bg-transparent px-3 pr-9 text-sm outline-none transition-colors focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
        >
          <option value="">All years</option>
          {availableYears.map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-xs text-muted-foreground">
          ▾
        </span>
      </div>
      <Input
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Filter by artist…"
        className="w-full sm:max-w-xs h-11"
      />
      <Button type="submit" variant="secondary" className="h-11 px-4">
        Search
      </Button>
      {hasActiveFilters && (
        <Button type="button" variant="ghost" className="h-11 px-4" onClick={handleClear}>
          Clear
        </Button>
      )}
    </form>
  );
}
