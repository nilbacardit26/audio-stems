import { Play } from 'lucide-react';

type Props = {
  error: string | null;
  canRun: boolean;
  loading: boolean;
  onRun: () => void;
};

export function StartPanel({ error, canRun, loading, onRun }: Props) {
  return (
    <section className="command-panel">
      <div className="panel-heading">
        <div>
          <h2>Start</h2>
          <p>Run separation with the selected files and preset.</p>
        </div>
      </div>

      {error ? <p className="inline-error">{error}</p> : null}

      <button className="run-button" type="button" onClick={onRun} disabled={!canRun || loading}>
        <Play size={19} />
        {loading ? 'Starting...' : 'Start separation'}
      </button>
    </section>
  );
}
