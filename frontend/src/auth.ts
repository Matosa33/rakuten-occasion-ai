// Cycle 15 (D-032) - gestion du token JWT côté client.
//
// Pattern minimal sans router ni Context : un store externe (localStorage +
// listeners) consommé par App via `useSyncExternalStore`. Le 401 intercepté
// dans api.ts appelle `clearToken()` → App re-render → LoginPage.

const STORAGE_KEY = "rakuten_token";

type Listener = () => void;
const listeners = new Set<Listener>();

function notify() {
  for (const l of listeners) l();
}

export function subscribe(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(STORAGE_KEY, token);
  notify();
}

export function clearToken() {
  localStorage.removeItem(STORAGE_KEY);
  notify();
}

/** OAuth2 password flow (D-032) : form-urlencoded → { access_token, token_type }. */
export async function login(username: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });
  if (!res.ok) {
    if (res.status === 401) throw new Error("Identifiants invalides");
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof detail.detail === "string" ? detail.detail : `Erreur ${res.status}`
    );
  }
  const body = (await res.json()) as { access_token: string };
  setToken(body.access_token);
}
