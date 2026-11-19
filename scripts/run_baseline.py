"""Launch the pinned AutoSaddler V2 reference configurations."""

from argparse import ArgumentParser
from functools import partial
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIGS = {
    "smoke": "local_template.yaml",
    "gaia2-smoke": "meta_are_smoke.yaml",
    "gaia2-full": "meta_are_full.yaml",
}


def git(directory, *arguments):
    return subprocess.check_output(["git", "-C", str(directory), *arguments], text=True).strip()


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=CONFIGS)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-id")
    mode.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        parser.error("run from Linux or WSL2 because upstream AutoSaddler uses POSIX file locking")
    if args.run_id is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.run_id):
        parser.error("--run-id must start with a letter or number and use letters, numbers, dots, underscores or hyphens")
    if args.prepare_only and args.profile == "smoke":
        parser.error("the credential-free smoke profile has no benchmark downloads")

    config_path = ROOT / "configs" / "v2" / CONFIGS[args.profile]
    config_bytes = config_path.read_bytes()
    config = yaml.safe_load(config_bytes)
    settings = config["scenario"]["settings"]
    provider = config["provider"]
    optimizer = provider["settings"]
    working_dir = ROOT
    if not args.prepare_only:
        source_commit = git(ROOT, "rev-parse", "HEAD")
        if git(ROOT, "status", "--porcelain"):
            parser.error("commit source and configuration changes before starting a recorded run")

    if args.profile != "smoke":
        from autosaddler.v2.plugins.meta_are.provisioning import (
            ProvisioningRequest,
            provision_demo_filesystem,
            run_meta_are_filesystem_probe,
        )
        from autosaddler.v2.plugins.meta_are.scenario_provisioning import (
            ScenarioProvisioningRequest,
            provision_gaia2_scenarios,
        )

        if not args.prepare_only:
            required = ["OPENAI_API_KEY"]
            if provider["type"] == "claude":
                required.append("ANTHROPIC_API_KEY")
            missing = [key for key in required if not os.environ.get(key)]
            if missing:
                parser.error("missing provider credentials: " + ", ".join(missing))

        os.environ["UV_PYTHON"] = "3.12"
        source_repo = (config_path.parent / settings["source_repo"]).resolve()
        revision = settings["base_revision"]
        if not source_repo.exists():
            subprocess.run(
                ["git", "-c", "core.autocrlf=false", "clone", "--no-checkout",
                 "https://github.com/pshlego/Meta-ARE.git", str(source_repo)],
                check=True,
            )
            git(source_repo, "config", "core.autocrlf", "false")
            git(source_repo, "checkout", "--detach", revision)
        if git(source_repo, "rev-parse", "HEAD") != revision or git(
            source_repo, "status", "--porcelain", "--untracked-files=no"
        ):
            parser.error(f"use a clean Meta-ARE checkout at {revision}: {source_repo}")

        git(source_repo, "ls-files", "--error-unmatch", "hook.json")
        hook = json.loads((source_repo / "hook.json").read_text(encoding="utf-8"))
        if hook["hooks"]["PreToolUse"] != []:
            parser.error("the pinned Meta-ARE baseline must start with an empty PreToolUse list")

        # Use the exact same revisions, manifests and paths as the evaluator.
        scenarios = provision_gaia2_scenarios(ScenarioProvisioningRequest(
            destination_root=(config_path.parent / settings["dataset_root"]).resolve(),
            source_revision=settings["dataset_source_revision"],
            manifests=tuple(
                (config_path.parent / settings[key]).resolve()
                for key in ("train_manifest", "development_manifest")
            ),
        ))
        filesystem = provision_demo_filesystem(
            ProvisioningRequest(
                destination_root=(config_path.parent / settings["demo_filesystem_root"]).resolve().parents[1],
                source_revision=settings["demo_filesystem_source_revision"],
            ),
            probe=partial(run_meta_are_filesystem_probe, source_repo),
        )
        print(f"provisioned {scenarios.file_count} scenarios and {filesystem.file_count} filesystem files", flush=True)
        if args.prepare_only:
            return
        working_dir = ROOT.parent / "working_dir"
        working_dir.mkdir(exist_ok=True)

    run_dir = (config_path.parent / config["storage"]["run_root"]).resolve() / args.run_id
    receipt = {
        "experiment_id": args.run_id,
        "method": "autosaddler-v2-fair",
        "profile": args.profile,
        "source_commit": source_commit,
        "config_sha256": sha256(config_bytes).hexdigest(),
        "harness_base_commit": settings.get("base_revision"),
        "dataset_revision": settings.get("dataset_source_revision"),
        "optimizer_model": optimizer.get("provider", {}).get("wire_model", optimizer.get("model")),
        "task_model": settings.get("model"),
        "judge_model": settings.get("judge_model"),
        "random_seed": config["optimization"]["task_selection"].get("seed", 0),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = run_dir / "experiment.json"
    if receipt_path.exists():
        if json.loads(receipt_path.read_text(encoding="utf-8")) != receipt:
            parser.error(f"this run ID already has different experiment inputs: {receipt_path}")
    else:
        with receipt_path.open("x", encoding="utf-8") as file:
            json.dump(receipt, file, indent=2)
            file.write("\n")
    print(f"experiment={receipt_path}", flush=True)
    subprocess.run(
        [sys.executable, "-m", "autosaddler.v2.cli", "--config", str(config_path), "--run-id", args.run_id],
        cwd=working_dir,
        check=True,
    )


if __name__ == "__main__":
    main()
