"""Public CMS data sources: registry, download, provenance and loading.

Only official, public, aggregate CMS Provider Data Catalog datasets are used.
No credentials are needed. Raw files are written once and never modified.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

USER_AGENT = "uwmc-quality-signal-monitor (open-source; public CMS data)"
METASTORE_URL = (
    "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/{dataset_id}"
)
LANDING_URL = "https://data.cms.gov/provider-data/dataset/{dataset_id}"
ARCHIVE_URL = "https://data.cms.gov/provider-data/archived-data/hospitals"
MANIFEST_NAME = "manifest.json"
SYNTHETIC_MARKER = "SYNTHETIC_DATA"


@dataclass(frozen=True)
class Dataset:
    key: str
    dataset_id: str
    title: str
    filename: str
    # Other filenames CMS has used for the same table (e.g. inside archive zips).
    aliases: tuple[str, ...] = ()

    @property
    def landing_page(self) -> str:
        return LANDING_URL.format(dataset_id=self.dataset_id)

    @property
    def metastore_url(self) -> str:
        return METASTORE_URL.format(dataset_id=self.dataset_id)


DATASETS: dict[str, Dataset] = {
    d.key: d
    for d in (
        Dataset(
            "hcahps_hospital",
            "dgck-syfz",
            "Patient survey (HCAHPS) - Hospital",
            "hcahps_hospital.csv",
            ("HCAHPS-Hospital.csv", "HCAHPS_Hospital.csv"),
        ),
        Dataset(
            "hcahps_national",
            "99ue-w85f",
            "Patient survey (HCAHPS) - National",
            "hcahps_national.csv",
            ("HCAHPS-National.csv", "HCAHPS_National.csv"),
        ),
        Dataset(
            "hospital_general",
            "xubh-q36u",
            "Hospital General Information",
            "hospital_general.csv",
            ("Hospital_General_Information.csv", "Hospital General Information.csv"),
        ),
    )
}


class SourceError(RuntimeError):
    """Raised when a source cannot be retrieved or located."""


# ---------------------------------------------------------------- fetching


def _get(url: str, timeout: float = 60.0):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 (https only)


def fetch_metadata(dataset: Dataset) -> dict:
    """Read the dataset's metadata (title, dates, download URL) from the CMS metastore API."""
    try:
        with _get(dataset.metastore_url) as resp:
            meta = json.load(resp)
    except Exception as exc:  # network, DNS, HTTP and JSON errors alike
        raise SourceError(
            f"Could not read CMS metadata for {dataset.title} ({dataset.metastore_url}): {exc}.\n"
            f"Offline? Download the CSV manually from {dataset.landing_page} and save it as "
            f"<data-dir>/{dataset.filename}."
        ) from exc
    csv_urls = [
        d.get("downloadURL")
        for d in meta.get("distribution", [])
        if str(d.get("downloadURL", "")).lower().endswith(".csv")
    ]
    if not csv_urls:
        raise SourceError(
            f"CMS metadata for {dataset.dataset_id} lists no CSV distribution; "
            f"the schema may have changed. Check {dataset.landing_page}."
        )
    return {
        "title": meta.get("title"),
        "modified": meta.get("modified"),
        "issued": meta.get("issued"),
        "download_url": csv_urls[0],
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_release(raw_dir: Path) -> Path:
    """Download the current release of all three datasets into raw_dir/<release>/.

    The release label is the hospital HCAHPS dataset's CMS "modified" date. Existing
    files are never overwritten; a re-fetch of an unchanged release is a no-op.
    """
    metas = {key: fetch_metadata(ds) for key, ds in DATASETS.items()}
    label = str(metas["hcahps_hospital"].get("modified") or "unknown")[:10]
    release_dir = Path(raw_dir) / label
    release_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    for key, ds in DATASETS.items():
        meta = metas[key]
        target = release_dir / ds.filename
        if not target.exists():
            tmp = target.with_suffix(".part")
            try:
                with _get(meta["download_url"], timeout=600) as resp, tmp.open("wb") as fh:
                    shutil.copyfileobj(resp, fh)
            except Exception as exc:
                tmp.unlink(missing_ok=True)
                raise SourceError(f"Download failed for {meta['download_url']}: {exc}") from exc
            tmp.rename(target)
        entries.append(
            {
                "key": key,
                "dataset_id": ds.dataset_id,
                "title": meta.get("title") or ds.title,
                "landing_page": ds.landing_page,
                "metastore_url": ds.metastore_url,
                "download_url": meta["download_url"],
                "cms_modified": meta.get("modified"),
                "cms_issued": meta.get("issued"),
                "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "file": ds.filename,
                "sha256": _sha256(target),
                "bytes": target.stat().st_size,
            }
        )

    manifest_path = release_dir / MANIFEST_NAME
    if not manifest_path.exists():
        manifest_path.write_text(
            json.dumps({"release": label, "provenance": "cms_api", "datasets": entries}, indent=2)
        )
    return release_dir


# ---------------------------------------------------------------- locating & loading


def locate_files(release_dir: Path) -> dict[str, Path]:
    """Find the three CSVs in a release directory, accepting known CMS file names."""
    release_dir = Path(release_dir)
    if not release_dir.is_dir():
        raise SourceError(f"Data directory not found: {release_dir}")
    by_lower = {p.name.lower(): p for p in release_dir.iterdir() if p.is_file()}
    found, missing = {}, []
    for key, ds in DATASETS.items():
        for name in (ds.filename, *ds.aliases):
            if name.lower() in by_lower:
                found[key] = by_lower[name.lower()]
                break
        else:
            missing.append(f"{ds.filename} ({ds.title}: {ds.landing_page})")
    if missing:
        raise SourceError(
            f"Missing required file(s) in {release_dir}:\n  - " + "\n  - ".join(missing)
            + "\nRun `uwmc-monitor fetch`, or download each CSV manually (see data/README.md)."
        )
    return found


def read_provenance(release_dir: Path, files: dict[str, Path]) -> dict:
    """Describe where the release came from: CMS API manifest, synthetic fixture, or manual files."""
    release_dir = Path(release_dir)
    synthetic = (release_dir / SYNTHETIC_MARKER).exists()
    manifest_path = release_dir / MANIFEST_NAME
    if manifest_path.exists():
        prov = json.loads(manifest_path.read_text())
    else:
        prov = {
            "release": release_dir.name,
            "provenance": "manual",
            "datasets": [
                {
                    "key": key,
                    "dataset_id": DATASETS[key].dataset_id,
                    "title": DATASETS[key].title,
                    "landing_page": DATASETS[key].landing_page,
                    "file": path.name,
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                    "file_modified": datetime.fromtimestamp(
                        path.stat().st_mtime, UTC
                    ).isoformat(timespec="seconds"),
                }
                for key, path in files.items()
            ],
        }
    prov["synthetic"] = synthetic or bool(prov.get("synthetic"))
    if prov["synthetic"]:
        prov["provenance"] = "synthetic_fixture"
    prov["path"] = str(release_dir)
    return prov


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CMS CSV as text, untouched; normalization happens in validation."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")


def resolve_data_dir(data_root: Path) -> Path:
    """Use data_root itself if it holds the CSVs, else its newest raw/<release>/ folder."""
    data_root = Path(data_root)
    try:
        locate_files(data_root)
        return data_root
    except SourceError:
        pass
    raw = data_root / "raw"
    releases = sorted(p for p in raw.iterdir() if p.is_dir()) if raw.is_dir() else []
    if releases:
        return releases[-1]
    raise SourceError(
        f"No CMS files found in {data_root} or {raw}/<release>/. "
        "Run `uwmc-monitor fetch` or see data/README.md."
    )
