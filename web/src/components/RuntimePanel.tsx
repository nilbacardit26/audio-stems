import { RefreshCw, Server, TriangleAlert } from 'lucide-react';
import type { RuntimeStatus } from '../types';

type Props = {
  runtime: RuntimeStatus | null;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
};

export function RuntimePanel({ runtime, loading, error, onRefresh }: Props) {
  const ready = Boolean(runtime?.ready);

  return (
    <section className="runtime-panel" aria-label="Runtime status">
      <div className="panel-heading">
        <div>
          <h2>Runtime</h2>
          <p>{ready ? 'Ready for Demucs separation' : 'Check local dependencies before running'}</p>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} aria-label="Refresh runtime">
          <RefreshCw size={18} />
        </button>
      </div>

      {error ? (
        <div className="notice error">
          <TriangleAlert size={18} />
          <span>{error}</span>
        </div>
      ) : null}

      <div className="runtime-grid" aria-busy={loading}>
        <RuntimeItem label="ffmpeg" value={runtime?.ffmpeg} required />
        <RuntimeItem label="GPU" value={runtime?.gpu} />
        <RuntimeItem label="Demucs" value={runtime?.demucs} required />
        <RuntimeItem label="audio-separator" value={runtime?.audioSeparator} />
      </div>

      {!ready && runtime ? (
        <div className="notice">
          <Server size={18} />
          <span>
            {runtime.setupScript
              ? 'Run ./scripts/setup.sh from this checkout to install the local runtime.'
              : 'Install ffmpeg and Demucs, then refresh the runtime check.'}
          </span>
        </div>
      ) : null}
    </section>
  );
}

function RuntimeItem({ label, value, required = false }: { label: string; value?: string | null; required?: boolean }) {
  return (
    <div className="runtime-item">
      <span>{label}</span>
      <strong className={value ? 'ok' : required ? 'missing' : 'optional'}>
        {value || (required ? 'missing' : 'optional')}
      </strong>
    </div>
  );
}
