"use client";

import { BarChart3, TrendingUp } from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { useAnalytics } from "@/lib/hooks/use-analytics";
import { PageHeader } from "@/components/shared/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPct } from "@/lib/utils";

function KpiCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-[var(--gray-500)] uppercase tracking-wider">
          {label}
        </p>
        <Icon className="h-4 w-4 text-[var(--gray-300)]" />
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: analytics, isLoading } = useAnalytics();

  const feedbackData = analytics
    ? [
        {
          name: "Accepted",
          value: analytics.accepted_count,
          fill: "#16a34a",
        },
        {
          name: "Rejected",
          value: analytics.rejected_count,
          fill: "#dc2626",
        },
        {
          name: "Maybe",
          value: analytics.maybe_count,
          fill: "#f59e0b",
        },
        {
          name: "No Feedback",
          value: analytics.no_feedback_count,
          fill: "#9ca3af",
        },
      ].filter((item) => item.value > 0)
    : [];

  return (
    <div className="space-y-8">
      <PageHeader title="Analytics" />

      {/* KPI Cards Row */}
      {isLoading ? (
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      ) : analytics ? (
        <div className="grid grid-cols-4 gap-4">
          <KpiCard
            label="Total Employees"
            value={analytics.total_employees}
            icon={BarChart3}
          />
          <KpiCard
            label="Total Projects"
            value={analytics.total_projects}
            icon={TrendingUp}
          />
          <KpiCard
            label="Total Recommendations"
            value={analytics.total_recommendations}
            icon={TrendingUp}
          />
          <KpiCard
            label="Acceptance Rate"
            value={formatPct(analytics.acceptance_rate)}
            icon={TrendingUp}
          />
        </div>
      ) : null}

      {/* Feedback Distribution Chart */}
      {isLoading ? (
        <Skeleton className="h-96 rounded-lg" />
      ) : analytics && feedbackData.length > 0 ? (
        <div className="rounded-lg border border-[var(--gray-200)] bg-background p-6">
          <h2 className="mb-4 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
            Feedback Distribution
          </h2>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={feedbackData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, value }) => `${name}: ${value}`}
                outerRadius={80}
                fill="#8884d8"
                dataKey="value"
              >
                {feedbackData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="rounded-lg border border-[var(--gray-200)] bg-background p-6 text-center text-sm text-[var(--gray-500)]">
          No feedback data yet
        </div>
      )}

      {/* Precision Table */}
      {isLoading ? (
        <Skeleton className="h-32 rounded-lg" />
      ) : analytics ? (
        <div className="rounded-lg border border-[var(--gray-200)] overflow-hidden">
          <div className="grid grid-cols-2 gap-4 border-b border-[var(--gray-200)] bg-[var(--gray-100)] px-4 py-2 text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
            <span>Metric</span>
            <span>Value</span>
          </div>
          <div className="divide-y divide-[var(--gray-200)]">
            <div className="grid grid-cols-2 gap-4 px-4 py-3 text-sm">
              <span className="text-foreground">Precision @ 5</span>
              <span className="text-[var(--gray-500)]">
                {formatPct(analytics.precision_at_5)}
              </span>
            </div>
            <div className="grid grid-cols-2 gap-4 px-4 py-3 text-sm">
              <span className="text-foreground">Precision @ 10</span>
              <span className="text-[var(--gray-500)]">
                {formatPct(analytics.precision_at_10)}
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
