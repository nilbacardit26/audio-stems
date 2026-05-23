from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from prompt_toolkit import prompt
from prompt_toolkit.completion import (
    Completer,
    Completion,
    FuzzyCompleter,
    PathCompleter,
    ThreadedCompleter,
    WordCompleter,
)
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.validation import ValidationError, Validator


@dataclass(frozen=True)
class Preset:
    engine: str
    model: str | None
    description: str
    two_stems: str | None = None


@dataclass(frozen=True)
class RuntimeStatus:
    ffmpeg: str | None
    nvidia_smi: str | None
    demucs: str | None
    audio_separator: str | None
    uv: str | None
    setup_script: Path | None
    gpu_summary: str | None


PRESETS: dict[str, Preset] = {
    "demucs": Preset(
        engine="demucs",
        model="htdemucs_ft",
        description="Recommended quality Demucs 4-stem model.",
    ),
    "fast": Preset(
        engine="demucs",
        model="htdemucs",
        description="Faster Demucs 4-stem model.",
    ),
    "vocals": Preset(
        engine="demucs",
        model="htdemucs_ft",
        description="Demucs vocals/no_vocals split.",
        two_stems="vocals",
    ),
    "six": Preset(
        engine="demucs",
        model="htdemucs_6s",
        description="Experimental Demucs 6-stem model: vocals, drums, bass, other, guitar, piano.",
    ),
    "separator": Preset(
        engine="separator",
        model=None,
        description="audio-separator/UVR model selected with --separator-model.",
    ),
}

AUDIO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".avi",
    ".flac",
    ".m4v",
    ".m4a",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ogg",
    ".opus",
    ".webm",
    ".wav",
    ".wma",
}

COMMANDS = {"separate", "interactive", "i", "doctor", "models", "presets"}
SEARCH_INDEX_TIMEOUT_SECONDS = 8
SEARCH_INDEX_LIMIT = 50000
SEARCH_LIMIT = 80
SEARCH_EXCLUDE_DIRS = {
    ".cache",
    ".git",
    ".local/share/Trash",
    ".npm",
    ".pyenv",
    ".venv",
    "__pycache__",
    "dev",
    "proc",
    "run",
    "snap",
    "sys",
    "var/cache",
    "var/lib/docker",
    "var/lib/flatpak",
    "var/log",
}
CODEX_STYLE = Style.from_dict(
    {
        "prompt-mark": "#22d3ee bold",
        "prompt": "#f9fafb",
        "placeholder": "#6b7280 italic",
        "hint": "#6b7280",
        "completion-menu.completion": "bg:#1f2335 #c0caf5",
        "completion-menu.completion.current": "bg:#7aa2f7 #111827 bold",
        "completion-menu.meta.completion": "bg:#1f2335 #9aa5ce",
        "completion-menu.meta.completion.current": "bg:#7aa2f7 #111827",
        "scrollbar.background": "bg:#1f2335",
        "scrollbar.button": "bg:#7aa2f7",
    }
)
PATH_KEY_BINDINGS = KeyBindings()


@PATH_KEY_BINDINGS.add("c-left", eager=True)
def _(event: object) -> None:
    jump_to_previous_path_segment(event.current_buffer)


