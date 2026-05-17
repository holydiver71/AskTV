// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import ChatPage from "@/app/chat/page";

function renderAtWidth(width: number) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    writable: true,
    value: width,
  });
  window.dispatchEvent(new Event("resize"));
  return render(<ChatPage />);
}

describe("Chat first-view hero layout", () => {
  afterEach(() => {
    cleanup();
  });

  it("keeps Tommy portrait before the query input on desktop width", () => {
    renderAtWidth(1280);

    const portrait = screen.getByRole("img", { name: /portrait of tommy vance/i });
    const input = screen.getByLabelText(/ask tommy question/i);

    expect(
      Boolean(portrait.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING)
    ).toBe(true);
  });

  it("keeps Tommy portrait before the query input on mobile width", () => {
    renderAtWidth(390);

    const portrait = screen.getByRole("img", { name: /portrait of tommy vance/i });
    const input = screen.getByLabelText(/ask tommy question/i);

    expect(
      Boolean(portrait.compareDocumentPosition(input) & Node.DOCUMENT_POSITION_FOLLOWING)
    ).toBe(true);
  });
});
