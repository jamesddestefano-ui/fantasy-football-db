import pytest
from sqlalchemy.orm import Session

from ffdb.db import make_engine
from ffdb.models import Base
from ffdb.seed import seed_mongo
from ffdb.sparta_seed import seed_sparta


@pytest.fixture()
def session(tmp_path):
    engine = make_engine(tmp_path / "test.db")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        with s.begin():
            seed_mongo(s)
            seed_sparta(s)
        yield s