@PATH_KEY_BINDINGS.add("c-right", eager=True)
def _(event: object) -> None:
    jump_to_next_path_segment(event.current_buffer)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        args = ["interactive"]
    if args and args[0] not in COMMANDS and args[0] not in {"-h", "--help"}:
        args.insert(0, "separate")

    parser = build_parser()
    ns = parser.parse_args(args)
    return ns.func(ns)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stems",
        description="Local wrapper for Demucs and audio-separator stem separation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    separate = subparsers.add_parser("separate", help="Separate one or more audio files")
    separate.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="Audio/video files readable by ffmpeg",
    )
    separate.add_argument(
        "-p",
        "--preset",
        choices=sorted(PRESETS),
        default="demucs",
        help="Separation preset.",
    )
    separate.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("separated"),
        help="Output directory. Default: separated",
    )
    separate.add_argument(
        "-d",
        "--device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
        help="Device for Demucs. Default: auto",
    )
    separate.add_argument(
        "--separator-model",
        help="audio-separator model filename, for example UVR-MDX-NET-Inst_HQ_3.onnx.",
    )
    separate.add_argument(
        "--model-dir",
        type=Path,
        default=Path("models/audio-separator"),
        help="audio-separator model cache directory.",
    )
    separate.add_argument(
        "--format",
        default="WAV",
        help="audio-separator output format. Default: WAV",
    )
    separate.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the underlying command without executing it.",
    )
    separate.set_defaults(func=cmd_separate)

    interactive = subparsers.add_parser(
        "interactive",
        aliases=["i"],
        help="Choose a song, preset, and output folder interactively",
    )
    interactive.set_defaults(func=cmd_interactive)

    doctor = subparsers.add_parser("doctor", help="Check local runtime dependencies")
    doctor.set_defaults(func=cmd_doctor)

    models = subparsers.add_parser("models", help="List audio-separator models")
    models.add_argument("--filter", help="Filter model list, for example vocals, drums, guitar.")
    models.add_argument("--limit", type=int, default=50, help="Limit listed models. Default: 50")
    models.set_defaults(func=cmd_models)

    presets = subparsers.add_parser("presets", help="Show available presets")
    presets.set_defaults(func=cmd_presets)

    return parser


def cmd_separate(ns: argparse.Namespace) -> int:
    missing = [str(path) for path in ns.inputs if not path.exists()]
    if missing:
        print("Input file(s) not found:", file=sys.stderr)
        for path in missing:
            print(f"  {path}", file=sys.stderr)
        return 2

    ns.out.mkdir(parents=True, exist_ok=True)

    try:
        command = build_command(ns)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print_command(command)
    if ns.dry_run:
        return 0

    try:
        completed = subprocess.run(command, check=False)
    except FileNotFoundError as exc:
        print(f"Missing executable: {exc.filename}", file=sys.stderr)
        print("Run ./scripts/setup.sh first, then activate .venv.", file=sys.stderr)
        return 127

    return completed.returncode


def cmd_interactive(_: argparse.Namespace) -> int:
    print("stems")
    print("Type a path, / for local media search, or @ for global media search.")
    print("Examples: /demo, /Videos, @Videos, @beatles.*flac")
    print("Press Ctrl-C to cancel.")

    try:
        if not ensure_interactive_runtime():
            return 1
        inputs = ask_input_files()
        preset_name = ask_preset()
        preset = PRESETS[preset_name]
        separator_model = ask_separator_model() if preset.engine == "separator" else None
        out = ask_output_dir()
        device = ask_device() if preset.engine == "demucs" else "auto"
        output_format = ask_output_format() if preset.engine == "separator" else "WAV"
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return 130

    ns = build_separate_namespace(
        inputs=inputs,
        preset=preset_name,
        out=out,
        device=device,
        separator_model=separator_model,
        output_format=output_format,
        dry_run=True,
    )
    command = build_command(ns)

    print("\nReady to run:")
    print_command(command)
    if not ask_confirm("Start separation?", default=True):
        print("Cancelled.")
        return 0

    ns.dry_run = False
    return cmd_separate(ns)


def build_separate_namespace(
    *,
    inputs: Sequence[Path],
    preset: str,
    out: Path,
    device: str,
    separator_model: str | None,
    output_format: str,
    dry_run: bool,
) -> argparse.Namespace:
    return argparse.Namespace(
        inputs=list(inputs),
        preset=preset,
        out=out,
        device=device,
        separator_model=separator_model,
        model_dir=Path("models/audio-separator"),
        format=output_format,
        dry_run=dry_run,
    )


def build_command(ns: argparse.Namespace) -> list[str]:
    preset = PRESETS[ns.preset]
    if preset.engine == "demucs":
        return build_demucs_command(preset, ns)
    if preset.engine == "separator":
        return build_separator_command(ns)
    raise ValueError(f"Unsupported engine: {preset.engine}")


def build_demucs_command(preset: Preset, ns: argparse.Namespace) -> list[str]:
    if preset.model is None:
        raise ValueError("Demucs preset requires a model")

    device = resolve_device(ns.device)
    command = [
        "demucs",
        "-d",
        device,
        "-n",
        preset.model,
        "-o",
        str(ns.out),
    ]
    if preset.two_stems:
        command.extend(["--two-stems", preset.two_stems])
    command.extend(str(path) for path in ns.inputs)
    return command


