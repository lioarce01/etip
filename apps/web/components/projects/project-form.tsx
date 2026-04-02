"use client";

import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SKILL_LEVELS, PROJECT_STATUSES } from "@/lib/constants";
import type { CreateProjectPayload } from "@/lib/api/projects";

const skillSchema = z.object({
  skill_label: z.string().min(1, "Skill name required"),
  level: z.enum(["junior", "mid", "senior"]),
  weight: z.number().min(0.1).max(1),
});

const projectSchema = z.object({
  name: z.string().min(1, "Name is required"),
  description: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
  status: z.enum(["planning", "active", "completed", "on_hold"]),
  required_skills: z.array(skillSchema),
});

type ProjectFormValues = z.infer<typeof projectSchema>;

interface ProjectFormProps {
  defaultValues?: Partial<ProjectFormValues>;
  onSubmit: (data: CreateProjectPayload) => Promise<void>;
  onCancel: () => void;
  isLoading?: boolean;
}

export function ProjectForm({
  defaultValues,
  onSubmit,
  onCancel,
  isLoading,
}: ProjectFormProps) {
  const form = useForm<ProjectFormValues>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      name: "",
      description: "",
      status: "planning",
      required_skills: [],
      ...defaultValues,
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: form.control,
    name: "required_skills",
  });

  async function handleSubmit(values: ProjectFormValues) {
    await onSubmit({
      name: values.name,
      description: values.description,
      start_date: values.start_date,
      end_date: values.end_date,
      status: values.status,
      required_skills: values.required_skills,
    });
  }

  return (
    <form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-5">
      <div className="space-y-1.5">
        <Label htmlFor="name">Name *</Label>
        <Input id="name" {...form.register("name")} />
        {form.formState.errors.name && (
          <p className="text-xs text-[var(--red-500)]">
            {form.formState.errors.name.message}
          </p>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="description">Description</Label>
        <Input id="description" {...form.register("description")} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="start_date">Start date</Label>
          <Input id="start_date" type="date" {...form.register("start_date")} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="end_date">End date</Label>
          <Input id="end_date" type="date" {...form.register("end_date")} />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>Status</Label>
        <Select
          defaultValue={form.getValues("status")}
          onValueChange={(v) =>
            form.setValue(
              "status",
              v as ProjectFormValues["status"]
            )
          }
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {PROJECT_STATUSES.map((s) => (
              <SelectItem key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Required Skills */}
      <div className="space-y-3">
        <Label>Required Skills</Label>
        {fields.length > 0 && (
          <div className="space-y-2">
            <div className="grid grid-cols-[1fr_1fr_80px_32px] gap-2 text-xs text-[var(--gray-500)]">
              <span>Skill label</span>
              <span>Level</span>
              <span>Weight</span>
              <span />
            </div>
            {fields.map((field, i) => (
              <div
                key={field.id}
                className="grid grid-cols-[1fr_1fr_80px_32px] gap-2 items-center"
              >
                <Input
                  placeholder="Python"
                  {...form.register(`required_skills.${i}.skill_label`)}
                />
                <Select
                  defaultValue={field.level}
                  onValueChange={(v) =>
                    form.setValue(
                      `required_skills.${i}.level`,
                      v as "junior" | "mid" | "senior"
                    )
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SKILL_LEVELS.map((l) => (
                      <SelectItem key={l} value={l}>
                        {l}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="1"
                  {...form.register(`required_skills.${i}.weight`, {
                    valueAsNumber: true,
                  })}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => remove(i)}
                >
                  <X className="h-4 w-4 text-[var(--gray-500)]" />
                </Button>
              </div>
            ))}
          </div>
        )}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() =>
            append({ skill_label: "", level: "mid", weight: 1.0 })
          }
        >
          <Plus className="h-4 w-4" /> Add skill
        </Button>
      </div>

      <div className="flex justify-end gap-3 pt-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={isLoading}>
          {isLoading ? "Saving..." : "Save Project"}
        </Button>
      </div>
    </form>
  );
}
