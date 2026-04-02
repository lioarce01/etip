"use client";

import { Toaster as Sonner, type ToasterProps } from "sonner";

export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      toastOptions={{
        style: {
          background: "var(--background)",
          border: "1px solid var(--gray-200)",
          color: "var(--foreground)",
        },
      }}
      {...props}
    />
  );
}
