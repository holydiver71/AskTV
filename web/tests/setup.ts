import "@testing-library/jest-dom/vitest";
import React from "react";
import { vi } from "vitest";

vi.mock("next/image", () => ({
  __esModule: true,
  default: ({
    alt = "",
    fill,
    priority,
    sizes,
    ...props
  }: React.ImgHTMLAttributes<HTMLImageElement> & {
    fill?: boolean;
    priority?: boolean;
    sizes?: string;
  }) =>
    React.createElement("img", {
      alt,
      // preserve layout-related props as data attributes so tests can inspect them
      "data-fill": fill ? "true" : undefined,
      "data-priority": priority ? "true" : undefined,
      "data-sizes": sizes,
      ...props,
    }),
}));

if (typeof window !== "undefined") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = vi.fn();
  }
}

// Mock next/navigation hooks used by client components in tests
vi.mock("next/navigation", () => {
  return {
    useRouter: () => ({
      push: vi.fn(),
      replace: vi.fn(),
      pathname: "/",
      prefetch: vi.fn().mockResolvedValue(undefined),
    }),
    useSearchParams: () => ({
      // return object with a `get` method used by components
      get: (key: string) => null,
    }),
  };
});
