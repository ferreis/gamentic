// Creator session persistence: chats survive refreshes via the stored
// session_id + GET /create/{session_id} (docs/frontend-api.md s0 item 7).

import { test, expect } from "vitest";
import { screen, waitFor } from "@testing-library/dom";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { server, mountApp } from "./setup.js";

const API = "http://localhost:8000";
const SESSION_KEY = "gamentic.creator.session";
const user = () => userEvent.setup({ delay: null });

test("an in-progress creation is restored after a refresh; Start over discards it", async () => {
  const u = user();
  server.use(
    http.get(`${API}/create/creator-abc`, () =>
      HttpResponse.json({
        session_id: "creator-abc",
        history: [
          { role: "user", content: "A haunted lighthouse." },
          { role: "assistant", content: "Storm-lashed rocks it is. Who joins you?" },
        ],
      }),
    ),
  );
  await mountApp(); // clears localStorage...
  localStorage.setItem(SESSION_KEY, "creator-abc"); // ...then simulate a pre-refresh session
  await u.click(screen.getByRole("button", { name: /crie um mundo/i }));

  expect(await screen.findByText(/retomamos de onde você parou/i)).toBeTruthy();
  expect(screen.getByText("A haunted lighthouse.")).toBeTruthy();
  expect(screen.getByText(/storm-lashed rocks/i)).toBeTruthy();

  await u.click(screen.getByRole("button", { name: /recomeçar/i }));
  expect(localStorage.getItem(SESSION_KEY)).toBeNull();
  await waitFor(() => expect(screen.queryByText("A haunted lighthouse.")).toBeNull());
});

test("an expired/unknown stored session starts clean and clears the stored id", async () => {
  const u = user();
  // no handler for GET /create/:id -> the catch-all 404s it
  await mountApp();
  localStorage.setItem(SESSION_KEY, "creator-gone");
  await u.click(screen.getByRole("button", { name: /crie um mundo/i }));

  expect(await screen.findByText(/conte sobre o mundo em que você quer jogar/i)).toBeTruthy();
  expect(screen.queryByText(/retomamos de onde você parou/i)).toBeNull();
  await waitFor(() => expect(localStorage.getItem(SESSION_KEY)).toBeNull());
});

test("sending a creator message stores the session id for a later restore", async () => {
  const u = user();
  server.use(http.post(`${API}/create/message`, () => HttpResponse.json({ reply: "Tell me more." })));
  await mountApp();
  await u.click(screen.getByRole("button", { name: /crie um mundo/i }));
  await u.type(screen.getByPlaceholderText(/descreva seu mundo/i), "A haunted lighthouse");
  await u.click(screen.getByRole("button", { name: /^enviar$/i }));

  expect(await screen.findByText("Tell me more.")).toBeTruthy();
  expect(localStorage.getItem(SESSION_KEY)).toMatch(/^creator-/);
});

test("focus returns to the creator chat box when the reply lands", async () => {
  server.use(http.post(`${API}/create/message`, () => HttpResponse.json({ reply: "A lighthouse. Good. What haunts it?" })));
  const u = user();
  await mountApp();
  await u.click(await screen.findByRole("button", { name: /crie um mundo/i }));
  const box = await screen.findByPlaceholderText(/descreva seu mundo/i);
  await u.type(box, "a haunted lighthouse");
  await u.click(screen.getByRole("button", { name: /^enviar$/i })); // focus lands on the button
  await screen.findByText(/what haunts it/i);
  // the reply landed: the keyboard comes back to the chat box on its own
  await waitFor(() => expect(document.activeElement).toBe(screen.getByPlaceholderText(/descreva seu mundo/i)));
});

test("the begin button stays locked until the world-builder signals ready, then unlocks", async () => {
  const u = user();
  let calls = 0;
  server.use(
    http.post(`${API}/create/message`, () => {
      calls += 1;
      return calls === 1
        ? HttpResponse.json({ reply: "What tone do you want?", ready: false })
        : HttpResponse.json({ reply: "Your world is complete. Say the word.", ready: true });
    }),
  );
  await mountApp();
  await u.click(screen.getByRole("button", { name: /crie um mundo/i }));
  // locked from the first breath: a fresh chat has no world yet
  const begin = () => screen.getByRole("button", { name: /iniciar/i });
  expect(begin().disabled).toBe(true);
  const box = screen.getByPlaceholderText(/descreva seu mundo/i);
  await u.type(box, "A haunted lighthouse");
  await u.click(screen.getByRole("button", { name: /^enviar$/i }));
  await screen.findByText(/what tone do you want/i);
  expect(begin().disabled).toBe(true);                       // builder not ready yet
  await u.type(screen.getByPlaceholderText(/descreva seu mundo/i), "Grim. A keeper. Survive the night.");
  await u.click(screen.getByRole("button", { name: /^enviar$/i }));
  await screen.findByText(/your world is complete/i);
  expect(begin().disabled).toBe(false);                      // the ready reply unlocks it
  expect(begin().textContent).toMatch(/iniciar a aventura/i);
});

test("a restored session that was already ready keeps the begin button unlocked", async () => {
  const u = user();
  server.use(
    http.get(`${API}/create/creator-abc`, () =>
      HttpResponse.json({
        session_id: "creator-abc",
        history: [
          { role: "user", content: "A haunted lighthouse." },
          { role: "assistant", content: "I'm ready to start the adventure whenever you are." },
        ],
        ready: true,
      }),
    ),
  );
  await mountApp();
  localStorage.setItem(SESSION_KEY, "creator-abc");
  await u.click(screen.getByRole("button", { name: /crie um mundo/i }));
  await screen.findByText(/retomamos de onde você parou/i);
  expect(screen.getByRole("button", { name: /iniciar a aventura/i }).disabled).toBe(false);
});
