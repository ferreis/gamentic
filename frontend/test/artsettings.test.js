import { describe, expect, it } from "vitest";
import { renderArtSettings } from "../src/render/artsettings.js";

describe("controles de checkpoint e LoRAs", () => {
  const controls = {
    checkpoints: [{ name: "anime.safetensors", label: "Anime", family: "sdxl" }, { name: "light.safetensors", label: "Leve", family: "sd15" }],
    loras: [{ name: "pixel.safetensors", label: "Pixel art", family: "sdxl" }],
  };
  it("mostra o modelo selecionado e a intensidade da LoRA", () => {
    document.body.innerHTML = renderArtSettings({ artControls: controls, artSelection: { checkpoint: "anime.safetensors", loras: [{ name: "pixel.safetensors", strength: 0.6 }] } });
    expect(document.querySelector("select").value).toBe("anime.safetensors");
    expect(document.querySelector('[type="checkbox"]').checked).toBe(true);
    expect(document.querySelector('[type="number"]').value).toBe("0.6");
    expect(document.body.textContent).toContain("todas as aventuras");
  });
  it("oculta LoRAs de outra família", () => {
    document.body.innerHTML = renderArtSettings({ artControls: controls, artSelection: { checkpoint: "light.safetensors", loras: [] } });
    expect(document.querySelector('[type="checkbox"]')).toBeNull();
    expect(document.body.textContent).toContain("Nenhuma LoRA");
  });
});
