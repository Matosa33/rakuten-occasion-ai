// Cycle 15 (D-032) - page de connexion JWT stub démo.
// Style cohérent avec le flow vendeur (rose/slate, carte blanche).

import { useState } from "react";
import { motion } from "framer-motion";
import { login } from "../auth";

export function LoginPage() {
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(username, password);
      // setToken (dans login) notifie le store → App re-render sur le flow.
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erreur inconnue");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-16">
      <header className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-rose-700">Vendez en un éclair ⚡</h1>
        <p className="mt-2 text-slate-600">Connectez-vous pour créer vos annonces.</p>
      </header>

      <motion.form
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        onSubmit={onSubmit}
        className="rounded-2xl bg-white p-6 shadow-sm"
      >
        <label className="block text-sm font-medium text-slate-700">Identifiant</label>
        <input
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          autoComplete="username"
          className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-slate-800 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
        />

        <label className="mt-4 block text-sm font-medium text-slate-700">Mot de passe</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
          placeholder="démo : demo"
          className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-slate-800 outline-none focus:border-rose-400 focus:ring-2 focus:ring-rose-100"
        />

        {error && (
          <div className="mt-4 rounded-lg border border-rose-300 bg-rose-50 p-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !username || !password}
          className="mt-6 w-full rounded-xl bg-rose-600 py-3 font-semibold text-white transition hover:bg-rose-700 disabled:opacity-40"
        >
          {loading ? "Connexion…" : "Se connecter"}
        </button>

        <p className="mt-4 text-center text-xs text-slate-400">
          Compte de démonstration : <code>demo</code> / <code>demo</code>
        </p>
      </motion.form>
    </div>
  );
}
