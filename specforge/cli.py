"""Command-line interface for SpecForge.

    specforge analyze  PATH
    specforge generate PATH --request "..." [--llm mock|ollama] [--out FILE]
    specforge validate --artefacts FILE --code PATH [--report FILE]
    specforge run      PATH --request "..." [--llm mock|ollama] [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from .analyze import analyze_path
from .generate import generate_artefacts
from .llm import get_llm
from .models import Artefacts
from .validate import report_markdown, validate


def _cmd_analyze(args: argparse.Namespace) -> int:
    analysis = analyze_path(args.path)
    if args.json:
        print(json.dumps(analysis.to_dict(), indent=2))
    else:
        print(f"Analyzed {args.path}: {analysis.summary}")
        for u in analysis.units:
            tag = f" [{u.http}]" if u.http else ""
            print(f"  {u.kind:9} {u.qualname}{tag}  ({u.file}:{u.lineno})")
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    analysis = analyze_path(args.path)
    llm = get_llm(args.llm, model=args.model)
    artefacts = generate_artefacts(analysis, args.request, llm)
    out = artefacts.to_json()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"Wrote {args.out} "
              f"({len(artefacts.specifications)} spec, {len(artefacts.user_stories)} stories, "
              f"{len(artefacts.acceptance_criteria)} criteria, {len(artefacts.test_scenarios)} tests)")
    else:
        print(out)
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    with open(args.artefacts, "r", encoding="utf-8") as fh:
        artefacts = Artefacts.from_dict(json.load(fh))
    analysis = analyze_path(args.code)
    report = validate(artefacts, analysis)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report_markdown(artefacts, report))
        print(f"Wrote {args.report}")
    print(json.dumps(report.to_dict(), indent=2))
    return 0 if report.passed else 1


def _cmd_run(args: argparse.Namespace) -> int:
    analysis = analyze_path(args.path)
    llm = get_llm(args.llm, model=args.model)
    artefacts = generate_artefacts(analysis, args.request, llm)
    report = validate(artefacts, analysis)

    os.makedirs(args.out_dir, exist_ok=True)
    art_path = os.path.join(args.out_dir, "artefacts.json")
    rep_path = os.path.join(args.out_dir, "report.md")
    with open(art_path, "w", encoding="utf-8") as fh:
        fh.write(artefacts.to_json())
    with open(rep_path, "w", encoding="utf-8") as fh:
        fh.write(report_markdown(artefacts, report))

    status = "PASSED" if report.passed else "FAILED"
    print(f"Generated {len(artefacts.user_stories)} stories / {len(artefacts.acceptance_criteria)} criteria / "
          f"{len(artefacts.test_scenarios)} tests")
    print(f"Validation: {status}  score={report.score}/100  coverage={report.coverage:.0%}  "
          f"issues={sum(report.counts().values())}")
    print(f"Wrote {art_path} and {rep_path}")
    return 0 if report.passed else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="specforge", description="AI-assisted SDLC toolkit: codebase -> traceable, validated engineering artefacts.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="Statically analyze a Python codebase.")
    a.add_argument("path")
    a.add_argument("--json", action="store_true", help="Emit the analysis as JSON.")
    a.set_defaults(func=_cmd_analyze)

    g = sub.add_parser("generate", help="Generate engineering artefacts.")
    g.add_argument("path")
    g.add_argument("--request", required=True, help="The business request / change to specify.")
    g.add_argument("--llm", default="mock", choices=["mock", "ollama"])
    g.add_argument("--model", default=None, help="Model name for the chosen backend (e.g. llama3.2:3b).")
    g.add_argument("--out", default=None, help="Write artefacts JSON to this file.")
    g.set_defaults(func=_cmd_generate)

    v = sub.add_parser("validate", help="Validate artefacts against a codebase.")
    v.add_argument("--artefacts", required=True)
    v.add_argument("--code", required=True)
    v.add_argument("--report", default=None, help="Write a Markdown report to this file.")
    v.set_defaults(func=_cmd_validate)

    r = sub.add_parser("run", help="Generate + validate end to end.")
    r.add_argument("path")
    r.add_argument("--request", required=True)
    r.add_argument("--llm", default="mock", choices=["mock", "ollama"])
    r.add_argument("--model", default=None)
    r.add_argument("--out-dir", default="specforge_out")
    r.set_defaults(func=_cmd_run)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
