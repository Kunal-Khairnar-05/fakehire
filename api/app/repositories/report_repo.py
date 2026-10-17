"""Repository for the reports table."""
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Check, Report


class ReportRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, **fields) -> Report:
        report = Report(**fields)
        self.session.add(report)
        self.session.flush()
        return report

    def get_for_update(self, report_id: int) -> Report | None:
        """SELECT ... FOR UPDATE locks this row until the transaction ends.
        If two moderators click at the same moment, the second waits, then sees the
        report is no longer pending, instead of both 'reviewing' it."""
        return self.session.scalar(select(Report).where(Report.id == report_id).with_for_update())

    def pending_queue(self, limit: int, after: datetime | None) -> list[tuple[Report, Check]]:
        """Oldest pending first, with the checked posting. Served by the partial index."""
        query = (select(Report, Check)
                 .join(Check, Check.id == Report.check_id)
                 .where(Report.status == "pending"))
        if after is not None:
            query = query.where(Report.created_at > after)
        query = query.order_by(Report.created_at).limit(limit)
        return [(row.Report, row.Check) for row in self.session.execute(query)]

    def list_for_reporter(self, reporter_id: int, limit: int) -> list[Report]:
        query = (select(Report).where(Report.reporter_id == reporter_id)
                 .order_by(Report.created_at.desc()).limit(limit))
        return list(self.session.scalars(query))