def build_separator_command(ns: argparse.Namespace) -> list[str]:
    if not ns.separator_model:
        raise SystemExit(
            "The separator preset requires --separator-model. "
            "Run `stems models --filter vocals` to inspect choices."
        )

    command = [
        "audio-separator",
        "--model_filename",
        ns.separator_model,
        "--output_dir",
        str(ns.out),
        "--model_file_dir",
        str(ns.model_dir),
        "--output_format",
        ns.format,
    ]
    command.extend(str(path) for path in ns.inputs)
    return command


def ensure_interactive_runtime() -> bool:
    status = collect_runtime_status()
    print_runtime_summary(status)

    if not status.ffmpeg:
        print("\nffmpeg is required and is not installed.")
        print("Install it with your system package manager, for example:")
        print("  sudo apt install ffmpeg")
        return False

    if status.demucs:
        print()
        return True

    print("\nDemucs is required for the default local separation presets.")
    if not status.setup_script:
        print("I could not find scripts/setup.sh, so automatic setup is not available here.")
        print("From the repo, run: ./scripts/setup.sh")
        return False

    if not status.uv:
        print("uv is required for automatic setup and was not found in PATH.")
        print("Install uv first, then run: ./scripts/setup.sh")
        return False

    if not ask_confirm("Run local setup now?", default=True):
        print("Setup skipped.")
        return False

    setup_command = [str(status.setup_script)]
    if not status.nvidia_smi:
        setup_command.append("--cpu")

    print("\nRunning setup:")
    print_command(setup_command)
    completed = subprocess.run(setup_command, check=False, cwd=status.setup_script.parent.parent)
    if completed.returncode != 0:
        print("Setup failed. Fix the error above and run `stems` again.", file=sys.stderr)
        return False

    venv_bin = status.setup_script.parent.parent / ".venv" / "bin"
    if venv_bin.exists():
        os.environ["PATH"] = f"{venv_bin}{os.pathsep}{os.environ.get('PATH', '')}"

    status = collect_runtime_status()
    print("\nPost-setup status:")
    print_runtime_summary(status)
    if not status.demucs:
        print("\nSetup completed, but Demucs is still not visible in PATH.", file=sys.stderr)
        print("Try: source .venv/bin/activate", file=sys.stderr)
        return False

    print()
    return True


def collect_runtime_status() -> RuntimeStatus:
    nvidia_smi = shutil.which("nvidia-smi")
    return RuntimeStatus(
        ffmpeg=shutil.which("ffmpeg"),
        nvidia_smi=nvidia_smi,
        demucs=shutil.which("demucs"),
        audio_separator=shutil.which("audio-separator"),
        uv=shutil.which("uv"),
        setup_script=find_setup_script(),
        gpu_summary=read_gpu_summary(nvidia_smi),
    )


def print_runtime_summary(status: RuntimeStatus) -> None:
    print("\nLocal runtime")
    print(f"  ffmpeg:          {status.ffmpeg or 'missing'}")
    print(f"  GPU:             {status.gpu_summary or 'not detected'}")
    print(f"  Demucs:          {status.demucs or 'missing'}")
    print(f"  audio-separator: {status.audio_separator or 'optional, not installed'}")
    print(f"  setup script:    {status.setup_script or 'not found'}")


def find_setup_script() -> Path | None:
    candidates: list[Path] = []
    for start in (Path.cwd(), Path(__file__).resolve()):
        candidates.extend(start.parents if start.is_file() else [start, *start.parents])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        setup_script = candidate / "scripts" / "setup.sh"
        pyproject = candidate / "pyproject.toml"
        if setup_script.exists() and pyproject.exists():
            return setup_script
    return None


