import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types/api";

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      logout: () => {
        set({ token: null, user: null });
        window.location.href = "/login";
      },
      isAuthenticated: () => !!get().token,
    }),
    {
      name: "atomquest-auth",
      partialize: (state) => ({ token: state.token, user: state.user }),
    },
  ),
);
