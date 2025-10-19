interface ProgressRingProps {
  value: number;
  max?: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
}

export function ProgressRing({ value, max = 100, size = 64, strokeWidth = 8, label }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const percent = Math.min(100, Math.max(0, (value / max) * 100));
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div style={{ width: size, height: size }} className="relative inline-flex items-center justify-center">
      <svg width={size} height={size}>
        <circle
          stroke="hsl(var(--muted-foreground))"
          fill="transparent"
          strokeWidth={strokeWidth}
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          stroke="hsl(var(--primary))"
          fill="transparent"
          strokeWidth={strokeWidth}
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={offset}
          strokeLinecap="round"
          r={radius}
          cx={size / 2}
          cy={size / 2}
          className="transition-all duration-500"
        />
      </svg>
      <span className="absolute text-sm font-semibold">
        {Math.round(percent)}
        <span className="text-xs">%</span>
      </span>
      {label ? <span className="sr-only">{label}</span> : null}
    </div>
  );
}
