import { describe, it, expect, beforeEach, vi } from "vitest";
import { registerRoute, navigate, startRouter } from "../src/router";

function tick(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("router", () => {
  beforeEach(() => {
    location.hash = "";
  });

  it("invokes the matching route's render callback with path params", async () => {
    const render = vi.fn();
    registerRoute("/article/:id", render);
    const outlet = document.createElement("div");
    startRouter(outlet, () => {});
    navigate("/article/42");
    await tick();
    expect(render).toHaveBeenCalledWith({ id: "42" });
  });

  it("falls back to notFound when no route matches", async () => {
    const notFound = vi.fn();
    const outlet = document.createElement("div");
    startRouter(outlet, notFound);
    navigate("/does-not-exist");
    await tick();
    expect(notFound).toHaveBeenCalled();
  });
});
