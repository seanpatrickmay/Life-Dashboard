import type { NextFunction, Request, Response } from 'express';
import { randomUUID } from 'node:crypto';
import { performance } from 'node:perf_hooks';

import { logger } from './logger';

export function requestLogger() {
  return function requestLoggerMiddleware(req: Request, res: Response, next: NextFunction) {
    const start = performance.now();
    const requestId = randomUUID();
    (req as any).id = requestId;

    logger.info({ event: 'request:start', req, requestId });

    res.on('finish', () => {
      const duration = Number((performance.now() - start).toFixed(2));
      logger.info({ event: 'request:complete', res, requestId, duration });
    });

    res.on('close', () => {
      if (!res.writableEnded) {
        const duration = Number((performance.now() - start).toFixed(2));
        logger.warn({ event: 'request:aborted', requestId, duration });
      }
    });

    next();
  };
}

export function healthHandler(serviceName: string) {
  return (_req: Request, res: Response) => {
    res.json({
      status: 'ok',
      service: serviceName,
      timestamp: new Date().toISOString()
    });
  };
}
