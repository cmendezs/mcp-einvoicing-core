"""Download-rules framework and CLI for mcp-einvoicing-core.

Provides the shared infrastructure for fetching Schematron XSLT artefacts
from their official sources.  Country packages define their own
DownloadSpec lists and entry points; this module supplies the HTTP download
utility, ZIP extraction helper, and the top-level CLI that lists available
country-specific commands.

Country package usage:

    # In mcp_einvoicing_de/download_rules.py
    from mcp_einvoicing_core.download_rules import DownloadSpec, download_artefacts
    from pathlib import Path

    _TARGET = Path(__file__).parent / "resources" / "schematron"

    SPECS = [
        DownloadSpec(
            name="EN 16931 CII Schematron",
            url="https://...",          # [Unverified: confirm URL from official source]
            dest_filename="EN16931-CII-validation.xslt",
            zip_path="path/in/zip.xslt",
        ),
    ]

    def main() -> int:
        return download_artefacts(SPECS, _TARGET)

    if __name__ == "__main__":
        raise SystemExit(main())

Entry points are declared per-package in pyproject.toml:

    [project.scripts]
    mcp-einvoicing-de-download-rules = "mcp_einvoicing_de.download_rules:main"
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DownloadSpec:
    """Specification for a single Schematron artefact to download.

    name:          Human-readable label shown in progress output.
    url:           HTTP URL of the source file (ZIP or direct XSLT).
    dest_filename: Filename to write inside *target_dir*.
    zip_path:      Path of the file inside the ZIP archive when *url* points
                   to a ZIP.  Set to None when the URL is a direct XSLT file.
    headers:       Optional extra HTTP headers (e.g. Accept, Authorization).
    """

    name: str
    url: str
    dest_filename: str
    zip_path: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


def download_artefacts(
    specs: list[DownloadSpec],
    target_dir: Path,
    *,
    overwrite: bool = False,
    http_timeout: float = 60.0,
) -> int:
    """Download a list of Schematron artefacts into *target_dir*.

    Args:
        specs:       List of DownloadSpec objects describing what to fetch.
        target_dir:  Directory to write the downloaded files into.
                     Created if it does not exist.
        overwrite:   If False (default), skip files that already exist.
        http_timeout: HTTP request timeout in seconds.

    Returns:
        0 on full success, 1 if any download failed.
    """
    try:
        import httpx
    except ImportError:  # pragma: no cover
        print("ERROR: httpx is required. Install: pip install httpx")
        return 1

    target_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for spec in specs:
        dest = target_dir / spec.dest_filename
        if dest.exists() and not overwrite:
            print(f"  [skip] {spec.dest_filename} (already present; use --overwrite to replace)")
            continue

        print(f"  [fetch] {spec.name}")
        print(f"          {spec.url}")
        try:
            response = httpx.get(
                spec.url,
                headers={**spec.headers, "User-Agent": "mcp-einvoicing-download-rules/1.0"},
                follow_redirects=True,
                timeout=http_timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            msg = f"FAILED to download {spec.name}: {exc}"
            print(f"  [error] {msg}")
            errors.append(msg)
            continue

        content = response.content

        if spec.zip_path is not None:
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    content = zf.read(spec.zip_path)
            except KeyError:
                available = [n for n in zf.namelist() if n.endswith(".xslt")]
                msg = (
                    f"Path {spec.zip_path!r} not found in ZIP. "
                    f"Available XSLT files: {available[:10]}"
                )
                print(f"  [error] {msg}")
                errors.append(msg)
                continue
            except Exception as exc:
                msg = f"FAILED to extract {spec.zip_path!r} from ZIP: {exc}"
                print(f"  [error] {msg}")
                errors.append(msg)
                continue

        dest.write_bytes(content)
        print(f"  [ok]    {dest} ({len(content):,} bytes)")

    if errors:
        print(f"\n{len(errors)} error(s) occurred:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"\nAll artefacts written to: {target_dir}")
    return 0


def main() -> int:
    """Core-level download-rules CLI.

    Auto-discovers installed country packages that register under the
    ``mcp_einvoicing.download_rules`` entry-point group and lists their
    commands. Country packages register via pyproject.toml:

        [project.entry-points."mcp_einvoicing.download_rules"]
        mcp-einvoicing-de-download-rules = "mcp_einvoicing_de.download_rules:main"
    """
    print("mcp-einvoicing-download-rules")
    print()

    discovered = sorted(
        entry_points(group="mcp_einvoicing.download_rules"), key=lambda e: e.name
    )

    if discovered:
        print("Available country download commands (installed packages):")
        print()
        for ep in discovered:
            print(f"  {ep.name}")
        print()
        print("Run any command above with --help for usage details.")
    else:
        print("No country packages with download rules are currently installed.")
        print()
        print("Install a country package and its command will appear here.")
        print("Example:")
        print()
        print("  pip install mcp-einvoicing-de")
        print("  mcp-einvoicing-de-download-rules")

    print()
    print("Or call download_artefacts() directly from your country package's")
    print("download_rules module.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
