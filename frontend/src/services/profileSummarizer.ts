import { embedTexts } from './api';
import { loadProfile } from './interestProfile';

const EMBEDDING_CACHE_KEY = 'ld_embeddings';
const PROFILE_EMBEDDING_KEY = 'ld_profile_embedding';

type EmbeddingCache = Record<string, number[]>;

function loadEmbeddingCache(): EmbeddingCache {
  try {
    const raw = localStorage.getItem(EMBEDDING_CACHE_KEY);
    return raw ? JSON.parse(raw) : {};
  } catch { return {}; }
}

function saveEmbeddingCache(cache: EmbeddingCache): void {
  // Cap at 500 entries to prevent localStorage bloat
  const entries = Object.entries(cache);
  if (entries.length > 500) {
    const trimmed = Object.fromEntries(entries.slice(-500));
    localStorage.setItem(EMBEDDING_CACHE_KEY, JSON.stringify(trimmed));
  } else {
    localStorage.setItem(EMBEDDING_CACHE_KEY, JSON.stringify(cache));
  }
}

export function loadProfileEmbedding(): number[] | null {
  try {
    const raw = localStorage.getItem(PROFILE_EMBEDDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (Date.now() - parsed.timestamp > 7 * 24 * 60 * 60 * 1000) return null;
    return parsed.embedding;
  } catch { return null; }
}

function saveProfileEmbedding(embedding: number[]): void {
  localStorage.setItem(PROFILE_EMBEDDING_KEY, JSON.stringify({
    embedding,
    timestamp: Date.now(),
  }));
}

/** Serialize the interest profile into a natural language paragraph for embedding. */
export function serializeProfileForEmbedding(): string {
  const profile = loadProfile();
  const parts: string[] = [];

  // Collect all topics across layers, weighted by layer importance
  const topicScores: Record<string, number> = {};
  for (const [cat, entry] of Object.entries(profile.stable.categoryAffinity)) {
    topicScores[cat] = (topicScores[cat] || 0) + entry.reads * 3;
  }
  for (const [cat, entry] of Object.entries(profile.contextual.categoryAffinity)) {
    topicScores[cat] = (topicScores[cat] || 0) + entry.reads * 2;
  }
  for (const [cat, entry] of Object.entries(profile.ephemeral.categoryAffinity)) {
    topicScores[cat] = (topicScores[cat] || 0) + entry.reads;
  }

  const sortedTopics = Object.entries(topicScores)
    .sort((a, b) => b[1] - a[1])
    .map(([cat]) => cat);

  if (sortedTopics.length > 0) {
    parts.push(`Interested in: ${sortedTopics.join(', ')}.`);
  }

  // Add source preferences
  const sourceScores: Record<string, number> = {};
  for (const [src, entry] of Object.entries(profile.stable.sourceAffinity)) {
    sourceScores[src] = (sourceScores[src] || 0) + entry.reads;
  }
  const topSources = Object.entries(sourceScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([src]) => src);

  if (topSources.length > 0) {
    parts.push(`Prefers sources: ${topSources.join(', ')}.`);
  }

  return parts.join(' ') || 'General news reader with diverse interests.';
}

/** Get or compute the profile embedding. */
export async function getProfileEmbedding(): Promise<number[] | null> {
  const cached = loadProfileEmbedding();
  if (cached) return cached;

  try {
    const text = serializeProfileForEmbedding();
    const embeddings = await embedTexts([text]);
    if (embeddings.length > 0) {
      saveProfileEmbedding(embeddings[0]);
      return embeddings[0];
    }
  } catch { /* graceful degradation */ }
  return null;
}

/** Get embeddings for articles, using cache for already-embedded ones. */
export async function getArticleEmbeddings(
  articles: Array<{ id: string; title: string; summary: string | null }>,
): Promise<Map<string, number[]>> {
  const cache = loadEmbeddingCache();
  const result = new Map<string, number[]>();
  const uncached: Array<{ id: string; text: string }> = [];

  for (const article of articles) {
    if (cache[article.id]) {
      result.set(article.id, cache[article.id]);
    } else {
      uncached.push({
        id: article.id,
        text: `${article.title}. ${article.summary || ''}`.trim(),
      });
    }
  }

  if (uncached.length === 0) return result;

  try {
    const embeddings = await embedTexts(uncached.map(a => a.text));
    for (let i = 0; i < uncached.length; i++) {
      if (embeddings[i]) {
        cache[uncached[i].id] = embeddings[i];
        result.set(uncached[i].id, embeddings[i]);
      }
    }
    saveEmbeddingCache(cache);
  } catch { /* graceful degradation — return what we have from cache */ }

  return result;
}

/** Cosine similarity between two vectors. */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (a.length !== b.length || a.length === 0) return 0;
  let dot = 0, magA = 0, magB = 0;
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i];
    magA += a[i] * a[i];
    magB += b[i] * b[i];
  }
  const denom = Math.sqrt(magA) * Math.sqrt(magB);
  return denom === 0 ? 0 : dot / denom;
}
