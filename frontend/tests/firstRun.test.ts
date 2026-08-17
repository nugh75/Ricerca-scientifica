import { describe, it, expect, beforeEach } from "vitest";
import { isFirstRunDone, markFirstRunDone } from "../src/firstRun";

describe("firstRun", () => {
  beforeEach(() => localStorage.clear());

  it("is false before markFirstRunDone is called", () => {
    expect(isFirstRunDone()).toBe(false);
  });

  it("is true after markFirstRunDone", () => {
    markFirstRunDone();
    expect(isFirstRunDone()).toBe(true);
  });
});