def read_gpu_summary(nvidia_smi: str | None) -> str | None:
    if not nvidia_smi:
        return None
    result = subprocess.run(
        [
            nvidia_smi,
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    return output.splitlines()[0] if output else None


def ask_input_files() -> list[Path]:
    files: list[Path] = []
    completer = ThreadedCompleter(MediaPathCompleter(only_directories=False))

    while True:
        label = "Audio file path/search"
        validator: Validator = ExistingAudioPathValidator()
        if files:
            label = "Add another audio file, or leave empty"
            validator = OptionalExistingAudioPathValidator()

        value = prompt(
            prompt_label(""),
            default="",
            placeholder=prompt_placeholder(label),
            completer=completer,
            complete_while_typing=True,
            key_bindings=PATH_KEY_BINDINGS,
            validator=validator,
            validate_while_typing=False,
            style=CODEX_STYLE,
        ).strip()

        if not value and files:
            return files

        path = parse_at_path(value)
        files.append(path)
        print(f"Added: {path}")


def ask_preset() -> str:
    print("\nPresets")
    for name, preset in sorted(PRESETS.items()):
        print(f"  {name:<9} {preset.description}")

    value = prompt(
        prompt_label("Preset [demucs]"),
        completer=WordCompleter(sorted(PRESETS), ignore_case=True),
        validator=OptionalChoiceValidator(PRESETS),
        complete_while_typing=True,
        style=CODEX_STYLE,
    ).strip().lower()
    return value or "demucs"


def ask_output_dir() -> Path:
    value = prompt(
        prompt_label("Output directory [@separated]"),
        completer=ThreadedCompleter(MediaPathCompleter(only_directories=True)),
        complete_while_typing=True,
        key_bindings=PATH_KEY_BINDINGS,
        style=CODEX_STYLE,
    ).strip()
    return parse_at_path(value or "@separated")


def ask_device() -> str:
    choices = ("auto", "cuda", "cpu")
    value = prompt(
        prompt_label("Device [auto]"),
        completer=WordCompleter(choices, ignore_case=True),
        validator=OptionalChoiceValidator(choices),
        complete_while_typing=True,
        style=CODEX_STYLE,
    ).strip().lower()
    return value or "auto"


def ask_output_format() -> str:
    choices = ("WAV", "FLAC", "MP3")
    value = prompt(
        prompt_label("Output format [WAV]"),
        completer=WordCompleter(choices, ignore_case=True),
        validator=OptionalChoiceValidator(choices),
        complete_while_typing=True,
        style=CODEX_STYLE,
    )
    return value.strip().upper() or "WAV"


def ask_separator_model() -> str:
    print("\naudio-separator models are selected by filename.")
    print("Run `stems models --filter vocals` in another terminal if you want the full list.")
    suggestions = (
        "UVR-MDX-NET-Inst_HQ_3.onnx",
        "UVR-MDX-NET-Voc_FT.onnx",
        "model_bs_roformer_ep_317_sdr_12.9755.ckpt",
    )
    return prompt(
        prompt_label("Separator model"),
        default="",
        completer=FuzzyCompleter(WordCompleter(suggestions, ignore_case=True)),
        validator=NonEmptyValidator("Model filename is required."),
        complete_while_typing=True,
        style=CODEX_STYLE,
    ).strip()


def ask_confirm(message: str, default: bool) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    value = prompt(
        prompt_label(f"{message} {suffix}"),
        validator=OptionalChoiceValidator(("y", "yes", "n", "no")),
        complete_while_typing=True,
        style=CODEX_STYLE,
    ).strip().lower()
    if not value:
        return default
    return value in {"y", "yes"}


def prompt_label(text: str) -> FormattedText:
    fragments = [("class:prompt-mark", "›"), ("", " ")]
    if text:
        fragments.extend([("class:prompt", text), ("", " ")])
    return FormattedText(fragments)


def prompt_placeholder(text: str) -> FormattedText:
    return FormattedText([("class:placeholder", text)])


def jump_to_previous_path_segment(buffer: object) -> None:
    text = buffer.text
    cursor = buffer.cursor_position
    if cursor <= 0:
        return

    prefix_offset = path_prefix_offset(text)
    if cursor <= prefix_offset:
        buffer.cursor_position = 0
        return

    search_end = max(prefix_offset, cursor - 1)
    slash = text.rfind("/", prefix_offset, search_end)
    buffer.cursor_position = slash + 1 if slash >= 0 else prefix_offset


def jump_to_next_path_segment(buffer: object) -> None:
    text = buffer.text
    cursor = buffer.cursor_position
    if cursor >= len(text):
        return

    prefix_offset = path_prefix_offset(text)
    search_start = max(cursor, prefix_offset)
    slash = text.find("/", search_start)
    buffer.cursor_position = slash + 1 if slash >= 0 else len(text)


def path_prefix_offset(text: str) -> int:
    return 1 if text.startswith("@") else 0


def parse_at_path(value: str) -> Path:
    text = value.strip()
    if text.startswith("@"):
        text = text[1:]
    return Path(os.path.expandvars(os.path.expanduser(text))).resolve()


MEDIA_INDEX: MediaFileIndex | None = None
LOCAL_MEDIA_INDEXES: dict[Path, MediaFileIndex] = {}


class MediaPathCompleter(Completer):
    def __init__(self, only_directories: bool) -> None:
        self.only_directories = only_directories
        self.path_completer = PathCompleter(
            only_directories=only_directories,
            expanduser=True,
            file_filter=file_filter if not only_directories else None,
        )

    def get_completions(self, document: Document, complete_event: object) -> Iterable[Completion]:
        text = document.text_before_cursor
        marker = text.rfind("@")
        if marker == -1:
            if not self.only_directories and should_use_local_search(text):
                yield from local_media_completions(text[1:], start_position=-len(text))
                return
            if should_use_plain_path_completion(text):
                yield from self.path_completions(text, complete_event)
            return

        path_fragment = text[marker + 1 :]
        if not self.only_directories and should_use_system_search(path_fragment):
            yield from indexed_media_completions(path_fragment)
            return

        yield from self.path_completions(path_fragment, complete_event)

    def path_completions(self, fragment: str, complete_event: object) -> Iterable[Completion]:
        nested = Document(fragment, cursor_position=len(fragment))

        for completion in self.path_completer.get_completions(nested, complete_event):
            yield Completion(
                completion.text,
                start_position=completion.start_position,
                display=completion.display,
                display_meta=completion.display_meta,
                style=completion.style,
                selected_style=completion.selected_style,
            )


def should_use_plain_path_completion(fragment: str) -> bool:
    if not fragment:
        return False
    return fragment.startswith(("/", "~", ".", "$")) or "/" in fragment


def should_use_local_search(fragment: str) -> bool:
    return fragment.startswith("/") and not fragment.startswith("//") and "/" not in fragment[1:]


def should_use_system_search(fragment: str) -> bool:
    if not fragment:
        return False
    if fragment.startswith(("/", "~", ".", "$")):
        return False
    if "/" in fragment:
        return False
    return len(fragment) >= 2


def indexed_media_completions(pattern: str) -> Iterable[Completion]:
    for path in media_index().search(pattern):
        yield Completion(
            str(path),
            start_position=-len(pattern),
            display=path.name,
            display_meta=str(path.parent),
        )


def local_media_completions(pattern: str, start_position: int) -> Iterable[Completion]:
    for path in local_media_index(Path.cwd()).search(pattern):
        yield Completion(
            str(path),
            start_position=start_position,
            display=path.name,
            display_meta=str(path.parent),
        )


def media_index() -> MediaFileIndex:
    global MEDIA_INDEX
    if MEDIA_INDEX is None:
        MEDIA_INDEX = MediaFileIndex()
    return MEDIA_INDEX


def local_media_index(root: Path) -> MediaFileIndex:
    resolved = root.resolve()
    if resolved not in LOCAL_MEDIA_INDEXES:
        LOCAL_MEDIA_INDEXES[resolved] = MediaFileIndex([resolved])
    return LOCAL_MEDIA_INDEXES[resolved]


class MediaFileIndex:
    def __init__(self, roots: Sequence[Path] | None = None) -> None:
        self.roots = roots
        self.paths: list[Path] | None = None

    def search(self, pattern: str) -> list[Path]:
        paths = self.load()
        if not pattern.strip():
            return sorted(paths, key=lambda path: str(path).lower())[:SEARCH_LIMIT]

        regex = compile_search_regex(pattern)
        scored: list[tuple[int, str, Path]] = []
        for path in paths:
            score = score_media_path(path, pattern, regex)
            if score <= 0:
                continue
            scored.append((score, str(path).lower(), path))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [path for _, _, path in scored[:SEARCH_LIMIT]]

    def load(self) -> list[Path]:
        if self.paths is not None:
            return self.paths

        roots = dedupe_existing_roots(self.roots) if self.roots else search_roots()
        rg = shutil.which("rg")
        if rg:
            paths = index_media_files_with_rg(rg, roots)
        else:
            paths = index_media_files_with_python(roots)

        self.paths = paths
        return paths


def compile_search_regex(pattern: str) -> re.Pattern[str] | None:
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error:
        return None


def score_media_path(path: Path, pattern: str, regex: re.Pattern[str] | None) -> int:
    query = pattern.strip().lower()
    if not query:
        return 0

    path_text = str(path)
    lower_path = path_text.lower()
    lower_name = path.name.lower()
    lower_parent = str(path.parent).lower()

    score = 0
    if any(part.lower() == query for part in path.parts):
        score = max(score, 110)
    if regex and regex.search(path_text):
        score = max(score, 50)
    if query in lower_name:
        score = max(score, 90)
    if lower_name.startswith(query):
        score = max(score, 100)
    if query in lower_parent:
        score = max(score, 80)
    if query in lower_path:
        score = max(score, 70)

    tokens = [token for token in re.split(r"\s+", query) if token]
    if tokens and all(token in lower_path for token in tokens):
        score = max(score, 60)

    if not has_regex_syntax(query):
        compact_query = compact_for_fuzzy(query)
        compact_path = compact_for_fuzzy(lower_path)
        if compact_query and is_subsequence(compact_query, compact_path):
            score = max(score, 30)

    if score and has_hidden_component(path):
        score = max(1, score - 25)

    return score


def has_hidden_component(path: Path) -> bool:
    return any(part.startswith(".") and part not in {".", ".."} for part in path.parts)


def has_regex_syntax(value: str) -> bool:
    return any(char in value for char in ".^$*+?{}[]\\|()")


def compact_for_fuzzy(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def is_subsequence(needle: str, haystack: str) -> bool:
    if not needle:
        return False
    position = 0
    for char in haystack:
        if char == needle[position]:
            position += 1
            if position == len(needle):
                return True
    return False


def search_roots() -> list[Path]:
    configured = os.environ.get("STEMS_SEARCH_ROOTS")
    if configured:
        roots = [Path(os.path.expanduser(part)) for part in configured.split(os.pathsep) if part]
    else:
        roots = [Path("/")]
    return dedupe_existing_roots(roots)


def dedupe_existing_roots(roots: Sequence[Path]) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        resolved = root.resolve()
        if resolved in seen or not resolved.exists():
            continue
        seen.add(resolved)
        selected.append(resolved)
    return selected


def index_media_files_with_rg(rg: str, roots: Sequence[Path]) -> list[Path]:
    command = [rg, "--files", "--hidden", "--no-messages"]
    for directory in sorted(SEARCH_EXCLUDE_DIRS):
        command.extend(["--glob", f"!{directory}/**"])
    for extension in sorted(AUDIO_EXTENSIONS):
        command.extend(["--glob", f"*{extension}", "--glob", f"*{extension.upper()}"])
    command.extend(str(root) for root in roots)

    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=SEARCH_INDEX_TIMEOUT_SECONDS,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    paths: list[Path] = []
    seen: set[Path] = set()
    for line in result.stdout.splitlines():
        path = Path(line).resolve()
        if path in seen:
            continue
        seen.add(path)
        paths.append(path)
        if len(paths) >= SEARCH_INDEX_LIMIT:
            break
    return paths


def index_media_files_with_python(roots: Sequence[Path]) -> list[Path]:
    deadline = time.monotonic() + SEARCH_INDEX_TIMEOUT_SECONDS
    paths: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        for current_root, directories, files in os.walk(root):
            if time.monotonic() > deadline:
                return paths
            directories[:] = [
                directory
                for directory in directories
                if not should_skip_search_dir(Path(current_root) / directory)
            ]
            for filename in files:
                path = Path(current_root) / filename
                if path in seen:
                    continue
                if path.suffix.lower() in AUDIO_EXTENSIONS:
                    seen.add(path)
                    paths.append(path)
                    if len(paths) >= SEARCH_INDEX_LIMIT:
                        return paths
    return paths


def should_skip_search_dir(path: Path) -> bool:
    text = str(path)
    return any(text == f"/{name}" or text.endswith(f"/{name}") for name in SEARCH_EXCLUDE_DIRS)


def file_filter(path: str) -> bool:
    candidate = Path(os.path.expanduser(path))
    return candidate.is_dir() or candidate.suffix.lower() in AUDIO_EXTENSIONS


class ExistingAudioPathValidator(Validator):
    def validate(self, document: Document) -> None:
        path = parse_at_path(document.text)
        validate_existing_audio_path(path, document)


class OptionalExistingAudioPathValidator(Validator):
    def validate(self, document: Document) -> None:
        if not document.text.strip():
            return
        path = parse_at_path(document.text)
        validate_existing_audio_path(path, document)


def validate_existing_audio_path(path: Path, document: Document) -> None:
    if not path.exists():
        raise ValidationError(
            message="File does not exist.",
            cursor_position=document.cursor_position,
        )
    if not path.is_file():
        raise ValidationError(
            message="Path must be a file.",
            cursor_position=document.cursor_position,
        )
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        raise ValidationError(
            message="Expected an audio/video file extension.",
            cursor_position=document.cursor_position,
        )


class ChoiceValidator(Validator):
    def __init__(self, choices: Iterable[str]) -> None:
        self.choices = {choice.lower(): choice for choice in choices}

    def validate(self, document: Document) -> None:
        if document.text.strip().lower() not in self.choices:
            raise ValidationError(
                message=f"Choose one of: {', '.join(self.choices.values())}",
                cursor_position=document.cursor_position,
            )


class OptionalChoiceValidator(ChoiceValidator):
    def validate(self, document: Document) -> None:
        if not document.text.strip():
            return
        super().validate(document)


class NonEmptyValidator(Validator):
    def __init__(self, message: str) -> None:
        self.message = message

    def validate(self, document: Document) -> None:
        if not document.text.strip():
            raise ValidationError(message=self.message, cursor_position=document.cursor_position)


def cmd_doctor(_: argparse.Namespace) -> int:
    print("Runtime check")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Working directory: {Path.cwd()}")

    ffmpeg = shutil.which("ffmpeg")
    print(f"ffmpeg: {ffmpeg or 'missing'}")

    nvidia_smi = shutil.which("nvidia-smi")
    print(f"nvidia-smi: {nvidia_smi or 'missing'}")
    if nvidia_smi:
        run_probe(
            [
                nvidia_smi,
                "--query-gpu=name,memory.total,driver_version",
                "--format=csv,noheader",
            ]
        )

    demucs = shutil.which("demucs")
    print(f"demucs: {demucs or 'missing'}")

    separator = shutil.which("audio-separator")
    print(f"audio-separator: {separator or 'missing'}")

    if demucs:
        run_probe(["demucs", "--help"], first_line_only=True)

    return 0 if ffmpeg and demucs else 1


def cmd_models(ns: argparse.Namespace) -> int:
    command = ["audio-separator", "--list_models", "--list_limit", str(ns.limit)]
    if ns.filter:
        command.extend(["--list_filter", ns.filter])

    print_command(command)
    try:
        return subprocess.run(command, check=False).returncode
    except FileNotFoundError:
        print("audio-separator is not installed. Run ./scripts/setup.sh --full.", file=sys.stderr)
        return 127


def cmd_presets(_: argparse.Namespace) -> int:
    width = max(len(name) for name in PRESETS)
    for name, preset in sorted(PRESETS.items()):
        print(f"{name:<{width}}  {preset.description}")
    return 0


def resolve_device(device: str) -> str:
    if device != "auto":
        return device
    return "cuda" if shutil.which("nvidia-smi") else "cpu"


def print_command(command: Sequence[str]) -> None:
    print("+ " + " ".join(shell_quote(part) for part in command))


def shell_quote(value: object) -> str:
    text = os.fspath(value)
    if not text:
        return "''"
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_./:=+-")
    if all(char in safe_chars for char in text):
        return text
    return "'" + text.replace("'", "'\"'\"'") + "'"


def run_probe(command: Sequence[str], first_line_only: bool = False) -> None:
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return

    output = (result.stdout or result.stderr).strip()
    if not output:
        return
    if first_line_only:
        output = output.splitlines()[0]
    for line in output.splitlines():
        print(f"  {line}")
