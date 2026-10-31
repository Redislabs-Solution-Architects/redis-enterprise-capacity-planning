"""recap entry point and shared REQ-01 output convention."""
import argparse
from enum import Enum
import json
import sys

from recap.units import parse


class Verdict(str, Enum):
    OK = "ok"
    FEASIBLE = "feasible"
    FEASIBLE_IN_STEPS = "feasible-in-steps"
    INFEASIBLE = "infeasible"
    GOAL_MET = "goal-met"
    GOAL_NOT_MET = "goal-not-met"
    NO_PLAN = "no-plan"


def exit_code(verdict: Verdict | str) -> int:
    verdict = Verdict(verdict)
    return int(verdict in (Verdict.INFEASIBLE, Verdict.GOAL_NOT_MET, Verdict.NO_PLAN))


def emit(command, verdict, snapshot, *, reasons=(), plan=(), output_format="text", details=None):
    verdict = Verdict(verdict)
    partial = snapshot.get("provenance", {}).get("partial", False)
    provenance = {key: snapshot[key] for key in ("source", "collected_at", "provenance") if key in snapshot}
    result = {"schema_version": 1, "command": command, "verdict": verdict.value,
              "reasons": list(reasons), "partial": partial, "snapshot": provenance}
    from recap.constraints import warnings
    warning_list = warnings(snapshot) if 'nodes' in snapshot else []
    if warning_list:
        result['warnings'] = warning_list
    if plan:
        result["plan"] = list(plan)
    if details:
        result.update(details)
    if exit_code(verdict) and not reasons:
        raise ValueError("negative verdicts require reasons")
    if output_format == "json":
        print(json.dumps(result))
    else:
        print(("PARTIAL: " if partial else "") + verdict.value)
        for reason in reasons:
            print(reason)
        for warning in warning_list:
            print('warning: ' + warning)
        if details:
            from recap.units import format_gib
            for group, rows in details.items():
                if isinstance(rows, list):
                    for row in rows:
                        if isinstance(row, dict):
                            print(group + ': ' + ' '.join(f'{key}={format_gib(value) if key in ("free_ram", "shard_size") and isinstance(value,int) else value}' for key,value in row.items()))
                        else:
                            print(str(row))
                else:
                    print(f'{group}: {rows}')
    return exit_code(verdict)


