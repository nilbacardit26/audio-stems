import { Cpu, Mic2, SlidersHorizontal, Zap } from 'lucide-react';
import type { Preset, SeparatorModel, SeparationForm } from '../types';

type Props = {
  presets: Preset[];
  separatorModels: SeparatorModel[];
  form: SeparationForm;
  onChange: (changes: Partial<SeparationForm>) => void;
};

const presetIcons = {
  demucs: Cpu,
  fast: Zap,
  vocals: Mic2,
  six: SlidersHorizontal,
  separator: SlidersHorizontal,
};

export function PresetSelector({ presets, separatorModels, form, onChange }: Props) {
  const selected = presets.find((preset) => preset.name === form.preset);
  const separatorSelected = selected?.engine === 'separator';

  return (
    <section className="tool-section">
      <div className="section-heading">
        <h2>Preset</h2>
        <p>Choose the same preset set exposed by the CLI.</p>
      </div>

      <div className="preset-grid">
        {presets.map((preset) => {
          const Icon = presetIcons[preset.name as keyof typeof presetIcons] ?? Cpu;
          return (
            <button
              className={preset.name === form.preset ? 'preset-card selected' : 'preset-card'}
              key={preset.name}
              type="button"
              onClick={() => onChange({ preset: preset.name })}
            >
              <Icon size={19} />
              <span>{preset.name}</span>
              <small>{preset.description}</small>
            </button>
          );
        })}
      </div>

      <div className="field-grid">
        <label>
          <span>Output directory</span>
          <input value={form.out} onChange={(event) => onChange({ out: event.target.value })} />
        </label>

        {separatorSelected ? (
          <>
            <label>
              <span>Model</span>
              <select
                value={form.separatorModel}
                onChange={(event) => onChange({ separatorModel: event.target.value })}
              >
                {separatorModels.map((model) => (
                  <option key={model.alias} value={model.alias}>
                    {model.alias} - {model.description}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Format</span>
              <select value={form.format} onChange={(event) => onChange({ format: event.target.value as SeparationForm['format'] })}>
                <option value="WAV">WAV</option>
                <option value="FLAC">FLAC</option>
                <option value="MP3">MP3</option>
              </select>
            </label>
          </>
        ) : (
          <label>
            <span>Device</span>
            <select value={form.device} onChange={(event) => onChange({ device: event.target.value as SeparationForm['device'] })}>
              <option value="auto">auto</option>
              <option value="cuda">cuda</option>
              <option value="cpu">cpu</option>
            </select>
          </label>
        )}
      </div>
    </section>
  );
}
