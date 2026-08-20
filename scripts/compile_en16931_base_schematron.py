"""Dev-time compiler: CEN EN 16931 base Schematron (.sch) -> validating XSLT.

Not shipped in the wheel and not run at install time. Regenerates the bundled
artefact at src/mcp_einvoicing_core/resources/schematron/en16931_base/ from
the vendored .sch source in specs/peppol/.

Compiler: SchXslt2 (MIT, David Maus), vendored at scripts/vendor/schxslt2-*/.
Provenance for both the .sch input and the SchXslt2 compiler is documented in
specs/peppol/README.md.

Runtime dependency: saxonche only (the [xslt2] extra core already ships).
SchXslt2 itself is dev-tooling, never imported at runtime.

Only the CEN base file is compiled here. The Peppol overlay
(PEPPOL-EN16931-UBL-3.0.20.sch) has no confirmed redistribution rights and
must never be run through this script or bundled as output — see
context-library/decisions/peppol-schematron-artifact.md.

Usage (from the workspace root main checkout, not a worktree):

    uv run --package mcp-einvoicing-core --extra xslt2 \\
        python mcp-einvoicing-core/scripts/compile_en16931_base_schematron.py
"""

from __future__ import annotations

from pathlib import Path

_CORE_ROOT = Path(__file__).resolve().parent.parent
_SCH_SOURCE = _CORE_ROOT / "specs" / "peppol" / "CEN-EN16931-UBL-3.0.20.sch"
_OUTPUT_XSLT = (
    _CORE_ROOT
    / "src"
    / "mcp_einvoicing_core"
    / "resources"
    / "schematron"
    / "en16931_base"
    / "CEN-EN16931-UBL.xslt"
)


def _find_transpiler() -> Path:
    """Locate the vendored SchXslt2 transpile.xsl, whichever version is present."""
    candidates = sorted(_CORE_ROOT.glob("scripts/vendor/schxslt2-*/transpile.xsl"))
    if not candidates:
        raise FileNotFoundError(
            "No vendored SchXslt2 transpile.xsl found under scripts/vendor/schxslt2-*/. "
            "See specs/peppol/README.md 'Build tooling' for the source to fetch."
        )
    return candidates[-1]


def compile_en16931_base() -> int:
    """Compile the CEN EN 16931 base .sch into the bundled runtime .xslt.

    Returns:
        0 on success, 1 on failure (missing input, missing compiler, or a
        Saxon compile/transform error).
    """
    try:
        from saxonche import PySaxonProcessor  # type: ignore[import-not-found]
    except ImportError:
        print(
            "ERROR: saxonche is required to run this compiler. "
            "Install with: uv sync --package mcp-einvoicing-core --extra xslt2"
        )
        return 1

    if not _SCH_SOURCE.exists():
        print(f"ERROR: Schematron source not found: {_SCH_SOURCE}")
        return 1

    try:
        transpiler = _find_transpiler()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"  [source]     {_SCH_SOURCE}")
    print(f"  [transpiler] {transpiler}")

    _OUTPUT_XSLT.parent.mkdir(parents=True, exist_ok=True)

    with PySaxonProcessor(license=False) as proc:
        xslt30 = proc.new_xslt30_processor()
        try:
            executable = xslt30.compile_stylesheet(stylesheet_file=str(transpiler))
        except Exception as exc:  # noqa: BLE001 - reported to the operator, not swallowed
            print(f"ERROR: failed to compile SchXslt2 transpiler: {exc}")
            return 1

        try:
            executable.transform_to_file(
                source_file=str(_SCH_SOURCE), output_file=str(_OUTPUT_XSLT)
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: SchXslt2 transpilation failed: {exc}")
            return 1

    size = _OUTPUT_XSLT.stat().st_size
    print(f"  [ok] {_OUTPUT_XSLT} ({size:,} bytes)")
    return 0


def main() -> int:
    print("compile_en16931_base_schematron")
    print()
    return compile_en16931_base()


if __name__ == "__main__":
    raise SystemExit(main())
