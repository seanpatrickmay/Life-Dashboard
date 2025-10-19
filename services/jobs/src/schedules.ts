export const cronSchedules = {
  nightlyRecompute: '0 3 * * *',
  staleSyncAlert: '0 */6 * * *'
};

export const CRON_TASKS = {
  nightlyRecompute: {
    description: 'Recompute readiness, trends, and nutrition compliance nightly',
    handler: 'services/jobs/src/recompute-nightly'
  },
  staleSyncAlert: {
    description: 'Send alerts if any connection has not synced for 48h',
    handler: 'services/jobs/src/stale-sync'
  }
};
