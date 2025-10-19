import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface MetricCardProps {
  title: string;
  value: string;
  unit?: string;
  trend?: string;
  description?: string;
  status?: 'positive' | 'negative' | 'neutral';
}

const statusBadge: Record<NonNullable<MetricCardProps['status']>, string> = {
  positive: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-500/20 dark:text-emerald-300',
  negative: 'bg-red-100 text-red-700 dark:bg-red-500/20 dark:text-red-300',
  neutral: 'bg-muted text-muted-foreground'
};

export function MetricCard({ title, value, unit, trend, description, status = 'neutral' }: MetricCardProps) {
  return (
    <Card className="flex flex-col gap-3">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <div>
          <CardTitle className="text-base">{title}</CardTitle>
          {description ? <CardDescription>{description}</CardDescription> : null}
        </div>
        <Badge className={statusBadge[status]}>{trend ?? '—'}</Badge>
      </CardHeader>
      <CardContent>
        <p className="text-3xl font-semibold">
          {value}
          {unit ? <span className="ml-1 text-base text-muted-foreground">{unit}</span> : null}
        </p>
      </CardContent>
    </Card>
  );
}
