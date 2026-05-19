import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { AlertCircle, Atom, CheckCircle2, Eye, EyeOff, ShieldCheck, Target, Users } from "lucide-react";
import { authApi, systemApi } from "@/api/endpoints";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoader } from "@/components/ui/spinner";
import { useAuthStore } from "@/stores/auth";

const DEMO_USERS = [
  { role: "Admin", email: "admin@atomquest.app", password: "Admin@123" },
  { role: "Manager", email: "manager@atomquest.app", password: "Manager@123" },
  { role: "Employee", email: "employee@atomquest.app", password: "Employee@123" },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const { data: capabilities, isLoading: loadingCapabilities, isError: capabilitiesError } = useQuery({
    queryKey: ["systemCapabilities"],
    queryFn: systemApi.capabilities,
    retry: 1,
    retryDelay: 800,
    // Never block the UI forever — treat missing backend as "show password form"
    staleTime: 0,
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const [searchParams] = useSearchParams();
  const ssoError = searchParams.get("sso_error");

  const SSO_ERROR_MESSAGES: Record<string, string> = {
    user_not_provisioned:
      "Your Microsoft account is not linked to an AtomQuest account. Contact your administrator.",
    token_exchange_failed: "Microsoft sign-in failed. Please try again.",
    graph_fetch_failed: "Could not retrieve your Microsoft profile. Please try again.",
    no_email_in_profile:
      "Your Microsoft account does not have an accessible email address.",
    missing_code: "The sign-in flow was interrupted. Please try again.",
    access_denied: "You cancelled the Microsoft sign-in.",
  };
  const ssoErrorMessage =
    ssoError ? (SSO_ERROR_MESSAGES[ssoError] ?? `Microsoft sign-in error: ${ssoError}`) : null;

  // When backend is offline/not yet deployed — show a brief loader only, never block forever
  if (loadingCapabilities) return <PageLoader />;

  // Fallback caps when backend unreachable: show password form, hide SSO
  const effectiveCaps = capabilities ?? (capabilitiesError ? { auth: { password: true, microsoft_sso: false }, demo_mode: false } : null);
  if (!effectiveCaps) return <PageLoader />;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const { access_token } = await authApi.login({ email, password });
      useAuthStore.setState({ token: access_token });
      const user = await authApi.me();
      setAuth(access_token, user);
      navigate("/", { replace: true });
    } catch (err: unknown) {
      if (
        err &&
        typeof err === "object" &&
        "response" in err &&
        (err as { response?: { status?: number } }).response?.status === 401
      ) {
        setError("Invalid email or password");
      } else {
        setError("Unable to sign in right now. Please try again shortly.");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleMicrosoftSignIn = async () => {
    setError("");
    setLoading(true);
    try {
      const { authorization_url } = await authApi.microsoftStart();
      window.location.href = authorization_url;
    } catch (err) {
      const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
      setError(typeof detail === "string" ? detail : "Microsoft sign-in is unavailable.");
      setLoading(false);
    }
  };

  return (
    <div className="grid min-h-screen bg-[var(--background)] lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden overflow-hidden border-r border-[var(--border)] bg-[#102426] p-10 text-white lg:flex lg:flex-col">
        <div className="absolute inset-0 opacity-30 [background-image:linear-gradient(rgba(255,255,255,.08)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.08)_1px,transparent_1px)] [background-size:44px_44px]" />
        <div className="relative flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-white text-[var(--primary)]">
            <Atom className="h-5 w-5" />
          </div>
          <div>
            <p className="text-lg font-semibold">AtomQuest</p>
            <p className="text-sm text-white/60">Goal Setting & Tracking Portal</p>
          </div>
        </div>

        <div className="relative mt-auto max-w-2xl">
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            className="page-kicker text-emerald-100"
          >
            FY2026 performance operations
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.05 }}
            className="mt-4 text-5xl font-semibold leading-tight"
          >
            Goals, approvals, check-ins, and escalations in one workbench.
          </motion.h1>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12 }}
            className="mt-8 grid grid-cols-3 gap-3"
          >
            {[
              { icon: Target, label: "100% weightage guard" },
              { icon: Users, label: "Manager approval queue" },
              { icon: ShieldCheck, label: "Audit-ready locking" },
            ].map((item) => (
              <div key={item.label} className="rounded-lg border border-white/15 bg-white/8 p-4">
                <item.icon className="mb-3 h-5 w-5 text-emerald-200" />
                <p className="text-sm text-white/80">{item.label}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      <section className="flex items-center justify-center px-5 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="w-full max-w-md"
        >
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--primary)] text-white">
              <Atom className="h-5 w-5" />
            </div>
            <div>
              <p className="text-lg font-semibold">AtomQuest</p>
              <p className="text-xs text-[var(--muted-foreground)]">Goal operations portal</p>
            </div>
          </div>

          <div className="rounded-lg border border-[var(--border)] bg-white p-6 shadow-sm">
            <p className="page-kicker">Secure workspace</p>
            <h2 className="mt-2 text-2xl font-semibold">Sign in</h2>
            <p className="mt-1 text-sm text-[var(--muted-foreground)]">
              Sign in to continue into the goal operations workspace.
            </p>

            {effectiveCaps?.auth.password && (
              <form onSubmit={handleSubmit} className="mt-6 space-y-4">
                {ssoErrorMessage && (
                  <div className="flex items-center gap-2 rounded-lg bg-amber-50 px-3 py-2.5 text-sm text-amber-800" role="alert">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {ssoErrorMessage}
                  </div>
                )}
                <div className="space-y-2">
                  <label htmlFor="email" className="text-sm font-medium">
                    Email
                  </label>
                  <Input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>

                <div className="space-y-2">
                  <label htmlFor="password" className="text-sm font-medium">
                    Password
                  </label>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                      autoComplete="current-password"
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((value) => !value)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] transition-colors hover:text-[var(--foreground)]"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>

                {error && (
                  <div className="flex items-center gap-2 rounded-lg bg-rose-50 px-3 py-2.5 text-sm text-rose-700" role="alert">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    {error}
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={loading || !email || !password}>
                  {loading ? "Signing in..." : "Sign in"}
                </Button>
              </form>
            )}

            {effectiveCaps?.auth.microsoft_sso && (
              <div className={effectiveCaps?.auth.password ? "mt-4" : "mt-6"}>
                <Button type="button" variant="outline" className="w-full" onClick={handleMicrosoftSignIn} disabled={loading}>
                  {loading ? "Preparing..." : "Sign in with Microsoft"}
                </Button>
              </div>
            )}

            {!effectiveCaps?.auth.password && !effectiveCaps?.auth.microsoft_sso && (
              <div className="mt-6 rounded-lg bg-[var(--secondary)] px-4 py-3 text-sm text-[var(--muted-foreground)]">
                No authentication method is enabled for this environment.
              </div>
            )}
          </div>

          {effectiveCaps?.demo_mode && (
          <div className="mt-4 rounded-lg border border-[var(--border)] bg-white/80 p-3">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[var(--muted-foreground)]">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              Demo credentials
            </div>
            <div className="grid gap-2">
              {DEMO_USERS.map((demo) => (
                <button
                  key={demo.role}
                  type="button"
                  onClick={() => {
                    setEmail(demo.email);
                    setPassword(demo.password);
                  }}
                  className="flex items-center justify-between rounded-md bg-[var(--secondary)] px-3 py-2 text-left text-xs transition-colors hover:bg-[var(--accent)]"
                >
                  <span className="font-medium text-[var(--foreground)]">{demo.role}</span>
                  <span className="font-mono text-[var(--muted-foreground)]">{demo.email}</span>
                </button>
              ))}
            </div>
          </div>
          )}
        </motion.div>
      </section>
    </div>
  );
}
