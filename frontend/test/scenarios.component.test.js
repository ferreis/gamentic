import { expect, test, vi } from "vitest";
import { screen, waitFor } from "@testing-library/dom";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { mountApp, server } from "./setup.js";

const API = "http://localhost:8000";
const scenario = { id: "scenario-1", title: "Mundo dos pactos", setting: "Cidades e ruínas.", rules: "Magia custa lembranças." };

test("saving the creator produces only a reusable scenario and returns to library", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const user = userEvent.setup();
  let saved = false;
  let starts = 0;
  server.use(
    http.post(`${API}/create/message`, () => HttpResponse.json({ reply: "As regras estão prontas.", ready: true })),
    http.post(`${API}/create/scenario`, () => { saved = true; return HttpResponse.json({ scenario_id: scenario.id }); }),
    http.get(`${API}/scenarios`, () => HttpResponse.json({ scenarios: saved ? [scenario] : [] })),
    http.post(`${API}/scenarios/:id/start`, () => { starts += 1; return HttpResponse.json({ game_id: "unexpected" }); }),
  );
  const application = await mountApp();
  await user.click(screen.getByRole("button", { name: /crie um mundo/i }));
  await user.type(screen.getByPlaceholderText(/descreva seu mundo/i), "Magia custa lembranças.");
  await user.click(screen.getByRole("button", { name: /^enviar$/i }));
  await screen.findByText("As regras estão prontas.");
  await user.click(screen.getByRole("button", { name: /^salvar cenário$/i }));
  await screen.findByText(scenario.title);
  expect(starts).toBe(0);
  expect(application.state.active).toBeNull();
  expect(application.state.view).toBe("library");
});

test("the same scenario can start two adventures with separate premises", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const user = userEvent.setup();
  const submittedPremises = [];
  server.use(
    http.get(`${API}/scenarios`, () => HttpResponse.json({ scenarios: [scenario] })),
    http.get(`${API}/scenarios/:id`, () => HttpResponse.json(scenario)),
    http.post(`${API}/scenarios/:id/start`, async ({ request }) => {
      submittedPremises.push((await request.json()).premise);
      return HttpResponse.json({ game_id: `adventure-${submittedPremises.length}` });
    }),
  );
  const application = await mountApp();
  await user.click(screen.getByRole("button", { name: /^jogar/i }));
  await user.click(await screen.findByRole("button", { name: /nova aventura neste cenário/i }));
  await user.type(await screen.findByLabelText(/seu personagem e a situação inicial/i), "Uma cartógrafa perdida.");
  await user.click(screen.getByRole("button", { name: /^iniciar aventura$/i }));
  await waitFor(() => expect(application.state.active?.id).toBe("adventure-1"));
  const { onAction } = await import("../src/app/ui.js");
  onAction("go-library", { dataset: {} });
  await user.click(await screen.findByRole("button", { name: /nova aventura neste cenário/i }));
  const secondPremise = await screen.findByLabelText(/seu personagem e a situação inicial/i);
  expect(secondPremise.value).toBe("");
  await user.type(secondPremise, "Um ferreiro da capital.");
  await user.click(screen.getByRole("button", { name: /^iniciar aventura$/i }));
  await waitFor(() => expect(application.state.active?.id).toBe("adventure-2"));
  expect(submittedPremises).toEqual(["Uma cartógrafa perdida.", "Um ferreiro da capital."]);
});

test("failed adventure creation keeps the premise for retry", async () => {
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const user = userEvent.setup();
  server.use(
    http.get(`${API}/scenarios`, () => HttpResponse.json({ scenarios: [scenario] })),
    http.get(`${API}/scenarios/:id`, () => HttpResponse.json(scenario)),
    http.post(`${API}/scenarios/:id/start`, () => HttpResponse.json({ detail: "Geração incompleta. Tente novamente." }, { status: 409 })),
  );
  await mountApp();
  await user.click(screen.getByRole("button", { name: /^jogar/i }));
  await user.click(await screen.findByRole("button", { name: /nova aventura neste cenário/i }));
  await user.type(await screen.findByLabelText(/seu personagem e a situação inicial/i), "Uma viajante.");
  await user.click(screen.getByRole("button", { name: /^iniciar aventura$/i }));
  await screen.findByRole("alert");
  expect(screen.getByLabelText(/seu personagem e a situação inicial/i).value).toBe("Uma viajante.");
  expect(screen.getByRole("button", { name: /^iniciar aventura$/i }).disabled).toBe(false);
});
