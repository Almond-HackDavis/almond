import Image from "next/image";
import { cn } from "@/lib/cn";

interface WordmarkProps {
  variant?: "wordmark" | "mark";
  className?: string;
  height?: number;
}

/** Brand wordmark / standalone mark. SVG sources are mirrored from
 *  almond-app/Almond/Assets.xcassets — keep in sync. */
export function Wordmark({ variant = "wordmark", className, height = 28 }: WordmarkProps) {
  const src = variant === "wordmark" ? "/almond-wordmark.svg" : "/almond-mark.svg";
  const aspect = variant === "wordmark" ? 829.62 / 237.12 : 1;
  return (
    <Image
      src={src}
      alt="Almond"
      height={height}
      width={Math.round(height * aspect)}
      className={cn("select-none", className)}
      priority
    />
  );
}
