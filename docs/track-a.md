# Track A · AutoSaddler V2

[Upstream AutoSaddler](https://github.com/microsoft/AutoSaddler/commit/e841543ce6cf6bdf690e65134b12a829ec9f66d1) is pinned at `e841543ce6cf6bdf690e65134b12a829ec9f66d1`. The `upstream-autosaddler-e841543` tag points to that commit. To fetch upstream changes for comparison, add the upstream remote once in your clone.

```bash
git remote add upstream https://github.com/microsoft/AutoSaddler.git
git fetch upstream
```

| Git ref | Experiment role |
| --- | --- |
| `main` | Public quickstart for the official V2 baseline |
| `baseline/v2-official`, `baseline-official-v1` | Upstream algorithm and experiment launcher |
| `baseline/v2-fair` | Engineering fixes for the main comparison. Freeze `baseline-fair-v1` after GAIA2 acceptance |
| `baseline/v2-strong` | Planned stronger comparison. Freeze `baseline-strong-v1` after acceptance |
| `research/ours` | Planned research method, to branch from the accepted Fair commit |

## Run GAIA2

Use a standalone clone under a writable parent directory. On Windows, use WSL2 and clone
under its Linux home directory. Git, uv, internet access and Python 3.12 are required.
The checked-in `uv.lock` pins AutoSaddler's dependencies. The launcher clones the adapted
Meta-ARE repository at `395d1dd512add1e3aeb5a6a092490768b51e3ce5`, downloads only the profile's
train and development splits, and prepares the approximately 260 MB demo filesystem.

To provision inputs without running any model:

```bash
git switch --detach baseline-official-v1
uv run --locked --python 3.12 --extra meta-are-setup \
  scripts/run_baseline.py gaia2-smoke --prepare-only
```

Copy `.env.example` to `.env` and fill in `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`. The
optional `HF_TOKEN` can also be exported before provisioning. Run the bounded experiment:

```bash
uv run --locked --python 3.12 --extra meta-are-setup --env-file .env \
  scripts/run_baseline.py gaia2-smoke --run-id gaia2-official-smoke-01
```

The smoke profile uses [the upstream config](../configs/v2/meta_are_smoke.yaml). It runs against
six GAIA2 train scenarios and one development scenario, with a budget of two optimization
iterations and 22 rollouts. It uses the configured OpenAI task and judge models and Anthropic
optimizer. For the [upstream full training profile](../configs/v2/meta_are_full.yaml), use
`gaia2-full` and a fresh run ID. It uses seed 42 and an OpenAI-backed optimizer with a much
larger budget. Both profiles may incur provider charges. Held-out evaluation is a separate step.

## Candidate Hooks

`hook.json` is a tracked Meta-ARE file and is included in Git worktrees. The pinned base starts
with an empty `PreToolUse` list. The launcher checks that the file is present and tracked before
provisioning. Git clone and pull require no locally installed Git hooks or Git LFS for this file.

The upstream AutoSaddler V2 runner omits the benchmark's `--hook-config` argument. The Fair branch
passes the evaluated candidate's own `hook.json` to Meta-ARE. Inspect the attempt's `command.json`
for the candidate worktree path and its `stdout.log` or `stderr.log` for hook-loading and matching
messages when a candidate declares a nonempty Hook.

## Reproduce a run

Use a clean checkout of the full source SHA recorded in `experiment.json`. It also records the
raw config SHA-256, the Meta-ARE commit, the GAIA2 dataset revision, the configured model IDs,
and the task-selection seed. AutoSaddler records resolved settings, verified input hashes,
candidate lineage and benchmark invocations alongside the receipt. Use a fresh run ID for
each independent run. To resume, use the same run ID, checkout and configuration.

GAIA2 downloads and runs live in sibling directories `Meta-ARE/`, `meta_are_data/` and
`working_dir/`. The credential-free smoke uses the ignored `outputs/` directory inside the
clone. Publish run receipts or reviewed aggregates as separate artifacts. Keep credentials,
datasets, raw traces and generated candidates in experiment storage.
