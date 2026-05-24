import { Activity, RotateCcw } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { createJob, getJob, getPresets, getRuntime } from './api';
import { FilePicker } from './components/FilePicker';
import { JobConsole } from './components/JobConsole';
import { PresetSelector } from './components/PresetSelector';
import { RuntimePanel } from './components/RuntimePanel';
import { StartPanel } from './components/StartPanel';
import type { PresetsResponse, RuntimeStatus, SeparationForm, SeparationJob } from './types';

const emptyPresets: PresetsResponse = {
  presets: [],
  separatorModels: [],
  devices: ['auto', 'cuda', 'cpu'],
  formats: ['WAV', 'FLAC', 'MP3'],
  audioExtensions: [],
};

const initialForm: SeparationForm = {
  inputs: [],
  preset: 'demucs',
  out: 'separated',
  device: 'auto',
  separatorModel: 'inst-hq',
  format: 'WAV',
};

export function App() {
  const [presets, setPresets] = useState(emptyPresets);
  const [presetsError, setPresetsError] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(true);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [form, setForm] = useState<SeparationForm>(initialForm);
  const [jobLoading, setJobLoading] = useState(false);
  const [job, setJob] = useState<SeparationJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);

  const loadRuntime = useCallback(() => {
    setRuntimeLoading(true);
    getRuntime()
      .then((status) => {
        setRuntime(status);
        setRuntimeError(null);
      })
      .catch((err: unknown) => {
        setRuntimeError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => setRuntimeLoading(false));
  }, []);

  useEffect(() => {
    getPresets()
      .then((data) => {
        setPresets(data);
        setPresetsError(null);
        if (data.separatorModels[0]) {
          setForm((current) => ({ ...current, separatorModel: data.separatorModels[0].alias }));
        }
      })
      .catch((err: unknown) => {
        setPresetsError(err instanceof Error ? err.message : String(err));
      });
    loadRuntime();
  }, [loadRuntime]);

  const selectedPreset = useMemo(
    () => presets.presets.find((preset) => preset.name === form.preset),
    [presets.presets, form.preset],
  );

  const canRun = form.inputs.length > 0;

  function updateForm(changes: Partial<SeparationForm>) {
    setForm((current) => ({ ...current, ...changes }));
    setJobError(null);
  }

  async function startJob() {
    setJobLoading(true);
    try {
      const next = await createJob(form);
      setJob(next);
      setJobError(null);
    } catch (err: unknown) {
      setJobError(err instanceof Error ? err.message : String(err));
    } finally {
      setJobLoading(false);
    }
  }

  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') {
      return;
    }

    const timer = window.setInterval(() => {
      getJob(job.id)
        .then((next) => {
          setJob(next);
          setJobError(null);
        })
        .catch((err: unknown) => {
          setJobError(err instanceof Error ? err.message : String(err));
        });
    }, 1200);

    return () => window.clearInterval(timer);
  }, [job]);

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <span className="eyebrow">
            <Activity size={16} />
            local stem separation
          </span>
          <h1>Audio Stems</h1>
        </div>
        <button type="button" onClick={() => setForm(initialForm)}>
          <RotateCcw size={18} />
          Reset
        </button>
      </header>

      {presetsError ? <p className="inline-error">{presetsError}</p> : null}

      <div className="layout">
        <div className="workspace">
          <RuntimePanel runtime={runtime} loading={runtimeLoading} error={runtimeError} onRefresh={loadRuntime} />
          <FilePicker inputs={form.inputs} onChange={(inputs) => updateForm({ inputs })} />
          <PresetSelector presets={presets.presets} separatorModels={presets.separatorModels} form={form} onChange={updateForm} />
        </div>

        <aside className="sidebar">
          <div className="summary-panel">
            <h2>Interactive flow</h2>
            <ol>
              <li className={form.inputs.length ? 'done' : ''}>Choose input files</li>
              <li className={selectedPreset ? 'done' : ''}>Pick preset and runtime options</li>
              <li className={job ? 'done' : ''}>Run and watch output</li>
            </ol>
          </div>
          <StartPanel
            error={jobError}
            canRun={canRun}
            loading={jobLoading}
            onRun={startJob}
          />
        </aside>
      </div>

      <JobConsole job={job} />
    </main>
  );
}
