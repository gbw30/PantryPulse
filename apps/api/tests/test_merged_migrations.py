"""The worker and operational histories must remain reachable from one head."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_merged_head_preserves_both_preexisting_histories():
    root = Path(__file__).resolve().parents[1]
    scripts = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    assert scripts.get_heads() == ["ppor_0005"]
    assert scripts.get_revision("ppor_0005").down_revision == "pp45_0004"
    assert scripts.get_revision("pp45_0004").down_revision == "pp_merge_0003"
    merge = scripts.get_revision("pp_merge_0003")
    assert set(merge.down_revision) == {"0001_jobs_foundation", "pp21_0002"}
    assert scripts.get_revision("pp19_0001").down_revision is None
    assert scripts.get_revision("0001_jobs_foundation").down_revision is None
