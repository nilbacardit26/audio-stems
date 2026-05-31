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
