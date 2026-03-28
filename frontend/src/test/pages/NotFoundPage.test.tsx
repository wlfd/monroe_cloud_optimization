import { describe, it, expect } from "vitest";
import { screen } from "@testing-library/react";
import { render } from "../test-utils";
import { NotFoundPage } from "@/pages/NotFoundPage";

function renderPage() {
  return render(<NotFoundPage />);
}

describe("NotFoundPage", () => {
  it('renders "404"', () => {
    renderPage();
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it('renders "Page not found."', () => {
    renderPage();
    expect(screen.getByText(/page not found/i)).toBeInTheDocument();
  });

  it("renders a link to the dashboard", () => {
    renderPage();
    const link = screen.getByRole("link", { name: /go to dashboard/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/dashboard");
  });
});
