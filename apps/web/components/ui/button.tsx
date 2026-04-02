"use client";
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cn } from "@/lib/utils";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "destructive" | "link";
  size?: "default" | "sm" | "lg" | "icon" | "icon-sm";
  asChild?: boolean;
}

const variantClasses: Record<string, string> = {
  primary:     "bg-foreground text-background hover:opacity-90",
  secondary:   "bg-background text-foreground border border-[var(--gray-200)] hover:bg-[var(--gray-100)]",
  outline:     "bg-background text-foreground border border-[var(--gray-200)] hover:bg-[var(--gray-100)]",
  ghost:       "text-[var(--gray-500)] hover:text-foreground hover:bg-[var(--gray-100)]",
  destructive: "bg-[var(--red-500)] text-white hover:opacity-90",
  link:        "text-[var(--blue-600)] underline-offset-4 hover:underline p-0 h-auto",
};

const sizeClasses: Record<string, string> = {
  default:   "h-9 px-4 text-sm",
  sm:        "h-8 px-3 text-sm",
  lg:        "h-10 px-6 text-sm",
  icon:      "h-9 w-9",
  "icon-sm": "h-7 w-7",
};

export function buttonVariants({ variant = "primary", size = "default", className = "" }: { variant?: ButtonProps["variant"]; size?: ButtonProps["size"]; className?: string } = {}) {
  return cn(
    "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--blue-600)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap",
    variantClasses[variant ?? "primary"] ?? variantClasses.primary,
    sizeClasses[size ?? "default"] ?? sizeClasses.default,
    className
  );
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "default", asChild = false, className, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--blue-600)] focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 whitespace-nowrap",
          variantClasses[variant] ?? variantClasses.primary,
          sizeClasses[size] ?? sizeClasses.default,
          className
        )}
        {...props}
      />
    );
  }
);
Button.displayName = "Button";
