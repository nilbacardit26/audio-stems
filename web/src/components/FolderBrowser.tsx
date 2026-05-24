import { ChevronLeft, Folder, HardDrive, LoaderCircle, Music, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { browseFolder } from '../api';
import type { BrowseResponse } from '../types';

type Props = {
  open: boolean;
  onClose: () => void;
  onSelect: (path: string) => void;
};

export function FolderBrowser({ open, onClose, onSelect }: Props) {
  const [path, setPath] = useState<string | undefined>();
  const [data, setData] = useState<BrowseResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      return;
    }

    setLoading(true);
    browseFolder(path)
      .then((next) => {
        setData(next);
        setError(null);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setLoading(false));
  }, [open, path]);

  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="folder-modal" role="dialog" aria-modal="true" aria-label="Choose audio file">
        <div className="panel-heading">
          <div>
            <h2>Choose audio file</h2>
            <p>{data?.path || 'Loading home folder'}</p>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="Close browser">
            <X size={18} />
          </button>
        </div>

        {data?.roots.length ? (
          <div className="root-row" aria-label="Quick folders">
            {data.roots.map((root) => (
              <button key={root.path} type="button" onClick={() => setPath(root.path)}>
                <HardDrive size={16} />
                {root.label}
              </button>
            ))}
          </div>
        ) : null}

        <div className="browser-toolbar">
          <button type="button" disabled={!data?.parent || loading} onClick={() => setPath(data?.parent || undefined)}>
            <ChevronLeft size={18} />
            Up
          </button>
          {loading ? (
            <span className="loading-label">
              <LoaderCircle size={16} />
              Loading
            </span>
          ) : null}
        </div>

        {error ? <p className="inline-error">{error}</p> : null}

        <div className="browser-list">
          {data?.entries.map((entry) => (
            <button
              key={entry.path}
              type="button"
              className={entry.kind === 'directory' ? 'browser-entry directory' : 'browser-entry file'}
              onClick={() => {
                if (entry.kind === 'directory') {
                  setPath(entry.path);
                  return;
                }
                onSelect(entry.path);
              }}
            >
              {entry.kind === 'directory' ? <Folder size={18} /> : <Music size={18} />}
              <span>{entry.name}</span>
            </button>
          ))}
          {!loading && data?.entries.length === 0 ? <p className="empty-browser">No audio files or folders here.</p> : null}
        </div>
      </section>
    </div>
  );
}
