import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface LLMInsightCardProps {
  title: string;
  summary: string;
  bullets?: string[];
  actions?: string[];
  confidence?: number;
  timestamp: string;
}

export function LLMInsightCard({ title, summary, bullets, actions, confidence, timestamp }: LLMInsightCardProps) {
  const bulletItems = bullets && bullets.length > 0 ? bullets : ['No highlights available'];
  const actionItems = actions && actions.length > 0 ? actions : ['No actions supplied'];
  const confidenceDisplay = confidence !== undefined ? (confidence * 100).toFixed(0) : '—';

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>
          Generated {new Date(timestamp).toLocaleString()} · Confidence {confidenceDisplay}%
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm leading-relaxed text-muted-foreground">{summary}</p>
        <div>
          <h4 className="text-sm font-semibold uppercase text-muted-foreground">Highlights</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {bulletItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
        <div>
          <h4 className="text-sm font-semibold uppercase text-muted-foreground">Suggested actions</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {actionItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
