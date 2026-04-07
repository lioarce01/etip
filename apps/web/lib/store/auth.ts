"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { User, Tenant } from "@/types/api";

interface AuthState {
  token: string | null;
  user: User | null;
  tenant: Tenant | null;
  availableTenants: Tenant[];
  setAuth: (token: string, user: User, tenant: Tenant) => void;
  setAvailableTenants: (tenants: Tenant[]) => void;
  setToken: (token: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      tenant: null,
      availableTenants: [],
      setAuth: (token, user, tenant) => set({ token, user, tenant }),
      setAvailableTenants: (availableTenants) => set({ availableTenants }),
      setToken: (token) => set({ token }),
      clearAuth: () => set({ token: null, user: null, tenant: null, availableTenants: [] }),
    }),
    {
      name: "etip-auth",
      storage: createJSONStorage(() => sessionStorage),
    }
  )
);
