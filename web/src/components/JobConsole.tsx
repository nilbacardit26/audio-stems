import { CircleCheck, CircleDashed, CircleX, LoaderCircle } from 'lucide-react';
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
    job.status === 'completed'
      ? CircleCheck
      : job.status === 'failed'
        ? CircleX
        : job.status === 'running'
          ? LoaderCircle
          : CircleDashed;

  return (
    <section className="console-panel">
      <div className="panel-heading">
        <div>
          <h2>Run output</h2>
          <p>{job.commandLine}</p>
        </div>
        <span className={`status-badge ${job.status}`}>
          <Icon size={17} />
          {job.status}
        </span>
      </div>
      {job.error ? <p className="inline-error">{job.error}</p> : null}
      <pre className="console-output">{job.output.length ? job.output.join('\n') : 'Waiting for output...'}</pre>
    </section>
  );
}
