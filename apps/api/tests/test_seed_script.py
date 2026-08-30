"""Regression test for a real bug: a database seeded by the Milestone 1/2
version of seed.py already has the 20 demo risks. Milestone 3 added
controls/actions seeding, but nested it inside a function that bailed out
entirely once any risk existed — so upgrading and re-running seed.py left
the new tables empty, invisible until a live check on a persisted database
surfaced it. seed_demo_risks must backfill controls/actions for
already-existing risks, not just on a fully empty database.
"""

from sqlalchemy import select

from database.seed.seed import seed_demo_risks
from packages.shared.models.action import Action
from packages.shared.models.control import Control, RiskControl
from packages.shared.models.risk import Risk


class TestSeedBackfill:
    def test_first_run_creates_risks_controls_and_actions(self, db_session, seeded):
        created = seed_demo_risks(db_session)
        db_session.commit()

        assert created == 20
        assert db_session.scalar(select(Risk).limit(1)) is not None
        assert len(db_session.scalars(select(Control)).all()) == 6
        assert len(db_session.scalars(select(Action)).all()) == 20

    def test_rerun_against_risks_that_already_exist_backfills_controls_and_actions(
        self, db_session, seeded
    ):
        """Simulates exactly what happened on a database carried over from
        Milestone 1/2: risks exist, controls/actions tables are empty."""
        first_pass_created = seed_demo_risks(db_session)
        db_session.commit()
        assert first_pass_created == 20

        # Wipe controls/actions only, as if this were a pre-Milestone-3 database.
        db_session.query(RiskControl).delete()
        db_session.query(Control).delete()
        db_session.query(Action).delete()
        db_session.commit()

        second_pass_created = seed_demo_risks(db_session)
        db_session.commit()

        assert second_pass_created == 0, "must not create duplicate risks"
        assert len(db_session.scalars(select(Control)).all()) == 6
        assert len(db_session.scalars(select(Action)).all()) == 20
        assert len(db_session.scalars(select(RiskControl)).all()) > 0

    def test_rerun_is_fully_idempotent_when_everything_already_seeded(self, db_session, seeded):
        seed_demo_risks(db_session)
        db_session.commit()

        seed_demo_risks(db_session)
        db_session.commit()

        assert len(db_session.scalars(select(Risk)).all()) == 20
        assert len(db_session.scalars(select(Control)).all()) == 6
        assert len(db_session.scalars(select(Action)).all()) == 20
