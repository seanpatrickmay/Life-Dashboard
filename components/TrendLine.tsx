interface TrendLineProps {
  values: number[];
  height?: number;
  stroke?: string;
}

export function TrendLine({ values, height = 48, stroke = 'currentColor' }: TrendLineProps) {
  if (!values.length) {
    return <div className="h-12 text-sm text-muted-foreground">No data</div>;
  }

  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;

  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100;
      const y = ((max - value) / range) * 100;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg viewBox="0 0 100 100" className="h-12 w-full overflow-visible">
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={4}
        strokeLinecap="round"
        points={points}
        strokeLinejoin="round"
      />
    </svg>
  );
}
