from __future__ import annotations

import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import eval_prompt  # noqa: E402
import tag_companies  # noqa: E402


def test_frozen_200_sample_is_refused_even_when_renamed(tmp_path):
    with pytest.raises(SystemExit, match="Refusing to evaluate on the frozen 200"):
        eval_prompt.refuse_frozen_sample(eval_prompt.FROZEN_SAMPLE_FILE)

    renamed = tmp_path / "innocent-looking-devset.csv"
    shutil.copyfile(eval_prompt.FROZEN_SAMPLE_FILE, renamed)
    sample, _stats = tag_companies.load_sample(renamed)

    with pytest.raises(SystemExit, match="Refusing to evaluate on the frozen 200"):
        eval_prompt.validate_inputs(renamed, sample, labels={})
