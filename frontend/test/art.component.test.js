import { afterEach, expect, test, vi } from "vitest";
import { screen, waitFor } from "@testing-library/dom";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { mountApp, server } from "./setup.js";
import { FakeEventSource, makeBeat, makeState } from "./fixtures.js";

afterEach(() => vi.unstubAllGlobals());

test("settings starts a regeneration and SSE refreshes images already present in the story", async () => {
  vi.stubGlobal("EventSource", FakeEventSource);
  const player = userEvent.setup({ delay: null });
  let progress = { status: "idle", total: 0, completed: 0, failed: 0 };
  let regenerated = false;
  let startRequests = 0;
  server.use(
    http.get("http://localhost:8000/games/:id/images/regeneration", () => HttpResponse.json(progress)),
    http.post("http://localhost:8000/games/:id/images/regenerate", () => {
      startRequests += 1;
      progress = { id: "job1", status: "running", total: 2, completed: 0, failed: 0 };
      return HttpResponse.json(progress, { status: 202 });
    }),
    http.get("http://localhost:8000/games/:id/state", () => {
      const gameState = makeState();
      gameState.scene.image_url = regenerated ? "/new-scene.png" : "/old-scene.png";
      return HttpResponse.json(gameState);
    }),
    http.get("http://localhost:8000/games/:id/beats", () => HttpResponse.json({ beats: [
      makeBeat({ id: "old-art", kind: "image", text: "Memória antiga", image_url: regenerated ? "/new-memory.png" : "/old-memory.png" }),
    ] })),
  );
  const application = await mountApp();
  await player.click(await screen.findByRole("button", { name: /entre nos mundos salvos/i }));
  await player.click(await screen.findByRole("button", { name: /^entrar$/i }));
  await screen.findAllByText("The Last Breath");
  await player.click(screen.getByRole("button", { name: /configurações/i }));
  await player.click(await screen.findByRole("button", { name: /regenerar todas as imagens/i }));
  await screen.findByText("0 de 2 imagens processadas.");
  expect(screen.getByRole("button", { name: /regenerando imagens/i }).disabled).toBe(true);
  expect(startRequests).toBe(1);
  regenerated = true;
  progress = { ...progress, status: "completed", completed: 2 };
  FakeEventSource.instances.at(-1).emit({ kind: "image-regeneration", regeneration: progress });
  await screen.findByText("2 imagens atualizadas.");
  await waitFor(() => expect(application.state.active.beats[0].imageUrl).toBe("/new-memory.png"));
  expect(application.state.active.beats[0].text).toBe("Memória antiga");
  expect(application.state.active.state.scene.imageUrl).toBe("/new-scene.png");
  expect(screen.getByRole("button", { name: /regenerar todas as imagens/i }).disabled).toBe(false);
});
