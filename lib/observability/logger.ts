import pino, { type LoggerOptions } from 'pino';

const baseOptions: LoggerOptions = {
  level: process.env.LOG_LEVEL ?? 'info',
  redact: {
    paths: ['req.headers.authorization', 'req.headers.cookie', 'res.headers["set-cookie"]'],
    remove: true
  },
  serializers: {
    req(request: Record<string, unknown>) {
      if (!request) return request;
      return {
        method: request.method,
        url: request.url,
        id: (request as any).id,
        remoteAddress: (request as any).ip ?? (request.connection as any)?.remoteAddress,
        userAgent: request.headers ? (request.headers as any)['user-agent'] : undefined
      };
    },
    res(response: Record<string, unknown>) {
      if (!response) return response;
      return {
        statusCode: response.statusCode,
        headers: (response as any).getHeaders?.()
      };
    }
  }
};

const prettyTransport =
  process.env.NODE_ENV === 'development'
    ? {
        target: 'pino-pretty',
        options: {
          colorize: true,
          translateTime: 'SYS:standard',
          singleLine: true
        }
      }
    : undefined;

export function createLogger(bindings?: Record<string, unknown>) {
  return pino(
    {
      ...baseOptions,
      transport: prettyTransport
    },
    bindings
  );
}

export const logger = createLogger();
