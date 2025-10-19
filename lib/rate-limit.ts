type Bucket = {
  timestamps: number[];
};

const RATE_LIMIT_CACHE = new Map<string, Bucket>();

function getBucket(key: string) {
  let bucket = RATE_LIMIT_CACHE.get(key);
  if (!bucket) {
    bucket = { timestamps: [] };
    RATE_LIMIT_CACHE.set(key, bucket);
  }
  return bucket;
}

export interface RateLimitOptions {
  max: number;
  windowMs: number;
}

export function rateLimit(key: string, options: RateLimitOptions): { allowed: boolean; remaining: number } {
  const now = Date.now();
  const bucket = getBucket(key);

  bucket.timestamps = bucket.timestamps.filter((timestamp) => now - timestamp <= options.windowMs);

  if (bucket.timestamps.length >= options.max) {
    return {
      allowed: false,
      remaining: Math.max(options.windowMs - (now - bucket.timestamps[0]), 0)
    };
  }

  bucket.timestamps.push(now);

  return {
    allowed: true,
    remaining: options.max - bucket.timestamps.length
  };
}
