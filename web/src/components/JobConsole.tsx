import { CircleCheck, CircleDashed, CircleX, LoaderCircle } from 'lucide-react';
import { isTerminalJobStatus, jobStatusClass, normalizedJobProgress } from '../jobStatus';
import type { SeparationJob } from '../types';

type Props = {
  job: SeparationJob | null;
};

export function JobConsole({ job }: Props) {
  if (!job) {
    return (
      <section className="console-panel">
        <div className="panel-heading">
          <div>
            <h2>Run output</h2>
            <p>Process output will stream here while a separation job is running.</p>
          </div>
        </div>
        <pre className="console-output">No active job.</pre>
      </section>
    );
  }

  const Icon =
    isTerminalJobStatus(job.status) && jobStatusClass(job.status) === 'completed'
      ? CircleCheck
      : jobStatusClass(job.status) === 'failed'
        ? CircleX
        : job.status === 'running'
          ? LoaderCircle
          : CircleDashed;
  const statusClass = jobStatusClass(job.status);
  const progress = normalizedJobProgress(job.progress, job.status);

  return (
    <section className="console-panel">
      <div className="panel-heading">
        <div>
          <h2>Run output</h2>
          <p>{job.commandLine}</p>
        </div>
        <span className={`status-badge ${statusClass}`}>
          <Icon size={17} />
          {job.status}
        </span>
      </div>
      <div
        aria-label="Job progress"
        aria-valuemax={100}
        aria-valuemin={0}
        aria-valuenow={progress}
        className={`progress-meter ${statusClass}`}
        role="progressbar"
      >
        <div className="progress-track">
          <span style={{ width: `${progress}%` }} />
        </div>
        <strong>{progress}%</strong>
      </div>
      {job.error ? <p className="inline-error">{job.error}</p> : null}
      <pre className="console-output">{job.output.length ? job.output.join('\n') : 'Waiting for output...'}</pre>
    </section>
  );
}
