export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--gray-100)] px-4 py-12">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="mb-8 text-center">
          <span className="text-lg font-semibold tracking-tight text-foreground">
            ◆ ETIP
          </span>
        </div>

        {/* Card */}
        <div className="rounded-lg border border-[var(--gray-200)] bg-background p-8">
          {children}
        </div>
      </div>
    </div>
  );
}
