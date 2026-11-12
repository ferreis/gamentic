import { expect, test } from "vitest";
import { screen } from "@testing-library/dom";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { mountApp, server } from "./setup.js";

test("seleciona checkpoint, combina LoRA e salva sem regenerar a aventura", async () => {
  const player = userEvent.setup({ delay: null });
  let savedSelection;
  server.use(
    http.get("http://localhost:8000/images/settings", () => HttpResponse.json({
      settings: { checkpoint: "", loras: [] },
      checkpoints: [{ name: "anime.safetensors", label: "Anime", family: "sdxl" }],
      loras: [{ name: "pixel.safetensors", label: "Pixel art", family: "sdxl" }],
    })),
    http.put("http://localhost:8000/images/settings", async ({ request }) => {
      savedSelection = await request.json();
      return HttpResponse.json({ settings: savedSelection });
    }),
  );
  await mountApp();
  await player.click(await screen.findByRole("button", { name: /entre nos mundos salvos/i }));
  await player.click(await screen.findByRole("button", { name: /^entrar$/i }));
  await screen.findAllByText("The Last Breath");
  await player.click(screen.getByRole("button", { name: /^menu$/i }));
  await player.selectOptions(await screen.findByRole("combobox", { name: /checkpoint/i }), "anime.safetensors");
  await player.click(screen.getByRole("checkbox", { name: "Pixel art" }));
  const intensity = screen.getByRole("spinbutton", { name: "Intensidade de Pixel art" });
  await player.clear(intensity);
  await player.type(screen.getByRole("spinbutton", { name: "Intensidade de Pixel art" }), "0.5");
  await player.click(screen.getByRole("button", { name: "Salvar configuração de arte" }));
  await screen.findByText(/Arte salva/);
  expect(savedSelection).toEqual({ checkpoint: "anime.safetensors", loras: [{ name: "pixel.safetensors", strength: 0.5 }] });
});
