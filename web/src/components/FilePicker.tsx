import { FolderOpen, Plus, Search, Trash2 } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { searchMedia } from '../api';
import type { SearchResult } from '../types';
import { FolderBrowser } from './FolderBrowser';

type Props = {
  inputs: string[];
  onChange: (inputs: string[]) => void;
};

export function FilePicker({ inputs, onChange }: Props) {
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [browserOpen, setBrowserOpen] = useState(false);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      setSearchError(null);
      return;
    }

    const timer = window.setTimeout(() => {
      searchMedia(query)
        .then((items) => {
          setResults(items);
          setSearchError(null);
        })
        .catch((err: unknown) => {
          setSearchError(err instanceof Error ? err.message : String(err));
        });
    }, 180);

    return () => window.clearTimeout(timer);
  }, [query]);

  const canAdd = useMemo(() => draft.trim().length > 0 && !inputs.includes(draft.trim()), [draft, inputs]);

  function addInput(path = draft) {
    const next = path.trim();
    if (!next || inputs.includes(next)) {
      return;
    }
    onChange([...inputs, next]);
    setDraft('');
  }

  function removeInput(path: string) {
    onChange(inputs.filter((input) => input !== path));
  }

  return (
    <section className="tool-section">
      <div className="section-heading">
        <h2>Input files</h2>
        <p>Add one or more local audio/video paths, or search the indexed media cache.</p>
      </div>

      <div className="path-row">
        <input
          aria-label="Audio file path"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              addInput();
            }
          }}
          placeholder="/media/music/song.wav"
        />
        <button type="button" onClick={() => addInput()} disabled={!canAdd}>
          <Plus size={18} />
          Add
        </button>
        <button type="button" onClick={() => setBrowserOpen(true)}>
          <FolderOpen size={18} />
          Browse
        </button>
      </div>

      <div className="search-box">
        <Search size={18} />
        <input
          aria-label="Search media"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="@ search, for example vocals or live.*wav"
        />
      </div>

      {searchError ? <p className="inline-error">{searchError}</p> : null}
      {results.length > 0 ? (
        <div className="search-results">
          {results.slice(0, 8).map((result) => (
            <button key={result.path} type="button" onClick={() => addInput(result.path)}>
              <span>{result.name}</span>
              <small>{result.directory}</small>
            </button>
          ))}
        </div>
      ) : null}

      <div className="selected-list" aria-label="Selected input files">
        {inputs.length === 0 ? <p>No files selected.</p> : null}
        {inputs.map((path) => (
          <div className="selected-item" key={path}>
            <span>{path}</span>
            <button className="icon-button" type="button" onClick={() => removeInput(path)} aria-label={`Remove ${path}`}>
              <Trash2 size={16} />
            </button>
          </div>
        ))}
      </div>

      <FolderBrowser
        open={browserOpen}
        onClose={() => setBrowserOpen(false)}
        onSelect={(path) => {
          addInput(path);
          setBrowserOpen(false);
        }}
      />
    </section>
  );
}
