"use client";

import { useState } from "react";
import { Check, X, CheckCircle2, HelpCircle, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { AvatarInitials } from "@/components/shared/avatar-initials";
import { formatScore, formatPct } from "@/lib/utils";
import type { Recommendation } from "@/types/api";
import type { FeedbackValue } from "@/lib/constants";
import { cn } from "@/lib/utils";

interface CandidateMatchCardProps {
  rec: Recommendation;
  rank: number;
  onFeedback: (recommendationId: string, feedback: FeedbackValue, reason?: string) => Promise<void>;
}

export function CandidateMatchCard({
  rec,
  rank,
  onFeedback,
}: CandidateMatchCardProps) {
  const [submitting, setSubmitting] = useState(false);
  const [activeFeedback, setActiveFeedback] = useState<FeedbackValue | null>(
    rec.feedback ?? null
  );
  const [showRejectReason, setShowRejectReason] = useState(false);
  const [rejectReason, setRejectReason] = useState("");

  async function handleFeedback(feedback: FeedbackValue) {
    // On first reject click, show the reason textarea
    if (feedback === "rejected" && activeFeedback !== "rejected") {
      setShowRejectReason(true);
      return;
    }

    setSubmitting(true);
    try {
      const reason = feedback === "rejected" ? rejectReason : undefined;
      await onFeedback(rec.id, feedback, reason);
      setActiveFeedback(feedback);
      setShowRejectReason(false);
      setRejectReason("");
      toast.success(
        feedback === "accepted"
          ? "Candidate accepted"
          : feedback === "rejected"
          ? "Candidate rejected"
          : "Marked as maybe"
      );
    } catch {
      toast.error("Failed to submit feedback");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-[var(--gray-200)] bg-background p-5 space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xs text-[var(--gray-500)] font-mono">#{rank}</span>
          <AvatarInitials
            name={rec.employee.full_name}
            className="h-8 w-8"
          />
          <div>
            <p className="text-sm font-medium text-foreground">
              {rec.employee.full_name}
            </p>
            <p className="text-xs text-[var(--gray-500)]">
              {rec.employee.title ?? "Employee"} ·{" "}
              {rec.employee.department ?? "—"}
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="text-lg font-semibold tabular-nums text-foreground">
            {formatScore(rec.score)}
          </p>
          <p className="text-xs text-[var(--gray-500)]">score</p>
        </div>
      </div>

      {/* Score bar */}
      <div className="h-0.5 w-full rounded-full bg-[var(--gray-200)]">
        <div
          className="h-full rounded-full bg-[var(--blue-600)]"
          style={{ width: `${rec.score * 100}%` }}
        />
      </div>

      {/* Availability */}
      <p className="text-xs text-[var(--gray-500)]">
        Available: <span className="text-foreground font-medium">{formatPct(rec.availability_pct)}</span>
      </p>

      {/* Skill matches */}
      <div>
        <p className="mb-2 text-xs text-[var(--gray-500)] uppercase tracking-wider">
          Skills matched
        </p>
        <div className="flex flex-wrap gap-2">
          {rec.skill_matches.map((sm, i) => (
            <span
              key={i}
              className={cn(
                "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs",
                sm.matched
                  ? "border-green-600/30 text-green-700"
                  : "border-[var(--gray-200)] text-[var(--gray-500)]"
              )}
            >
              {sm.matched ? (
                <Check className="h-3 w-3" />
              ) : (
                <X className="h-3 w-3" />
              )}
              {sm.skill_label}
              {sm.required_level && (
                <span className="opacity-60">({sm.required_level})</span>
              )}
            </span>
          ))}
        </div>
      </div>

      {/* LLM Explanation */}
      {rec.explanation && (
        <div className="rounded border border-[var(--gray-200)] bg-[var(--gray-100)] px-4 py-3">
          <p className="text-xs text-[var(--gray-500)] italic leading-relaxed">
            &ldquo;{rec.explanation}&rdquo;
          </p>
        </div>
      )}

      {/* Feedback buttons */}
      <div className="flex items-center gap-2 pt-1">
        <Button
          size="sm"
          variant="outline"
          className={cn(
            "gap-1.5",
            activeFeedback === "accepted" &&
              "border-green-600/30 bg-green-50 text-green-700"
          )}
          disabled={submitting}
          onClick={() => handleFeedback("accepted")}
        >
          <CheckCircle2 className="h-4 w-4" /> Accept
        </Button>
        <Button
          size="sm"
          variant="outline"
          className={cn(
            "gap-1.5",
            activeFeedback === "maybe" &&
              "border-amber-500/30 bg-amber-50 text-amber-700"
          )}
          disabled={submitting}
          onClick={() => handleFeedback("maybe")}
        >
          <HelpCircle className="h-4 w-4" /> Maybe
        </Button>
        <Button
          size="sm"
          variant="outline"
          className={cn(
            "gap-1.5",
            activeFeedback === "rejected" &&
              "border-[var(--red-500)]/30 bg-red-50 text-[var(--red-500)]"
          )}
          disabled={submitting}
          onClick={() => handleFeedback("rejected")}
        >
          <XCircle className="h-4 w-4" /> Reject
        </Button>
      </div>

      {/* Rejection reason textarea */}
      {showRejectReason && activeFeedback !== "rejected" && (
        <div className="space-y-2 border-t border-[var(--gray-200)] pt-3">
          <label className="text-xs font-medium text-[var(--gray-500)] uppercase tracking-wider">
            Why reject? (optional)
          </label>
          <textarea
            className="w-full h-16 p-2 text-sm border border-[var(--gray-200)] rounded-md focus:outline-none focus:ring-2 focus:ring-[var(--blue-600)]"
            placeholder="Provide feedback for future improvements..."
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={submitting}
              onClick={() => handleFeedback("rejected")}
            >
              Confirm Rejection
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={submitting}
              onClick={() => {
                setShowRejectReason(false);
                setRejectReason("");
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
