const terminalJobStatuses = new Set(['completed', 'synced', 'success', 'done', 'failed', 'cancelled']);
const failedJobStatuses = new Set(['failed', 'cancelled']);

export function isTerminalJobStatus(status: string) {
  return terminalJobStatuses.has(status);
}

export function jobStatusClass(status: string) {
  if (failedJobStatuses.has(status)) {
    return 'failed';
  }
  if (terminalJobStatuses.has(status)) {
    return 'completed';
  }
  return 'active';
}

export function normalizedJobProgress(progress: number | null | undefined, status: string) {
  if (status === 'completed' || status === 'synced' || status === 'success' || status === 'done') {
    return 100;
  }
  const fallback = status === 'queued' ? 0 : 5;
  const value = Number.isFinite(progress) ? Number(progress) : fallback;
  return Math.max(0, Math.min(100, Math.round(value)));
}
