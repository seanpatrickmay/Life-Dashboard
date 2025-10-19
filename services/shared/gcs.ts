import { Storage } from '@google-cloud/storage';

import { optionalEnv, requireEnv } from './env';
import { logger } from './logger';

const projectId = optionalEnv('GCP_PROJECT_ID');
const keyFile = optionalEnv('GOOGLE_APPLICATION_CREDENTIALS');

export const storage = new Storage({
  projectId,
  keyFilename: keyFile
});

const bucketName = requireEnv('GCS_BUCKET_RAW');
export const rawBucket = storage.bucket(bucketName);

export async function writeRawPayload(prefix: string, id: string | number, payload: unknown) {
  const objectName = `${prefix}/${id}-${Date.now()}.json`;
  const file = rawBucket.file(objectName);
  let data: string | Buffer;
  if (typeof payload === 'string' || payload instanceof Buffer) {
    data = payload;
  } else {
    data = JSON.stringify(payload);
  }

  logger.debug({ objectName }, 'writing raw payload to GCS');
  await file.save(data, { contentType: 'application/json' });
  return objectName;
}
