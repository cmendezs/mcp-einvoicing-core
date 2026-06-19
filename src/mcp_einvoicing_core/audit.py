"""Shared audit infrastructure for mcp-einvoicing country packages.

Provides the data types, CHECK 1 (core interface coverage) runner, CHECK 4
(version compatibility) runner, and report-rendering utilities that are
identical across every per-package ``audit/audit_vs_core.py`` script.

Country packages keep their own CHECK 2 (tool registry), CHECK 3 (model
alignment), and CHECK 5 (country-specific structural) checks, and delegate
CHECK 1 and CHECK 4 to this module.

Install the optional extra to guarantee full PEP 440 specifier support:
    pip install 'mcp-einvoicing-core[audit]'

Without the extra the module is still usable; version comparisons fall back to
a minimal ``>=`` / ``<`` parser that is sufficient for the standard
``>=X.Y,<X+1`` range used by all country packages.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import importlib.metadata
import inspect
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

SEVERITY_BLOCKING = "BLOCKING"
SEVERITY_WARNING = "WARNING"
SEVERITY_OK = "OK"
SEVERITY_SKIP = "SKIP"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CheckFinding:
    """Single finding emitted by one audit check."""

    check_id: str
    tag: str        # e.g. [OK], [MISSING], [OVERRIDE], [SKIP], [WRONG_BASE_CLASS]
    severity: str   # SEVERITY_* constant
    symbol: str     # Qualified name of the checked item
    message: str


@dataclass
class CheckResult:
    """Aggregated findings for one audit check."""

    check_id: str
    name: str
    findings: list[CheckFinding] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str = ""

    @property
    def blocking_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_BLOCKING)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_WARNING)

    @property
    def passed(self) -> bool:
        return self.blocking_count == 0


@dataclass
class AuditReport:
    """Full audit report for one country package."""

    generated_at: str
    pkg_name: str           # e.g. "mcp-einvoicing-de"
    pkg_version: str        # installed version of the country package
    core_version: str | None
    core_version_compatible: bool
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def total_blocking(self) -> int:
        return sum(c.blocking_count for c in self.checks)

    @property
    def total_warnings(self) -> int:
        return sum(c.warning_count for c in self.checks)

    @property
    def exit_code(self) -> int:
        if self.total_blocking > 0:
            return 2
        if self.total_warnings > 0:
            return 1
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "pkg_name": self.pkg_name,
            "pkg_version": self.pkg_version,
            "core_version": self.core_version,
            "core_version_compatible": self.core_version_compatible,
            "exit_code": self.exit_code,
            "total_blocking": self.total_blocking,
            "total_warnings": self.total_warnings,
            "checks": [
                {
                    "check_id": c.check_id,
                    "name": c.name,
                    "passed": c.passed,
                    "skipped": c.skipped,
                    "skip_reason": c.skip_reason,
                    "blocking_count": c.blocking_count,
                    "warning_count": c.warning_count,
                    "findings": [
                        {
                            "check_id": f.check_id,
                            "tag": f.tag,
                            "severity": f.severity,
                            "symbol": f.symbol,
                            "message": f.message,
                        }
                        for f in c.findings
                    ],
                }
                for c in self.checks
            ],
        }


# ---------------------------------------------------------------------------
# Shared helpers (re-usable by per-package CHECK 2 / 3 / 5 implementations)
# ---------------------------------------------------------------------------


def _try_import(module_path: str) -> tuple[Any | None, str | None]:
    """Attempt to import a module; return (module, None) or (None, error_str)."""
    try:
        return importlib.import_module(module_path), None
    except ImportError as exc:
        return None, str(exc)


def _get_public_symbols(module: Any) -> dict[str, Any]:
    """Return all public symbols from a module, respecting ``__all__`` if defined."""
    if hasattr(module, "__all__"):
        return {
            name: getattr(module, name)
            for name in module.__all__
            if hasattr(module, name)
        }
    return {
        name: obj
        for name, obj in inspect.getmembers(module)
        if not name.startswith("_") and not inspect.ismodule(obj)
    }


def _get_installed_version(package_name: str) -> str | None:
    """Return the installed version of *package_name*, or None if not found."""
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _version_in_range(version: str, spec: str) -> bool:
    """Check whether *version* satisfies the PEP 440 specifier *spec*.

    Tries ``packaging.specifiers.SpecifierSet`` first (full PEP 440). Falls
    back to a minimal ``>=`` / ``<`` / ``~=`` parser when ``packaging`` is
    not installed. Install ``mcp-einvoicing-core[audit]`` for full support.
    """
    try:
        from packaging.specifiers import SpecifierSet  # noqa: PLC0415
        from packaging.version import Version  # noqa: PLC0415
        return Version(version) in SpecifierSet(spec)
    except ImportError:
        pass
    except Exception:
        return True

    # Naive fallback — sufficient for >=X.Y,<X+1 ranges used by all packages.
    def _parse(v: str) -> tuple[int, ...]:
        parts = v.split(".")
        result = []
        for p in parts[:3]:
            try:
                result.append(int(p.split("a")[0].split("b")[0].split("rc")[0]))
            except ValueError:
                result.append(0)
        while len(result) < 3:
            result.append(0)
        return tuple(result)

    parsed = _parse(version)
    for part in spec.split(","):
        part = part.strip()
        if part.startswith(">="):
            if parsed < _parse(part[2:].strip()):
                return False
        elif part.startswith("<"):
            if parsed >= _parse(part[1:].strip()):
                return False
        elif part.startswith("~="):
            base = _parse(part[2:].strip())
            if len(base) >= 2 and (parsed < base or parsed[0] != base[0]):
                return False
    return True


def _read_core_version_spec(pyproject_path: Path) -> str | None:
    """Extract the ``mcp-einvoicing-core`` version specifier from *pyproject_path*."""
    if not pyproject_path.exists():
        return None
    try:
        text = pyproject_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            if "mcp-einvoicing-core" in line:
                start = line.find("mcp-einvoicing-core")
                fragment = line[start:].strip().strip('",').strip("'")
                spec = fragment.replace("mcp-einvoicing-core", "").strip()
                return spec if spec else None
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Canonical module list (authoritative list of core sub-modules to audit)
# ---------------------------------------------------------------------------

#: Sub-modules whose public symbols form the country-package integration contract.
#: Excludes ``mcp_einvoicing_core.logging_utils`` (internal, not in __all__)
#: and ``mcp_einvoicing_core.testing`` (test fixtures, not runtime).
DEFAULT_CORE_MODULES: list[str] = [
    "mcp_einvoicing_core.base_server",
    "mcp_einvoicing_core.digital_signature",
    "mcp_einvoicing_core.download_rules",
    "mcp_einvoicing_core.en16931",
    "mcp_einvoicing_core.exceptions",
    "mcp_einvoicing_core.http_client",
    "mcp_einvoicing_core.models",
    "mcp_einvoicing_core.pdf",
    "mcp_einvoicing_core.peppol",
    "mcp_einvoicing_core.profile_registry",
    "mcp_einvoicing_core.qr",
    "mcp_einvoicing_core.schematron",
    "mcp_einvoicing_core.xml_utils",
]


# ---------------------------------------------------------------------------
# CHECK 1 — Core interface coverage (canonical invoice tree sub-check)
# ---------------------------------------------------------------------------


def _run_invoice_tree_check(
    result: CheckResult,
    is_en16931_family: bool,
    primary_invoice_class: tuple[str, str],
    package_label: str,
) -> None:
    """CHECK 1 sub-check: verify the canonical invoice tree rule.

    EN 16931 family packages must extend ``EN16931Invoice``; all others must
    extend ``InvoiceDocument``. Emits a single BLOCKING finding if violated.
    See CLAUDE.md "Canonical invoice tree" for the full rule.
    """
    mod_path, cls_name = primary_invoice_class

    country_mod, err = _try_import(mod_path)
    if country_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol=f"{mod_path}.{cls_name}",
            message=f"Cannot verify invoice tree: could not import {mod_path}: {err}",
        ))
        return

    country_cls = getattr(country_mod, cls_name, None)
    if country_cls is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[MISSING]",
            severity=SEVERITY_BLOCKING,
            symbol=f"{mod_path}.{cls_name}",
            message=f"Primary invoice class '{cls_name}' not found in {mod_path}.",
        ))
        return

    if is_en16931_family:
        core_mod, _ = _try_import("mcp_einvoicing_core.en16931")
        base_name = "EN16931Invoice"
        base_source = "mcp_einvoicing_core.en16931"
    else:
        core_mod, _ = _try_import("mcp_einvoicing_core.models")
        base_name = "InvoiceDocument"
        base_source = "mcp_einvoicing_core.models"

    if core_mod is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol=base_name,
            message=f"Cannot verify invoice tree: {base_source} not importable.",
        ))
        return

    expected_base = getattr(core_mod, base_name, None)
    if expected_base is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol=base_name,
            message=f"Base class '{base_name}' not found in {base_source}.",
        ))
        return

    pathway = "EN 16931 family" if is_en16931_family else "non-EN 16931"
    if issubclass(country_cls, expected_base):
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[OK]",
            severity=SEVERITY_OK,
            symbol=f"{cls_name} → {base_name}",
            message=(
                f"{cls_name} correctly extends {base_name} "
                f"(canonical invoice tree, {pathway} pathway)."
            ),
        ))
    else:
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[WRONG_BASE_CLASS]",
            severity=SEVERITY_BLOCKING,
            symbol=f"{cls_name} → {base_name}",
            message=(
                f"{package_label} is a {pathway} package: {cls_name} must extend "
                f"{base_name} from {base_source}, not be a standalone implementation. "
                "See CLAUDE.md 'Canonical invoice tree' and resolve before publish."
            ),
        ))


def _collect_package_imports(package_modules: list[str]) -> set[str]:
    """Collect names of core symbols imported into any of *package_modules*."""
    imported: set[str] = set()
    for mod_path in package_modules:
        mod, _ = _try_import(mod_path)
        if mod is None:
            continue
        for name, obj in inspect.getmembers(mod):
            if not name.startswith("_"):
                obj_module = getattr(obj, "__module__", "") or ""
                if "mcp_einvoicing_core" in obj_module:
                    imported.add(name)
    return imported


def run_check_core_coverage(
    *,
    package_name: str,
    package_modules: list[str],
    intentional_overrides: dict[str, set[str]] | None = None,
    modules_to_check: list[str] | None = None,
    is_en16931_family: bool | None = None,
    primary_invoice_class: tuple[str, str] | None = None,
) -> CheckResult:
    """CHECK 1 — Core interface coverage.

    Verifies that every public class and function in each core sub-module is
    either imported by the country package or marked as an intentional override.
    Optionally runs the canonical invoice tree sub-check.

    Args:
        package_name: PyPI name of the country package (e.g. "mcp-einvoicing-de").
            Used in missing-symbol messages.
        package_modules: Dotted import paths of the package's own modules to
            scan for core symbol usage (e.g. ``_DE_MODULES``).
        intentional_overrides: ``{module_path: {symbol_names}}`` declaring
            symbols the package deliberately does not import. Defaults to ``{}``.
        modules_to_check: Core sub-modules to check. Defaults to
            ``DEFAULT_CORE_MODULES`` (the 13-module canonical list).
        is_en16931_family: ``True`` → primary class must extend ``EN16931Invoice``;
            ``False`` → must extend ``InvoiceDocument``; ``None`` → skip tree check.
        primary_invoice_class: ``(module_path, class_name)`` of the package's
            main invoice model. Required when *is_en16931_family* is not ``None``.

    Returns:
        CheckResult with id ``"CHECK_1"``.
    """
    result = CheckResult(check_id="CHECK_1", name="Core interface coverage")
    overrides = intentional_overrides or {}
    mods = modules_to_check if modules_to_check is not None else DEFAULT_CORE_MODULES
    label = package_name

    if _get_installed_version("mcp-einvoicing-core") is None:
        result.skipped = True
        result.skip_reason = (
            "mcp-einvoicing-core is not installed. "
            "Install it with: pip install mcp-einvoicing-core"
        )
        result.findings.append(CheckFinding(
            check_id="CHECK_1",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="mcp-einvoicing-core",
            message="Package not installed — cannot verify core interface coverage.",
        ))
        return result

    pkg_imports = _collect_package_imports(package_modules)

    for mod_path in mods:
        core_mod, err = _try_import(mod_path)
        if core_mod is None:
            result.findings.append(CheckFinding(
                check_id="CHECK_1",
                tag="[SKIP]",
                severity=SEVERITY_WARNING,
                symbol=mod_path,
                message=f"Could not import core module: {err}",
            ))
            continue

        overrides_for_mod = overrides.get(mod_path, set())
        symbols = _get_public_symbols(core_mod)

        for sym_name, sym_obj in symbols.items():
            if not (inspect.isclass(sym_obj) or inspect.isfunction(sym_obj)):
                continue

            if sym_name in overrides_for_mod:
                result.findings.append(CheckFinding(
                    check_id="CHECK_1",
                    tag="[OVERRIDE]",
                    severity=SEVERITY_OK,
                    symbol=f"{mod_path}.{sym_name}",
                    message=f"Intentionally overridden by {label}.",
                ))
            elif sym_name in pkg_imports:
                result.findings.append(CheckFinding(
                    check_id="CHECK_1",
                    tag="[OK]",
                    severity=SEVERITY_OK,
                    symbol=f"{mod_path}.{sym_name}",
                    message="Imported and used.",
                ))
            else:
                result.findings.append(CheckFinding(
                    check_id="CHECK_1",
                    tag="[MISSING]",
                    severity=SEVERITY_WARNING,
                    symbol=f"{mod_path}.{sym_name}",
                    message=(
                        f"Core symbol '{sym_name}' is neither imported by {label} "
                        "nor marked as an intentional override. "
                        "Add to _INTENTIONAL_OVERRIDES if this is deliberate."
                    ),
                ))

    # Canonical invoice tree sub-check
    if is_en16931_family is not None and primary_invoice_class is not None:
        _run_invoice_tree_check(result, is_en16931_family, primary_invoice_class, label)

    return result


# ---------------------------------------------------------------------------
# CHECK 4 — Version compatibility
# ---------------------------------------------------------------------------


def run_check_version_compatibility(
    *,
    package_name: str,
    pyproject_path: Path,
) -> CheckResult:
    """CHECK 4 — Version compatibility.

    Verifies that the installed ``mcp-einvoicing-core`` version satisfies the
    specifier declared in the country package's ``pyproject.toml``.

    Args:
        package_name: PyPI name of the country package (for messages).
        pyproject_path: Absolute path to the country package's ``pyproject.toml``.

    Returns:
        CheckResult with id ``"CHECK_4"``.
    """
    result = CheckResult(check_id="CHECK_4", name="Version compatibility")

    installed_core = _get_installed_version("mcp-einvoicing-core")
    if installed_core is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_4",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="mcp-einvoicing-core",
            message=(
                "mcp-einvoicing-core is not installed — cannot check version compatibility."
            ),
        ))
        return result

    declared_spec = _read_core_version_spec(pyproject_path)
    if declared_spec is None:
        result.findings.append(CheckFinding(
            check_id="CHECK_4",
            tag="[SKIP]",
            severity=SEVERITY_WARNING,
            symbol="pyproject.toml",
            message=(
                f"Could not parse mcp-einvoicing-core version spec from "
                f"{pyproject_path}. Ensure the file uses standard PEP 440 specifiers."
            ),
        ))
        return result

    compatible = _version_in_range(installed_core, declared_spec)
    result.findings.append(CheckFinding(
        check_id="CHECK_4",
        tag="[OK]" if compatible else "[VERSION_MISMATCH]",
        severity=SEVERITY_OK if compatible else SEVERITY_BLOCKING,
        symbol="mcp-einvoicing-core",
        message=(
            f"Installed: {installed_core} | "
            f"Declared range: {declared_spec} | "
            f"Compatible: {compatible}"
        ),
    ))
    return result


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def render_summary_table(report: AuditReport) -> str:
    """Render a human-readable ASCII summary table for *report*."""
    lines: list[str] = []
    sep = "─" * 80

    lines.append(sep)
    lines.append(f"  {report.pkg_name}  Pre-publish Audit Report")
    lines.append(f"  Generated : {report.generated_at}")
    lines.append(f"  Version   : {report.pkg_version}")
    lines.append(f"  Core ver  : {report.core_version or 'not installed'}")
    lines.append(sep)

    for check in report.checks:
        status = "SKIPPED" if check.skipped else ("PASS" if check.passed else "FAIL")
        lines.append(f"\n  [{status}] {check.check_id}: {check.name}")
        if check.skipped:
            lines.append(f"         ↳ {check.skip_reason}")
            continue
        lines.append(
            f"         Blocking: {check.blocking_count}  "
            f"Warnings: {check.warning_count}  "
            f"OK: {sum(1 for f in check.findings if f.severity == SEVERITY_OK)}"
        )
        for finding in check.findings:
            if finding.severity in (SEVERITY_BLOCKING, SEVERITY_WARNING):
                indent = "    "
                tag_str = f"{finding.tag:<24}"
                msg = textwrap.fill(
                    finding.message,
                    width=72,
                    initial_indent=indent + tag_str + " ",
                    subsequent_indent=indent + " " * 25,
                )
                lines.append(msg)

    lines.append(f"\n{sep}")
    lines.append(
        f"  TOTAL — Blocking: {report.total_blocking}  "
        f"Warnings: {report.total_warnings}  "
        f"Exit code: {report.exit_code}"
    )
    verdict = {0: "PASS", 1: "WARNINGS", 2: "FAIL"}[report.exit_code]
    lines.append(f"  Verdict: {verdict}")
    lines.append(sep)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI argument parsing (shared boilerplate)
# ---------------------------------------------------------------------------


def parse_audit_args(
    description: str,
    argv: list[str] | None = None,
) -> argparse.Namespace:
    """Parse standard audit CLI arguments.

    Args:
        description: Shown in ``--help`` output.
        argv: Argument list; defaults to ``sys.argv[1:]``.

    Returns:
        Namespace with ``output``, ``fail_on``, and ``quiet`` attributes.
    """
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Exit codes:
          0  All checks passed
          1  Warnings only
          2  Blocking failures (publish should be blocked)
        """),
    )
    parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write JSON report to this path (default: audit/report.json)",
        default=None,
    )
    parser.add_argument(
        "--fail-on",
        metavar="LEVEL",
        choices=["blocking", "warnings", "never"],
        default="blocking",
        help=(
            "When to exit non-zero: "
            "'blocking' (default) = only on BLOCKING findings; "
            "'warnings' = on any warning or blocking; "
            "'never' = always exit 0."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress human-readable table; only write JSON.",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Convenience: build AuditReport header fields
# ---------------------------------------------------------------------------


def make_report(
    pkg_name: str,
    pyproject_path: Path,
) -> AuditReport:
    """Construct an empty ``AuditReport`` with header fields populated.

    Args:
        pkg_name: PyPI package name (e.g. ``"mcp-einvoicing-de"``).
        pyproject_path: Path to the country package's ``pyproject.toml`` (used
            to extract the declared core specifier for version compatibility).

    Returns:
        Empty AuditReport ready for checks to be appended.
    """
    pkg_version = _get_installed_version(pkg_name) or "0.0.0-dev"
    core_version = _get_installed_version("mcp-einvoicing-core")
    core_compat = True
    if core_version:
        spec = _read_core_version_spec(pyproject_path)
        if spec:
            core_compat = _version_in_range(core_version, spec)

    return AuditReport(
        generated_at=datetime.now(UTC).isoformat(),
        pkg_name=pkg_name,
        pkg_version=pkg_version,
        core_version=core_version,
        core_version_compatible=core_compat,
    )


# ---------------------------------------------------------------------------
# CHECK 6 — Known shared helpers (compliance audit 2.3)
# ---------------------------------------------------------------------------

KNOWN_SHARED_HELPERS: frozenset[str] = frozenset({
    "format_amount",
    "format_quantity",
    "safe_fromstring",
    "xml_element",
    "xml_optional",
    "format_error",
    "filter_empty_values",
    "resolve_xml_input",
    "mark_untrusted",
    "mark_untrusted_fields",
    "scrub",
    "validate_date_iso",
    "validate_iban",
    "assert_not_read_only",
    "xml_escape",
})


def _collect_defined_functions(source_dir: Path) -> list[tuple[str, str, int]]:
    """Walk *source_dir* for ``def`` statements; return ``[(name, filepath, lineno)]``."""
    results: list[tuple[str, str, int]] = []
    if not source_dir.is_dir():
        return results
    for py_file in source_dir.rglob("*.py"):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                results.append((node.name, str(py_file), node.lineno))
    return results


def run_check_known_shared_helpers(
    *,
    source_dir: Path,
    package_label: str,
    extra_helpers: frozenset[str] | None = None,
) -> CheckResult:
    """CHECK 6 — detect re-implementations of core helpers in a country package.

    AST-scans all ``.py`` files under *source_dir* for function definitions
    whose names match ``KNOWN_SHARED_HELPERS`` (or *extra_helpers*). Any match
    is BLOCKING: the country package must use the core export instead.

    Args:
        source_dir: Path to the country package's ``src/`` directory.
        package_label: Human-readable package name for messages.
        extra_helpers: Additional function names to flag beyond the default set.

    Returns:
        CheckResult with id ``"CHECK_6"``.
    """
    result = CheckResult(check_id="CHECK_6", name="Known shared helpers")
    helpers = KNOWN_SHARED_HELPERS | (extra_helpers or frozenset())

    if not source_dir.is_dir():
        result.skipped = True
        result.skip_reason = f"Source directory not found: {source_dir}"
        return result

    defined = _collect_defined_functions(source_dir)
    seen: set[str] = set()

    for func_name, filepath, lineno in defined:
        if func_name in helpers and func_name not in seen:
            seen.add(func_name)
            result.findings.append(CheckFinding(
                check_id="CHECK_6",
                tag="[REIMPLEMENTED]",
                severity=SEVERITY_BLOCKING,
                symbol=func_name,
                message=(
                    f"{package_label} defines '{func_name}' at {filepath}:{lineno}. "
                    f"This is a core helper — use the export from mcp_einvoicing_core "
                    f"instead of re-implementing."
                ),
            ))

    if not seen:
        result.findings.append(CheckFinding(
            check_id="CHECK_6",
            tag="[OK]",
            severity=SEVERITY_OK,
            symbol="(all)",
            message=f"No core helpers re-implemented in {package_label}.",
        ))

    return result


# ---------------------------------------------------------------------------
# load_rates — file-driven tax rate loading (compliance audit 4.2)
# ---------------------------------------------------------------------------


@dataclass
class TaxRate:
    """A single tax rate entry loaded from ``specs/rates.toml``."""

    name: str
    value: str
    effective_from: str
    source: str
    category: str = ""


def load_rates(rates_path: Path) -> list[TaxRate]:
    """Load and validate tax rates from a ``specs/rates.toml`` file.

    Each entry under ``[rates.<name>]`` must contain ``value``,
    ``effective_from``, and ``source`` fields. Missing fields raise
    ``ValueError``.

    Args:
        rates_path: Path to the ``specs/rates.toml`` file.

    Returns:
        List of validated ``TaxRate`` entries.

    Raises:
        FileNotFoundError: If *rates_path* does not exist.
        ValueError: If any entry is missing required fields.
    """
    import tomllib  # noqa: PLC0415

    if not rates_path.exists():
        raise FileNotFoundError(f"Tax rates file not found: {rates_path}")

    with open(rates_path, "rb") as f:
        data = tomllib.load(f)

    rates_section = data.get("rates", {})
    if not rates_section:
        raise ValueError(f"No [rates] section found in {rates_path}")

    required_fields = {"value", "effective_from", "source"}
    results: list[TaxRate] = []

    for name, entry in rates_section.items():
        if not isinstance(entry, dict):
            raise ValueError(f"rates.{name}: expected a table, got {type(entry).__name__}")
        missing = required_fields - set(entry.keys())
        if missing:
            raise ValueError(
                f"rates.{name}: missing required fields: {', '.join(sorted(missing))}. "
                f"Each rate entry must include value, effective_from, and source."
            )
        results.append(TaxRate(
            name=name,
            value=str(entry["value"]),
            effective_from=str(entry["effective_from"]),
            source=str(entry["source"]),
            category=str(entry.get("category", "")),
        ))

    return results
