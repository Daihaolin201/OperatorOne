"use client";
import { Link as NextIntlLink } from "next-intl/routing";
import type { ComponentProps } from "react";

type LinkProps = ComponentProps<typeof NextIntlLink>;

export function Link({ className = "", ...props }: LinkProps) {
  return (
    <NextIntlLink
      className={["text-brand-600 hover:text-brand-700 hover:underline", className].join(" ")}
      {...props}
    />
  );
}
