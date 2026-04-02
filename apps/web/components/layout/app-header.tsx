"use client";

import { usePathname } from "next/navigation";
import { Search } from "lucide-react";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "./command-palette";

const breadcrumbMap: Record<string, string> = {
  overview:   "Overview",
  employees:  "Employees",
  projects:   "Projects",
  connectors: "Connectors",
  users:      "Team",
  settings:   "Settings",
  import:     "Import",
  new:        "New",
};

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function segmentLabel(seg: string): string {
  if (UUID_RE.test(seg)) return "Detail";
  return breadcrumbMap[seg] ?? seg.charAt(0).toUpperCase() + seg.slice(1);
}

export function AppHeader() {
  const pathname = usePathname();
  const [paletteOpen, setPaletteOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const segments = pathname.split("/").filter(Boolean);
  const crumbs = segments.map(segmentLabel);

  return (
    <>
      <header className="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-[var(--gray-200)] bg-background/80 px-6 backdrop-blur-sm">
        {/* Breadcrumb */}
        <nav className="flex items-center text-sm">
          {crumbs.map((crumb, i) => (
            <span key={i} className="flex items-center">
              {i > 0 && (
                <span className="mx-1.5 text-[var(--gray-300)]">/</span>
              )}
              <span
                className={
                  i === crumbs.length - 1
                    ? "font-medium text-foreground"
                    : "text-[var(--gray-500)]"
                }
              >
                {crumb}
              </span>
            </span>
          ))}
        </nav>

        {/* Search trigger */}
        <Button
          variant="secondary"
          size="sm"
          className="w-52 justify-start gap-2 text-[var(--gray-500)]"
          onClick={() => setPaletteOpen(true)}
        >
          <Search className="h-3.5 w-3.5 shrink-0" />
          <span className="flex-1 text-left">Search...</span>
          <kbd className="ml-auto font-mono text-[10px] bg-[var(--gray-100)] px-1.5 py-0.5 rounded border border-[var(--gray-200)]">
            ⌘K
          </kbd>
        </Button>
      </header>

      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </>
  );
}
