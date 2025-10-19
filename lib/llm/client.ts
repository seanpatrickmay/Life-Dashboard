export interface GenerateInsightsPayload {
  userId: string;
  from: string;
  to: string;
  topics: Array<'daily' | 'weekly' | 'nutrition' | 'training' | 'custom'>;
}

export interface InsightSummary {
  topic: string;
  cached: boolean;
  summary: string;
  actions?: string[];
  bullets?: string[];
}

export async function generateInsights(payload: GenerateInsightsPayload) {
  const response = await fetch('/api/llm/insights', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      user_id: payload.userId,
      from: payload.from,
      to: payload.to,
      topics: payload.topics
    })
  });

  if (!response.ok) {
    throw new Error('Failed to generate insights');
  }

  const data = (await response.json()) as { data: InsightSummary[] };
  return data.data;
}
