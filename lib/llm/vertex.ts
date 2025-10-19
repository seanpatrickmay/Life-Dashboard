import { VertexAI } from '@google-cloud/vertexai';
import type { ZodTypeAny } from 'zod';

import { assertEnv } from '@/lib/utils';

const DEFAULT_MODEL = 'gemini-1.5-pro';
const DEFAULT_LOCATION = 'us-central1';

type VertexClient = ReturnType<typeof createVertexClient>;

let cachedClient: VertexClient | null = null;

function createVertexClient() {
  const project = assertEnv('GCP_PROJECT_ID');
  const location = process.env.GCP_LOCATION ?? DEFAULT_LOCATION;
  const vertexAI = new VertexAI({ project, location });
  const modelName = process.env.VERTEX_MODEL ?? DEFAULT_MODEL;

  const generativeModel = vertexAI.getGenerativeModel({
    model: modelName,
    generationConfig: {
      response_mime_type: 'application/json',
      temperature: 0.3,
      top_p: 0.8
    },
    systemInstruction: {
      role: 'system',
      parts: [
        {
          text: `You are an endurance coach and precision nutritionist.
Return objective, data-backed insights grounded in the provided context.
Always respond with STRICT JSON matching the requested schema. Do not wrap the JSON in fences or add commentary.`
        }
      ]
    }
  });

  return {
    generativeModel,
    project,
    location,
    modelName
  };
}

function getClient(): VertexClient {
  if (!cachedClient) {
    cachedClient = createVertexClient();
  }
  return cachedClient;
}

export async function generateInsight(prompt: string, schema: ZodTypeAny) {
  const client = getClient();

  const result = await client.generativeModel.generateContent({
    contents: [
      {
        role: 'user',
        parts: [{ text: prompt }]
      }
    ]
  });

  const candidate = result.response?.candidates?.[0];
  if (!candidate) {
    throw new Error('Vertex returned no candidates');
  }

  const parts = candidate.content?.parts ?? [];
  const textPart = parts.find((part) => 'text' in part) as { text?: string } | undefined;
  const responseText = textPart?.text?.trim() ?? '';

  if (!responseText) {
    throw new Error('Vertex returned empty response');
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(responseText);
  } catch (error) {
    throw new Error(`Vertex returned invalid JSON: ${responseText} (${(error as Error).message})`);
  }

  try {
    return schema.parse(parsed);
  } catch (error) {
    throw new Error(`Vertex response failed validation: ${(error as Error).message}`);
  }
}
