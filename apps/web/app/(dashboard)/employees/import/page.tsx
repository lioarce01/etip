"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, CheckCircle, AlertCircle, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { useImportCSV } from "@/lib/hooks/use-employees";
import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { CSVImportResult } from "@/types/api";

export default function ImportPage() {
  const { mutateAsync, isPending } = useImportCSV();
  const [result, setResult] = useState<CSVImportResult | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;
      try {
        const res = await mutateAsync(file);
        setResult(res);
        toast.success(`Import complete: ${res.created} created, ${res.updated} updated`);
      } catch {
        toast.error("Import failed. Check the file and try again.");
      }
    },
    [mutateAsync]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "text/csv": [".csv"] },
    maxFiles: 1,
    disabled: isPending,
  });

  if (result) {
    return (
      <div className="space-y-6 max-w-xl">
        <PageHeader title="Import Employees" />

        <div className="rounded-lg border border-[var(--gray-200)] bg-background p-6 space-y-4">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle className="h-5 w-5" />
            <span className="font-medium">Import complete</span>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--gray-500)]">Created</span>
              <span className="text-foreground font-medium">{result.created}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--gray-500)]">Updated</span>
              <span className="text-foreground font-medium">{result.updated}</span>
            </div>
            {result.errors.length > 0 && (
              <div>
                <div className="flex justify-between">
                  <span className="text-amber-700">Errors</span>
                  <span className="text-amber-700 font-medium">
                    {result.errors.length}
                  </span>
                </div>
                <div className="mt-2 rounded border border-amber-200 bg-amber-50 p-3 space-y-1">
                  {result.errors.map((e, i) => (
                    <div key={i} className="flex gap-2 text-xs text-amber-700">
                      <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                      <span>
                        Row {e.row}: {e.message}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        <Button
          variant="outline"
          onClick={() => setResult(null)}
        >
          <RefreshCw className="h-4 w-4" /> Import another file
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-xl">
      <PageHeader title="Import Employees" />

      <div
        {...getRootProps()}
        className={cn(
          "flex flex-col items-center justify-center rounded-lg border-2 border-dashed p-16 text-center cursor-pointer transition-colors",
          isDragActive
            ? "border-[var(--blue-600)] bg-[var(--blue-600)]/5"
            : "border-[var(--gray-200)] hover:border-[var(--gray-300)]",
          isPending && "opacity-50 cursor-not-allowed"
        )}
      >
        <input {...getInputProps()} />
        <Upload className="h-8 w-8 text-[var(--gray-400)] mb-4" />
        {isPending ? (
          <p className="text-sm text-[var(--gray-500)]">Uploading...</p>
        ) : isDragActive ? (
          <p className="text-sm text-[var(--blue-600)]">Drop the CSV file here</p>
        ) : (
          <>
            <p className="text-sm text-foreground font-medium">
              Drag & drop a CSV file here
            </p>
            <p className="mt-1 text-xs text-[var(--gray-500)]">or click to browse</p>
            <p className="mt-4 text-xs text-[var(--gray-500)]">
              Required columns: <span className="text-foreground">email, full_name</span>
              <br />
              Optional: title, department
            </p>
          </>
        )}
      </div>

      <Button variant="ghost" size="sm" className="text-[var(--gray-500)]" asChild>
        <a href="/sample_employees.csv" download>
          Download sample CSV
        </a>
      </Button>
    </div>
  );
}
