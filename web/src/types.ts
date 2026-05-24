export type Preset = {
  name: string;
  engine: 'demucs' | 'separator';
  model: string | null;
  description: string;
  twoStems: string | null;
};

export type SeparatorModel = {
  alias: string;
  filename: string;
  description: string;
};

export type PresetsResponse = {
  presets: Preset[];
  separatorModels: SeparatorModel[];
  devices: Array<'auto' | 'cuda' | 'cpu'>;
  formats: Array<'WAV' | 'FLAC' | 'MP3'>;
  audioExtensions: string[];
};

export type RuntimeStatus = {
  pythonReady: boolean;
  ffmpeg: string | null;
  gpu: string | null;
  nvidiaSmi: string | null;
  demucs: string | null;
  audioSeparator: string | null;
  uv: string | null;
  setupScript: string | null;
  ready: boolean;
};

export type SearchResult = {
  path: string;
  name: string;
  directory: string;
};

export type BrowseEntry = {
  name: string;
  path: string;
  kind: 'directory' | 'file';
  selectable: boolean;
};

export type BrowseRoot = {
  label: string;
  path: string;
};

export type BrowseResponse = {
  path: string;
  parent: string | null;
  entries: BrowseEntry[];
  roots: BrowseRoot[];
};

export type SeparationForm = {
  inputs: string[];
  preset: string;
  out: string;
  device: 'auto' | 'cuda' | 'cpu';
  separatorModel: string;
  format: 'WAV' | 'FLAC' | 'MP3';
};

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export type SeparationJob = {
  id: string;
  status: JobStatus;
  command: string[];
  commandLine: string;
  output: string[];
  returncode: number | null;
  startedAt: number;
  finishedAt: number | null;
  error: string | null;
};
