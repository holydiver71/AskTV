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

  it("keeps the main homepage heading on one line on mobile", () => {
    render(<Home />);

    const heading = screen.getByRole("heading", {
      level: 1,
      name: "The Friday Rock Show",
    });

    expect(heading).toHaveClass("text-3xl");
    expect(heading).toHaveClass("whitespace-nowrap");
  });
});
