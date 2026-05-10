"use client";

import { useId } from "react";

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  stroke?: string;
  fill?: string;
  strokeWidth?: number;
  className?: string;
}

/** Lightweight inline sparkline. SVG-only, no Recharts overhead. */
export function Sparkline({
  data,
  width = 120,
  height = 32,
  stroke = "var(--color-cocoa)",
  fill = "var(--color-cocoa)",
  strokeWidth = 1.5,
  className,
}: SparklineProps) {
  const id = useId().replace(/:/g, "");
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padX = 1;
  const padY = 4;
  const w = width - padX * 2;
  const h = height - padY * 2;
  const step = data.length > 1 ? w / (data.length - 1) : 0;

  const points = data.map((d, i) => {
    const x = padX + i * step;
    const y = padY + h - ((d - min) / range) * h;
    return [x, y] as const;
  });

  const linePath = points
    .map(([x, y], i) => (i === 0 ? `M${x.toFixed(2)},${y.toFixed(2)}` : `L${x.toFixed(2)},${y.toFixed(2)}`))
    .join(" ");

  const areaPath = `${linePath} L${(padX + w).toFixed(2)},${(padY + h).toFixed(2)} L${padX.toFixed(2)},${(padY + h).toFixed(2)} Z`;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id={`spark-${id}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={fill} stopOpacity="0.22" />
          <stop offset="100%" stopColor={fill} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#spark-${id})`} />
      <path d={linePath} fill="none" stroke={stroke} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
      <circle
        cx={points[points.length - 1][0]}
        cy={points[points.length - 1][1]}
        r={2.4}
        fill={stroke}
      />
    </svg>
  );
}
