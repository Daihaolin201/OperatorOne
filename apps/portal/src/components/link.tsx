"use client";
import { createNavigation } from "next-intl/navigation";
import { routing } from "@/i18n/routing";
import type { ComponentProps } from "react";

const { Link: NextIntlLink } = createNavigation(routing);

type LinkProps = ComponentProps<typeof NextIntlLink>;

export function Link({ className = "", ...props }: LinkProps) {
  return (
    <NextIntlLink
      className={["text-brand-600 hover:text-brand-700 hover:underline", className].join(" ")}
      {...props}
    />
  );
}
