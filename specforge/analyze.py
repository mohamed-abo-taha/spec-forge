"""ast-based scan of a Python codebase.

Collects functions, methods, classes and HTTP endpoints so the generator works
from what actually exists instead of guessing.
"""
from __future__ import annotations

import ast
import os

from .models import AnalysisResult, CodeUnit

_ENDPOINT_ATTRS = {"route", "get", "post", "put", "delete", "patch"}


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = [a.arg for a in node.args.args]
    if node.args.vararg:
        args.append("*" + node.args.vararg.arg)
    if node.args.kwarg:
        args.append("**" + node.args.kwarg.arg)
    return f"{node.name}({', '.join(args)})"


def _first_str_arg(call: ast.Call) -> str:
    for a in call.args:
        if isinstance(a, ast.Constant) and isinstance(a.value, str):
            return a.value
    return ""


def _endpoint_from_decorator(dec: ast.expr) -> str | None:
    """Return an "METHOD /path" string if the decorator looks like a route, else None."""
    call = dec if isinstance(dec, ast.Call) else None
    target = call.func if call else dec
    if not isinstance(target, ast.Attribute) or target.attr not in _ENDPOINT_ATTRS:
        return None

    path = _first_str_arg(call) if call else ""
    if target.attr == "route":
        method = "GET"
        if call:
            for kw in call.keywords:
                if kw.arg == "methods" and isinstance(kw.value, (ast.List, ast.Tuple)):
                    methods = [e.value for e in kw.value.elts if isinstance(e, ast.Constant)]
                    if methods:
                        method = str(methods[0]).upper()
    else:
        method = target.attr.upper()
    return f"{method} {path}".strip()


def _analyze_file(path: str, root: str) -> list[CodeUnit]:
    with open(path, "r", encoding="utf-8") as fh:
        source = fh.read()
    tree = ast.parse(source, filename=path)
    rel = os.path.relpath(path, root).replace(os.sep, "/")
    units: list[CodeUnit] = []

    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{child.name}"
                http = ""
                for dec in child.decorator_list:
                    http = _endpoint_from_decorator(dec) or ""
                    if http:
                        break
                units.append(
                    CodeUnit(
                        qualname=qual,
                        kind="endpoint" if http else ("method" if prefix else "function"),
                        file=rel,
                        lineno=child.lineno,
                        signature=_signature(child),
                        docstring=(ast.get_docstring(child) or "").strip(),
                        http=http,
                    )
                )
            elif isinstance(child, ast.ClassDef):
                units.append(
                    CodeUnit(
                        qualname=f"{prefix}{child.name}",
                        kind="class",
                        file=rel,
                        lineno=child.lineno,
                        docstring=(ast.get_docstring(child) or "").strip(),
                    )
                )
                visit(child, prefix=f"{prefix}{child.name}.")

    visit(tree, prefix="")
    return units


def analyze_path(path: str) -> AnalysisResult:
    """Analyze a single .py file or a directory tree of them."""
    result = AnalysisResult(root=path if os.path.isdir(path) else os.path.dirname(path) or ".")
    files: list[str] = []
    if os.path.isfile(path) and path.endswith(".py"):
        files = [path]
        result.root = os.path.dirname(path) or "."
    else:
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", "venv", "node_modules"}]
            for name in filenames:
                if name.endswith(".py"):
                    files.append(os.path.join(dirpath, name))

    for fpath in sorted(files):
        try:
            result.units.extend(_analyze_file(fpath, result.root))
        except (SyntaxError, UnicodeDecodeError):
            # A file we cannot parse is skipped rather than crashing the run.
            continue
    result.file_count = len(files)
    return result
