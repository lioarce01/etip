"use client";

import { create } from "zustand";
import type { User, Tenant } from "@/types/api";

interface AuthState {
  token: string | null;
  user: User | null;
  tenant: Tenant | null;
  setAuth: (token: string, user: User, tenant: Tenant) => void;
  setToken: (token: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()((set) => ({
  token: null,
  user: null,
  tenant: null,
  setAuth: (token, user, tenant) => set({ token, user, tenant }),
  setToken: (token) => set({ token }),
  clearAuth: () => set({ token: null, user: null, tenant: null }),
}));