def size(value):
    try:
        return parse(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def upscale_size(value):
    try:
        parse(value, current=0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    return value  # Relative quantities must be resolved against the loaded database.


def used_max(value):
    if value == "none":
        return None
    if value == "-1":
        raise argparse.ArgumentTypeError("use --shard-used-max none for no limit")
    return size(value)


def positive_int(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def common(parser, *, snapshot=True, markdown=False):
    if snapshot:
        parser.add_argument("--snapshot", required=True, help="snapshot file, or - for stdin")
        parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--format", choices=["text", "json"] + (["markdown"] if markdown else []), default="text")


def create_flags(parser):
    parser.add_argument("--memory", type=size, required=True)
    parser.add_argument("--shards", type=positive_int, required=True)
    parser.add_argument("--replication", action="store_true")
    racks = parser.add_mutually_exclusive_group()
    racks.add_argument("--rack-aware", dest="rack_aware", action="store_true")
    racks.add_argument("--no-rack-aware", dest="rack_aware", action="store_false")
    parser.set_defaults(rack_aware=None)
    parser.add_argument("--placement", choices=["dense", "sparse"])


def upscale_flags(parser):
    targets = parser.add_mutually_exclusive_group(required=True)
    targets.add_argument("--db")
    targets.add_argument("--all", action="store_true")
    parser.add_argument("--memory", type=upscale_size)
    parser.add_argument("--shards", type=positive_int)
    parser.add_argument("--ladder")
    parser.add_argument("--url")


def build_parser():
    parser = argparse.ArgumentParser(prog="recap", description="Offline Redis Software capacity planner")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    common(collect, snapshot=False)
    collect.add_argument("--url", required=True)
    collect.add_argument("--netrc", action="store_true")
    collect.add_argument("--ca-cert")
    collect.add_argument("--insecure", action="store_true")
    collect.add_argument("--allow-partial", action="store_true")
    collect.add_argument("--out", default="-")
    capacity = commands.add_parser("capacity")
    common(capacity)
    capacity.add_argument("--shard-size", type=size, nargs="+")
    capacity.add_argument("--ram-headroom", type=float, default=0)
    create = commands.add_parser("can-create")
    common(create)
    create_flags(create)
    upscale = commands.add_parser("can-upscale")
    common(upscale)
    upscale_flags(upscale)
    optimize = commands.add_parser("optimize")
    scopes = optimize.add_subparsers(dest="scope", required=True)
    for scope in ("db", "node", "rack", "cluster"):
        sub = scopes.add_parser(scope)
        common(sub)
        sub.add_argument("--" + (scope if scope != "cluster" else "rack"), required=scope != "cluster")
        for flag in ("shard-size-min", "shard-size-max", "need", "reserve-shard-size"):
            sub.add_argument("--" + flag, type=size)
        sub.add_argument("--shard-used-max", type=used_max, default=False)
        sub.add_argument("--level", type=int, choices=[1, 2], default=1)
        sub.add_argument("--explain", action="store_true")
    report = commands.add_parser("report")
    common(report, markdown=True)
    report.add_argument("--ladder")
    snapshot = commands.add_parser("snapshot")
    actions = snapshot.add_subparsers(dest="snapshot_action", required=True)
    common(actions.add_parser("validate"))
    cross = commands.add_parser("cross-check")
    common(cross)
    cross.add_argument("--url", required=True)
    cross.add_argument("--max-age", type=float, default=600)
    checks = cross.add_subparsers(dest="check", required=True)
    create_flags(checks.add_parser("can-create"))
    upscale_flags(checks.add_parser("can-upscale"))
    checks.add_parser("rebalance").add_argument("--db", required=True)
    return parser


def optimize_plan(snapshot,args):
    from recap.planner.optimize import plan
    return plan(snapshot,args)


def emit_plan(command,snapshot,result,args):
    from recap.verifier import verify
    success=exit_code(result['verdict'])==0
    verify(snapshot,result.get('plan',[]),result.get('goal') if success else None)
    return emit(command,result['verdict'],snapshot,reasons=result.get('reasons',[]),
                plan=result.get('plan',[]),output_format=args.format,details=result.get('details'))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "collect":
        from recap.collect import run
        return run(args)
    if args.command == 'can-create':
        from recap.snapshot import load, SnapshotError
        from recap.verifier import VerificationError
        from recap.planner.create import plan
        try:
            snapshot=load(args.snapshot,allow_partial=args.allow_partial)
            result=plan(snapshot,args.memory,args.shards,args.replication,args.rack_aware,args.placement)
            return emit_plan('can-create',snapshot,result,args)
        except VerificationError as exc:
            print(str(exc),file=sys.stderr)
            return 5
        except (SnapshotError,ValueError) as exc:
            print(str(exc),file=sys.stderr)
            return 2
    if args.command == 'optimize':
        from recap.snapshot import load, SnapshotError
        from recap.verifier import VerificationError
        try:
            snapshot=load(args.snapshot,allow_partial=args.allow_partial)
            result=optimize_plan(snapshot,args)
            return emit_plan('optimize',snapshot,result,args)
        except VerificationError as exc:
            print(str(exc),file=sys.stderr)
            return 5
        except (SnapshotError,ValueError) as exc:
            print(str(exc),file=sys.stderr)
            return 2
    if args.command == "capacity":
        from recap.snapshot import SnapshotError, load
        from recap.model import capacity
        try:
            snapshot = load(args.snapshot, allow_partial=args.allow_partial)
            details = capacity(snapshot, args.shard_size, args.ram_headroom)
            return emit('capacity','ok',snapshot,output_format=args.format,details=details)
        except (SnapshotError,ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 2
    if args.command == "snapshot" and args.snapshot_action == "validate":
        from recap.snapshot import SnapshotError, load
        try:
            snapshot = load(args.snapshot, allow_partial=args.allow_partial)
        except SnapshotError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return emit("snapshot validate", "ok", snapshot, output_format=args.format)
    print(f"{args.command}: not implemented", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
