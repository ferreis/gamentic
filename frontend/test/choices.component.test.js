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
  await user.click(within(alternatives).getByRole("button", { name: /alternativa 5/i }));
  await waitFor(() => expect(submitted).toHaveLength(1));
  expect(submitted[0].segments).toEqual([{ type: "say", text: "Minha resposta 5." }]);
  await waitFor(() => expect(document.querySelector("#cmpInput").getAttribute("contenteditable")).toBe("true"));
  await user.type(document.querySelector("#cmpInput"), "Vou fazer algo diferente.");
  await user.keyboard("{Enter}");
  await waitFor(() => expect(submitted).toHaveLength(2));
  expect(submitted[1].segments[0].text).toBe("Vou fazer algo diferente.");
});
