from pathlib import Path

REQUIRED = [
    "docs/OBSERVABILITY_GUIDELINES.md",
    "docs/RELEASE_TRAIN.md",
    "docs/MULTI_TENANT_GUIDELINES.md",
    "ops/release_checklist.md",
]

def test_release_readiness_files_exist():
    for item in REQUIRED:
        assert Path(item).exists(), item
