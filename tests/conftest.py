import dataclasses

import pytest

from youdata.config import load_settings
from youdata.seed import build_database


@pytest.fixture(scope="session")
def settings(tmp_path_factory):
    db = tmp_path_factory.mktemp("db") / "test.db"
    build_database(db)
    return dataclasses.replace(load_settings(), db_path=db)
