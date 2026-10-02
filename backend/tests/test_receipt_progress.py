"""Tests fuer den Fortschritt (Meilensteine + Zeitschaetzung) der Bon-Scans.

Ausfuehren (im backend-Ordner; braucht fastapi + sqlalchemy, nutzt SQLite):

    python -m unittest discover -s tests -v
"""

import asyncio
import os
import sys
import tempfile
import unittest

_DB_DIR = tempfile.mkdtemp(prefix="yousplit-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_DIR}/test.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import models  # noqa: E402
import receipt_jobs  # noqa: E402
import schemas  # noqa: E402
from database import Base, SessionLocal, engine  # noqa: E402
from routers import lists  # noqa: E402


class AnalysisEstimateTest(unittest.TestCase):
    def setUp(self) -> None:
        receipt_jobs._analysis_seconds = receipt_jobs.DEFAULT_ANALYSIS_SECONDS

    def test_startwert(self) -> None:
        self.assertEqual(receipt_jobs.expected_analysis_seconds(), 60)

    def test_gleitender_durchschnitt_naehert_sich_den_echten_zeiten(self) -> None:
        receipt_jobs.record_analysis_duration(20)
        self.assertEqual(receipt_jobs.expected_analysis_seconds(), 40)  # (20+60)/2
        receipt_jobs.record_analysis_duration(20)
        self.assertEqual(receipt_jobs.expected_analysis_seconds(), 30)  # (20+40)/2

    def test_unsinnige_werte_werden_ignoriert_und_minimum_gilt(self) -> None:
        receipt_jobs.record_analysis_duration(0)
        receipt_jobs.record_analysis_duration(-3)
        self.assertEqual(receipt_jobs.expected_analysis_seconds(), 60)
        for _ in range(20):
            receipt_jobs.record_analysis_duration(0.1)
        self.assertEqual(receipt_jobs.expected_analysis_seconds(), 5)


class ScanProgressTest(unittest.TestCase):
    def setUp(self) -> None:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.db = SessionLocal()
        shared = models.SharedList(title="Test")
        self.db.add(shared)
        self.db.commit()
        self.list_id = shared.id

        self._orig = (
            lists.analyze_receipt,
            lists.is_model_available,
            lists.get_exchange_rate,
            receipt_jobs.set_progress,
        )
        self.progress_calls: list[int] = []

        async def fake_analyze(_: bytes) -> schemas.ReceiptAnalysis:
            return schemas.ReceiptAnalysis(
                title="REWE",
                amount=24.50,
                date="2026-08-12",
                category="Lebensmittel",
                currency="EUR",
            )

        async def fake_available() -> bool:
            return True

        async def fake_rate(_: str) -> float:
            return 1.0

        original_set_progress = receipt_jobs.set_progress

        def recording_set_progress(job_id, progress):  # type: ignore[no-untyped-def]
            self.progress_calls.append(progress)
            original_set_progress(job_id, progress)

        lists.analyze_receipt = fake_analyze
        lists.is_model_available = fake_available
        lists.get_exchange_rate = fake_rate
        receipt_jobs.set_progress = recording_set_progress

    def tearDown(self) -> None:
        (
            lists.analyze_receipt,
            lists.is_model_available,
            lists.get_exchange_rate,
            receipt_jobs.set_progress,
        ) = self._orig
        self.db.close()

    def new_job(self) -> models.ReceiptJob:
        job = models.ReceiptJob(
            list_id=self.list_id,
            payer_name="Kev",
            status=receipt_jobs.STATUS_PROCESSING,
            progress=receipt_jobs.PROGRESS_ACCEPTED,
        )
        self.db.add(job)
        self.db.commit()
        return job

    def run_scan(self, job: models.ReceiptJob) -> models.ReceiptJob:
        asyncio.run(
            lists._process_receipt_in_background(
                job.id, self.list_id, "Kev", b"bild"
            )
        )
        self.db.expire_all()
        return self.db.get(models.ReceiptJob, job.id)

    def test_meilensteine_steigen_und_enden_bei_100(self) -> None:
        job = self.run_scan(self.new_job())
        self.assertEqual(
            self.progress_calls,
            [
                receipt_jobs.PROGRESS_ANALYZING,
                receipt_jobs.PROGRESS_ANALYZED,
                receipt_jobs.PROGRESS_CHECKED,
                receipt_jobs.PROGRESS_SAVING,
            ],
        )
        self.assertEqual(self.progress_calls, sorted(self.progress_calls))
        self.assertEqual(job.status, receipt_jobs.STATUS_DONE)
        self.assertEqual(job.progress, 100)

    def test_duplikat_stoppt_vor_dem_speichern(self) -> None:
        self.run_scan(self.new_job())  # legt den Bon an
        self.progress_calls.clear()
        job = self.run_scan(self.new_job())  # derselbe Bon noch einmal
        self.assertEqual(job.status, receipt_jobs.STATUS_DUPLICATE)
        self.assertNotIn(receipt_jobs.PROGRESS_SAVING, self.progress_calls)

    def test_liste_liefert_fortschritt_und_schaetzung(self) -> None:
        receipt_jobs._analysis_seconds = receipt_jobs.DEFAULT_ANALYSIS_SECONDS
        self.new_job()
        jobs = lists.list_receipt_jobs(self.list_id, db=self.db)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].progress, receipt_jobs.PROGRESS_ACCEPTED)
        self.assertEqual(jobs[0].estimated_seconds, 60)


if __name__ == "__main__":
    unittest.main()
