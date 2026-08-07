import csv
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.analyze_pancake_debug import aggregate_runs
from analysis.list_pancake_instances import (
    CSV_FIELDS,
    build_instance_table,
    write_csv,
    write_json,
)
from envs.pancake_env import PancakeSortingEnv
from runners import pancake_debug_sweep
from runners.pancake_debug_sweep import (
    SweepRun,
    build_seed_runs,
    load_instance_runs,
    output_dir_for_run,
    run_one,
)
from runners.pancake_hidden_sweep import (
    build_hidden_runs,
    event_dir_for_run,
    output_dir_for_run as hidden_output_dir_for_run,
    select_initial_state_by_min_moves,
)


CONFIG_PATH = (
    REPO_ROOT
    / "configs"
    / "pancake_instances"
    / "N3-5_T0_6_minmoves_stratified_v1.json"
)
SCRIPT_PATH = (
    REPO_ROOT / "runners" / "scripts" / "run_pancake_debug_stratified_sweep.sh"
)


def write_instances_file(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "instances.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_candidate_table_writes_csv_and_json(tmp_path):
    table = build_instance_table([3, 4], seed_start=1, seed_end=2)
    csv_path = tmp_path / "nested" / "instances.csv"
    json_path = tmp_path / "nested" / "instances.json"

    write_csv(csv_path, table["instances"])
    write_json(json_path, table)

    assert table["schema_version"] == 1
    assert table["generator"] == "PancakeSortingEnv"
    assert len(table["instances"]) == 4

    saved_json = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved_json == table
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert list(rows[0]) == CSV_FIELDS
    assert json.loads(rows[0]["initial_state"]) == table["instances"][0]["initial_state"]
    assert json.loads(rows[0]["goal_state"]) == [1, 2, 3]
    assert json.loads(rows[0]["optimal_moves"]) == table["instances"][0]["optimal_moves"]


def test_candidate_table_rejects_reversed_seed_range():
    with pytest.raises(ValueError, match="seed_end"):
        build_instance_table([3], seed_start=2, seed_end=1)


def test_pancake_debug_aggregate_can_group_by_min_moves():
    rows = [
        {
            "N": 4,
            "min_moves": 3,
            "temperature": 0.6,
            "final_accuracy": 1,
            "goal_reached_all_mentions": True,
            "no_final": False,
            "length_stop": False,
            "loop_trap": False,
            "repeated_state_ratio": 0.1,
            "outcome_label": "success_final",
        },
        {
            "N": 4,
            "min_moves": 4,
            "temperature": 0.6,
            "final_accuracy": 0,
            "goal_reached_all_mentions": False,
            "no_final": False,
            "length_stop": True,
            "loop_trap": True,
            "repeated_state_ratio": 0.4,
            "outcome_label": "length_stop",
        },
    ]

    by_n = aggregate_runs(rows)
    by_min_moves = aggregate_runs(rows, group_by_min_moves=True)

    assert by_n[0]["runs"] == 2
    assert by_n[0]["final_accuracy"] == 0.5
    assert [(row["N"], row["min_moves"], row["runs"]) for row in by_min_moves] == [
        (4, 3, 1),
        (4, 4, 1),
    ]
    assert by_min_moves[1]["length_stop_count"] == 1


def test_instance_run_precedence_and_output_directory(tmp_path):
    path = write_instances_file(
        tmp_path,
        {
            "schema_version": 1,
            "temperature": 0.6,
            "num_predict": 8192,
            "instances": [
                {
                    "instance_id": "override",
                    "N": 4,
                    "seed": 7,
                    "initial_state": [3, 2, 1, 4],
                    "min_moves": 1,
                    "temperature": 0.9,
                    "num_predict": 256,
                },
                {
                    "instance_id": "from_cli",
                    "N": 4,
                    "initial_state": [1, 2, 4, 3],
                    "min_moves": 3,
                },
            ],
        },
    )

    runs = load_instance_runs(path, cli_temperatures=[0.2, 0.4], cli_num_predict=512)

    assert [(run.instance_id, run.temperature, run.num_predict) for run in runs] == [
        ("override", 0.9, 256),
        ("from_cli", 0.2, 512),
        ("from_cli", 0.4, 512),
    ]
    assert runs[0].seed == 7
    assert runs[1].seed is None
    assert output_dir_for_run(Path("out"), runs[1]) == Path(
        "out/from_cli_np512_T0_2"
    )

    root_runs = load_instance_runs(path, cli_temperatures=None, cli_num_predict=None)
    assert [(run.temperature, run.num_predict) for run in root_runs] == [
        (0.9, 256),
        (0.6, 8192),
    ]


def test_instances_file_rejects_min_moves_mismatch_before_execution(tmp_path):
    path = write_instances_file(
        tmp_path,
        {
            "schema_version": 1,
            "temperature": 0.6,
            "num_predict": 128,
            "instances": [
                {
                    "instance_id": "bad_mm",
                    "N": 4,
                    "initial_state": [3, 2, 1, 4],
                    "min_moves": 2,
                }
            ],
        },
    )

    with pytest.raises(ValueError, match=r"requested min_moves=2.*min_moves=1"):
        load_instance_runs(path, cli_temperatures=None, cli_num_predict=None)


@pytest.mark.parametrize("instance_id", ["has space", "../escape", "bad.dot", ""])
def test_instances_file_rejects_unsafe_instance_id(tmp_path, instance_id):
    path = write_instances_file(
        tmp_path,
        {
            "schema_version": 1,
            "temperature": 0.6,
            "num_predict": 128,
            "instances": [
                {
                    "instance_id": instance_id,
                    "N": 4,
                    "initial_state": [3, 2, 1, 4],
                    "min_moves": 1,
                }
            ],
        },
    )

    with pytest.raises(ValueError, match="instance_id"):
        load_instance_runs(path, cli_temperatures=None, cli_num_predict=None)


def test_checked_in_stratified_config_contains_valid_instances():
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    runs = load_instance_runs(CONFIG_PATH, cli_temperatures=None, cli_num_predict=None)

    assert len(runs) == len(data["instances"])
    assert {run.N for run in runs} == {3, 4, 5}
    assert {(run.N, run.requested_min_moves) for run in runs} >= {
        (3, 3),
        (4, 3),
        (4, 4),
        (5, 3),
        (5, 5),
    }
    for run in runs:
        env = PancakeSortingEnv(N=run.N, initial_state=run.initial_state)
        assert env.min_moves == run.requested_min_moves
        if run.seed is not None:
            generated = PancakeSortingEnv(N=run.N, seed=run.seed)
            assert generated.initial_state == run.initial_state


def test_run_one_writes_fixed_instance_metadata_without_model_loading(
    tmp_path, monkeypatch
):
    class StubTokenizer:
        def __call__(self, text, return_tensors):
            assert return_tensors == "pt"
            return SimpleNamespace(input_ids=[1, 2])

    monkeypatch.setattr(
        pancake_debug_sweep,
        "build_formatted_prompt",
        lambda tokenizer, prompt, env, n_shot, profile: "formatted",
    )
    monkeypatch.setattr(
        pancake_debug_sweep,
        "generate_text",
        lambda **kwargs: ("<final>\nFlip 3\n</final>", [10, 11], "eos"),
    )
    args = Namespace(
        model_id="test/model",
        n_shot=0,
        num_predict=None,
        repetition_penalty=1.1,
    )
    output_dir = tmp_path / "fixed"

    result = run_one(
        model=object(),
        tokenizer=StubTokenizer(),
        profile=SimpleNamespace(think_mode="none"),
        args=args,
        N=4,
        temperature=0.6,
        seed=17,
        output_dir=output_dir,
        initial_state=(3, 2, 1, 4),
        instance_id="N4_seed17_mm1",
        requested_min_moves=1,
        num_predict=123,
    )

    saved = json.loads((output_dir / "debug.json").read_text(encoding="utf-8"))
    assert result["final_accuracy"] == 1
    assert saved["instance_id"] == "N4_seed17_mm1"
    assert saved["instance_seed"] == 17
    assert saved["seed"] == 17
    assert saved["requested_min_moves"] == 1
    assert saved["min_moves"] == 1
    assert saved["initial_state"] == "(3, 2, 1, 4)"
    assert saved["num_predict"] == 123


def test_legacy_seed_sweep_keeps_defaults_and_directory_shape():
    args = Namespace(
        ns="3",
        temperatures=None,
        trials=1,
        seed_base=9,
        num_predict=None,
    )

    runs = build_seed_runs(args)

    assert len(runs) == 5
    assert runs[0] == SweepRun(N=3, temperature=0.0, num_predict=4096, seed=9)
    assert output_dir_for_run(Path("out"), runs[0]) == Path(
        "out/N3_seed9_np4096_T0_0"
    )


def test_stratified_shell_script_invokes_single_runner_process_in_dry_run():
    env = {
        **os.environ,
        "INSTANCES_FILE": str(CONFIG_PATH.relative_to(REPO_ROOT)),
        "TEMPERATURES": "0.6",
        "NUM_PREDICT": "8192",
        "ANALYZE": "0",
        "DRY_RUN": "1",
    }

    completed = subprocess.run(
        ["bash", str(SCRIPT_PATH)],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )

    assert completed.stdout.count("runners/pancake_debug_sweep.py") == 1
    assert "--instances-file" in completed.stdout
    assert "--temperatures" in completed.stdout
    assert "--num_predict" in completed.stdout
    assert "--ns" not in completed.stdout
    assert "--trials" not in completed.stdout


def test_hidden_sweep_selects_exact_min_moves_state():
    state = select_initial_state_by_min_moves(3, 3)

    env = PancakeSortingEnv(N=3, initial_state=state)
    assert state == (1, 3, 2)
    assert env.min_moves == 3


def test_hidden_sweep_builds_direct_min_moves_run():
    args = Namespace(
        instances_file=None,
        N=3,
        min_moves=3,
        initial_state=None,
        instance_index=0,
        instance_id=None,
        seed=11,
        temperature=None,
        num_predict=None,
    )

    runs = build_hidden_runs(args)

    assert len(runs) == 1
    assert runs[0].N == 3
    assert runs[0].min_moves == 3
    assert runs[0].initial_state == (1, 3, 2)
    assert runs[0].instance_id == "N3_mm3_idx1"
    assert runs[0].instance_seed == 11
    assert runs[0].temperature == 0.6
    assert runs[0].num_predict == 8192


def test_hidden_sweep_rejects_initial_state_min_moves_mismatch():
    args = Namespace(
        instances_file=None,
        N=4,
        min_moves=2,
        initial_state=(3, 2, 1, 4),
        instance_index=0,
        instance_id=None,
        seed=None,
        temperature=0.6,
        num_predict=128,
    )

    with pytest.raises(ValueError, match="requested min_moves=2"):
        build_hidden_runs(args)


def test_hidden_sweep_uses_instances_file_and_output_shape(tmp_path):
    path = write_instances_file(
        tmp_path,
        {
            "schema_version": 1,
            "temperature": 0.6,
            "num_predict": 8192,
            "instances": [
                {
                    "instance_id": "N3_seed1_mm3",
                    "N": 3,
                    "seed": 1,
                    "initial_state": [1, 3, 2],
                    "min_moves": 3,
                }
            ],
        },
    )
    args = Namespace(
        instances_file=path,
        temperature=None,
        num_predict=None,
    )

    runs = build_hidden_runs(args)

    assert len(runs) == 1
    assert runs[0].instance_id == "N3_seed1_mm3"
    assert runs[0].instance_seed == 1
    assert hidden_output_dir_for_run(Path("out"), "model", runs[0]) == Path(
        "out/model/N3_seed1_mm3_T0_6"
    )
    assert event_dir_for_run(Path("events"), "model", runs[0]) == Path(
        "events/model/N3_seed1_mm3_T0_6"
    )
