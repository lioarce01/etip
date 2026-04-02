import ky, { type KyInstance } from "ky";
import { API_BASE_URL } from "@/lib/constants";
import { useAuthStore } from "@/lib/store/auth";

let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

async function refreshToken(): Promise<string | null> {
  try {
    const data = await ky
      .post("/auth/refresh", { credentials: "include" })
      .json<{ access_token: string }>();
    return data.access_token;
  } catch {
    return null;
  }
}

export const apiClient: KyInstance = ky.create({
  prefixUrl: API_BASE_URL,
  credentials: "include",
  hooks: {
    beforeRequest: [
      (request) => {
        const token = useAuthStore.getState().token;
        if (token) {
          request.headers.set("Authorization", `Bearer ${token}`);
        }
      },
    ],
    afterResponse: [
      async (request, _options, response) => {
        if (response.status !== 401) return response;

        if (isRefreshing) {
          return new Promise<Response>((resolve) => {
            refreshQueue.push(async (newToken: string) => {
              request.headers.set("Authorization", `Bearer ${newToken}`);
              resolve(await fetch(request));
            });
          });
        }

        isRefreshing = true;
        const newToken = await refreshToken();
        isRefreshing = false;

        if (!newToken) {
          useAuthStore.getState().clearAuth();
          window.location.href = "/login";
          return response;
        }

        useAuthStore.getState().setToken(newToken);
        refreshQueue.forEach((cb) => cb(newToken));
        refreshQueue = [];

        request.headers.set("Authorization", `Bearer ${newToken}`);
        return fetch(request);
      },
    ],
  },
});
