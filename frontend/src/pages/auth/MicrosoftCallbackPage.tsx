/**
 * MicrosoftCallbackPage
 *
 * Receives the AtomQuest JWT issued by the backend after a successful Entra
 * SSO exchange.  The backend redirects to:
 *
 *   /auth/callback#token=<jwt>         ← success
 *   /login?sso_error=<reason>          ← backend error (handled on LoginPage)
 *
 * The token is passed in the URL *fragment* (hash) so it is never sent to the
 * server or captured in access logs by reverse proxies.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertCircle, Atom, Loader2 } from "lucide-react";
import { authApi } from "@/api/endpoints";
import { useAuthStore } from "@/stores/auth";

type State = "loading" | "error";

function extractToken(): string | null {
  const hash = window.location.hash.slice(1); // strip leading "#"
  const params = new URLSearchParams(hash);
  return params.get("token");
}

export default function MicrosoftCallbackPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [state, setState] = useState<State>("loading");
  const [errorMsg, setErrorMsg] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function hydrate() {
      const token = extractToken();
      if (!token) {
        setErrorMsg("No authentication token was returned from Microsoft.");
        setState("error");
        return;
      }

      // Store the token so authApi.me() will send it in the Authorization header
      useAuthStore.setState({ token });

      try {
        const user = await authApi.me();
        if (!cancelled) {
          setAuth(token, user);
          navigate("/", { replace: true });
        }
      } catch {
        if (!cancelled) {
          // Token was present but invalid or user not found
          useAuthStore.setState({ token: null, user: null });
          setErrorMsg(
            "Your Microsoft account is not linked to an AtomQuest user. " +
              "Please contact your administrator.",
          );
          setState("error");
        }
      }
    }

    hydrate();
    return () => {
      cancelled = true;
    };
  }, [navigate, setAuth]);

  if (state === "loading") {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-[var(--background)]">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)] text-white">
          <Atom className="h-6 w-6" />
        </div>
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1, ease: "linear" }}
        >
          <Loader2 className="h-6 w-6 text-[var(--primary)]" />
        </motion.div>
        <p className="text-sm text-[var(--muted-foreground)]">
          Completing Microsoft sign-in…
        </p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[var(--background)] px-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[var(--primary)] text-white">
        <Atom className="h-6 w-6" />
      </div>
      <div className="w-full max-w-md rounded-lg border border-[var(--border)] bg-white p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-500" />
          <div>
            <p className="font-semibold text-[var(--foreground)]">
              Sign-in failed
            </p>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              {errorMsg}
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => navigate("/login", { replace: true })}
          className="mt-5 w-full rounded-md bg-[var(--primary)] py-2 text-sm font-medium text-white transition-opacity hover:opacity-90"
        >
          Back to sign-in
        </button>
      </div>
    </div>
  );
}
