// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import Home from "@/app/page";
import { Nav } from "@/components/nav";

describe("Homepage mobile layout", () => {
  it("uses top-aligned hero spacing on small screens", () => {
    const { container } = render(<Home />);
    const root = container.firstElementChild;

    expect(root).toHaveClass("justify-start");
    expect(root).toHaveClass("pt-8");
    expect(root).toHaveClass("md:justify-center");
  });

  it("renders a hamburger menu trigger for mobile navigation", () => {
    render(<Nav />);

    expect(screen.getByText("Open menu")).toBeInTheDocument();
  });
});
