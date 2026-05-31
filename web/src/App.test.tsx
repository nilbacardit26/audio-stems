import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

const presetsPayload = {
  presets: [
    {
      name: 'demucs',
      engine: 'demucs',
      model: 'htdemucs_ft',
      description: 'Recommended quality Demucs 4-stem model.',
      twoStems: null,
    },
    {
      name: 'separator',
      engine: 'separator',
      model: null,
      description: 'audio-separator model.',
      twoStems: null,
    },
  ],
  separatorModels: [{ alias: 'inst-hq', filename: 'UVR-MDX-NET-Inst_HQ_3.onnx', description: 'vocal split' }],
  devices: ['auto', 'cuda', 'cpu'],
  formats: ['WAV', 'FLAC', 'MP3'],
  audioExtensions: ['.wav'],
};

const runtimePayload = {
  pythonReady: true,
  ffmpeg: '/usr/bin/ffmpeg',
  gpu: null,
  nvidiaSmi: null,
  demucs: '/repo/.venv/bin/demucs',
  audioSeparator: null,
  uv: '/usr/bin/uv',
  setupScript: '/repo/scripts/setup.sh',
  ready: true,
};

let jobPollResponses: Array<Partial<ReturnType<typeof jobPayload>>>;
let jobPollCount: number;

describe('App', () => {
  beforeEach(() => {
    jobPollResponses = [jobPayload('completed')];
    jobPollCount = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url === '/api/presets') {
          return jsonResponse(presetsPayload);
        }
        if (url === '/api/runtime') {
          return jsonResponse(runtimePayload);
        }
        if (url.startsWith('/api/search')) {
          return jsonResponse({ results: [{ path: '/music/song.wav', name: 'song.wav', directory: '/music' }] });
        }
        if (url.startsWith('/api/browse')) {
          return jsonResponse({
            path: '/music',
            parent: '/',
            roots: [{ label: '/music', path: '/music' }],
            entries: [{ name: 'song.wav', path: '/music/song.wav', kind: 'file', selectable: true }],
          });
        }
        if (url === '/api/jobs' && init?.method === 'POST') {
          return jsonResponse(jobPayload('queued'));
        }
        if (url === '/api/jobs/job-1') {
          jobPollCount += 1;
          return jsonResponse(jobPollResponses.shift() ?? jobPayload('completed'));
        }
        throw new Error(`Unhandled request: ${url}`);
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('starts separation directly after files are selected', async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Audio Stems' })).toBeInTheDocument();
    expect(await screen.findByText('Ready for Demucs separation')).toBeInTheDocument();

    await user.type(screen.getByLabelText('Audio file path'), '/music/song.wav');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.click(screen.getByRole('button', { name: 'Start separation' }));

    await waitFor(() => expect(screen.getByText('+ demucs /music/song.wav')).toBeInTheDocument());
  });

  it('marks synced jobs complete instead of leaving them active', async () => {
    jobPollResponses = [
      jobPayload('running', { progress: 37, output: ['Downloading source'] }),
      jobPayload('synced', { progress: 100, output: ['Downloaded source', 'Synced to storage'], finishedAt: 2, returncode: 0 }),
    ];
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByLabelText('Audio file path'), '/music/song.wav');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.click(screen.getByRole('button', { name: 'Start separation' }));

    const syncedBadge = await screen.findByText('synced');
    expect(syncedBadge.closest('.status-badge')).toHaveClass('completed');
    expect(screen.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100');
    expect(screen.getByText(/Synced to storage/)).toBeInTheDocument();
    expect(jobPollCount).toBe(2);
  });

  it('updates the progress bar while a job is running', async () => {
    jobPollResponses = [
      jobPayload('running', { progress: 12, output: ['Preparing'] }),
      jobPayload('running', { progress: 64, output: ['Preparing', '64% separated'] }),
      jobPayload('completed', { progress: 100, output: ['Done'], finishedAt: 2, returncode: 0 }),
    ];
    const user = userEvent.setup();
    render(<App />);

    await user.type(await screen.findByLabelText('Audio file path'), '/music/song.wav');
    await user.click(screen.getByRole('button', { name: 'Add' }));
    await user.click(screen.getByRole('button', { name: 'Start separation' }));

    await waitFor(() => {
      expect(screen.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '64');
    });
    await waitFor(
      () => {
        expect(screen.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100');
      },
      { timeout: 1800 },
    );
  });

  it('adds a file from the local folder browser', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(await screen.findByRole('button', { name: 'Browse' }));
    await user.click(await screen.findByRole('button', { name: 'song.wav' }));

    expect(screen.getByText('/music/song.wav')).toBeInTheDocument();
  });
});

function jobPayload(status: string, overrides: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'job-1',
    status,
    progress: 0,
    command: ['demucs', '/music/song.wav'],
    commandLine: '+ demucs /music/song.wav',
    output: [],
    returncode: null,
    startedAt: 1,
    finishedAt: null,
    error: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown) {
  return Promise.resolve(
    new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    }),
  );
}
