import { expect, test, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/dom";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { mountApp, server } from "./setup.js";
import { makeState } from "./fixtures.js";

const API = "http://localhost:8000";
const choices = Array.from({ length: 5 }, (unused, choiceIndex) => ({
  label: `Alternativa ${choiceIndex + 1}`, text: `Minha resposta ${choiceIndex + 1}.`,
  mode: choiceIndex === 4 ? "say" : "do",
}));

test("five choices send the selected action while the free composer remains available", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const user = userEvent.setup();
  const submitted = [];
  server.use(
    http.get(`${API}/games/:id/state`, () => HttpResponse.json(makeState({ action_choices: choices }))),
    http.post(`${API}/games/:id/action`, async ({ request }) => {
      submitted.push(await request.json());
      return HttpResponse.json({ beats: [], state: makeState({ action_choices: choices }) });
    }),
  );
  await mountApp();
  await user.click(await screen.findByRole("button", { name: /entre nos mundos salvos/i }));
  await user.click(await screen.findByRole("button", { name: /^entrar$/i }));
  const alternatives = await screen.findByRole("region", { name: /o que você quer fazer ou dizer/i });
  expect(within(alternatives).getAllByRole("button")).toHaveLength(5);
  expect(document.querySelector("#cmpInput").getAttribute("contenteditable")).toBe("true");
  await user.click(screen.getByRole("button", { name: /^5 opções$/i }));
  let dialog = screen.getByRole("dialog", { name: /escolha seu próximo passo/i });
  expect(dialog.querySelectorAll('[data-act="choose-action"]')).toHaveLength(5);
  expect(document.activeElement.textContent).toContain("Alternativa 1");
  await user.tab({ shift: true });
  expect(document.activeElement.textContent).toContain("Escrever minha ação ou fala");
  await user.tab();
  expect(document.activeElement.textContent).toContain("Alternativa 1");
  await user.click(within(dialog).getByRole("button", { name: /escrever minha ação ou fala/i }));
  expect(submitted).toHaveLength(0);
  expect(document.activeElement.id).toBe("cmpInput");
  await user.click(screen.getByRole("button", { name: /^5 opções$/i }));
  dialog = screen.getByRole("dialog", { name: /escolha seu próximo passo/i });
  await user.click(within(dialog).getByRole("button", { name: /alternativa 5/i }));
  await waitFor(() => expect(submitted).toHaveLength(1));
  expect(submitted[0].segments).toEqual([{ type: "say", text: "Minha resposta 5." }]);
  await waitFor(() => expect(document.querySelector("#cmpInput").getAttribute("contenteditable")).toBe("true"));
  await user.type(document.querySelector("#cmpInput"), "Vou fazer algo diferente.");
  await user.keyboard("{Enter}");
  await waitFor(() => expect(submitted).toHaveLength(2));
  expect(submitted[1].segments[0].text).toBe("Vou fazer algo diferente.");
});

test("an existing adventure loads AI choices without blocking free typing", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const user = userEvent.setup();
  let finishGeneration;
  let generations = 0;
  server.use(
    http.get(`${API}/games/:id/state`, () => HttpResponse.json(makeState({ action_choices: [] }))),
    http.post(`${API}/games/:id/choices`, async () => {
      generations += 1;
      await new Promise(resolve => { finishGeneration = resolve; });
      return HttpResponse.json({ action_choices: choices });
    }),
  );
  await mountApp();
  await user.click(await screen.findByRole("button", { name: /entre nos mundos salvos/i }));
  await user.click(await screen.findByRole("button", { name: /^entrar$/i }));
  await screen.findByText(/a IA está preparando cinco opções/i);
  const composer = document.querySelector("#cmpInput");
  expect(composer.getAttribute("contenteditable")).toBe("true");
  await user.type(composer, "Quero tentar outro caminho.");
  finishGeneration();
  await screen.findByRole("button", { name: /alternativa 5/i });
  expect(document.querySelector("#cmpInput").textContent).toBe("Quero tentar outro caminho.");
  expect(generations).toBe(1);
});

test("AI failure offers retry without inserting fixed alternatives", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const user = userEvent.setup();
  let generations = 0;
  server.use(
    http.get(`${API}/games/:id/state`, () => HttpResponse.json(makeState({ action_choices: [] }))),
    http.post(`${API}/games/:id/choices`, () => {
      generations += 1;
      return HttpResponse.json(generations === 1
        ? { action_choices: [], action_choices_error: "A IA não gerou opções. Tente novamente." }
        : { action_choices: choices });
    }),
  );
  await mountApp();
  await user.click(await screen.findByRole("button", { name: /entre nos mundos salvos/i }));
  await user.click(await screen.findByRole("button", { name: /^entrar$/i }));
  await screen.findByRole("alert");
  expect(document.querySelectorAll('[data-act="choose-action"]')).toHaveLength(0);
  expect(document.querySelector("#cmpInput").getAttribute("contenteditable")).toBe("true");
  await user.click(screen.getByRole("button", { name: /gerar cinco opções com IA/i }));
  await screen.findByRole("button", { name: /alternativa 5/i });
  expect(generations).toBe(2);
});
