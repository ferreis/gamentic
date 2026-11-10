import { afterEach, beforeEach, expect, test, vi } from "vitest";

const controls = vi.hoisted(() => ({
  state: { active: null, view: "settings" },
  api: { regenerateImages: vi.fn(), imageRegenerationStatus: vi.fn(), getState: vi.fn(), getBeats: vi.fn(), characterProfile: vi.fn() },
  render: vi.fn(), showToast: vi.fn(),
}));
vi.mock("../src/app/ctx.js", () => ({ state: controls.state, api: controls.api }));
vi.mock("../src/app/ui.js", () => ({ render: controls.render }));
vi.mock("../src/app/cues.js", () => ({ showToast: controls.showToast }));

import { loadImageRegeneration, regenerateAllImages, stopImageRegenerationWatch } from "../src/app/artctl.js";

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
  controls.state.active = {
    id: "g1", state: { scene: { imageUrl: "/old-scene.png" } }, generating: false,
    beats: [{ id: "old-beat", imageUrl: "/old-beat.png", text: "The same memory.", viaProfile: "c1" }],
  };
  controls.api.getState.mockResolvedValue({ game_id: "g1", scene: { image_url: "/new-scene.png" }, characters: [] });
  controls.api.getBeats.mockResolvedValue({ beats: [{ id: "old-beat", kind: "image", text: "The same memory.", image_url: "/new-beat.png" }] });
});
afterEach(() => {
  stopImageRegenerationWatch();
  vi.useRealTimers();
});

test("starts once, tracks progress and refreshes existing historical images without replaying the story", async () => {
  const running = { id: "job1", status: "running", total: 1, completed: 0, failed: 0 };
  controls.api.regenerateImages.mockResolvedValue(running);
  controls.api.imageRegenerationStatus.mockResolvedValueOnce(running)
    .mockResolvedValueOnce({ ...running, status: "completed", completed: 1 });
  await regenerateAllImages();
  await regenerateAllImages();
  expect(controls.api.regenerateImages).toHaveBeenCalledTimes(1);
  await vi.advanceTimersByTimeAsync(2500);
  expect(controls.api.getBeats).toHaveBeenCalledWith("g1"); // full history, not since=lastTurn
  expect(controls.state.active.beats[0]).toMatchObject({
    id: "old-beat", text: "The same memory.", viaProfile: "c1", imageUrl: "/new-beat.png",
  });
  expect(controls.state.active.state.scene.imageUrl).toBe("/new-scene.png");
  await vi.advanceTimersByTimeAsync(10000);
  expect(controls.api.imageRegenerationStatus).toHaveBeenCalledTimes(2);
});

test("a failed start preserves existing images and unlocks the button", async () => {
  controls.api.regenerateImages.mockRejectedValue(new Error("Gerador indisponível"));
  await regenerateAllImages();
  expect(controls.state.active.imageRegenerationStarting).toBe(false);
  expect(controls.state.active.state.scene.imageUrl).toBe("/old-scene.png");
  expect(controls.state.active.imageRegenerationError).toBe("Gerador indisponível");
});

test("an old adventure response cannot cancel progress polling for the newly opened adventure", async () => {
  let resolveOldRequest;
  controls.api.imageRegenerationStatus.mockImplementationOnce(() => new Promise((resolve) => { resolveOldRequest = resolve; }))
    .mockResolvedValue({ id: "job2", status: "running", total: 3, completed: 0 });
  const previousRequest = loadImageRegeneration();
  controls.state.active = { id: "g2", state: {}, beats: [] };
  await loadImageRegeneration();
  resolveOldRequest({ status: "idle" });
  await previousRequest;
  await vi.advanceTimersByTimeAsync(2500);
  expect(controls.api.imageRegenerationStatus).toHaveBeenLastCalledWith("g2");
  expect(controls.api.imageRegenerationStatus).toHaveBeenCalledTimes(3);
});
