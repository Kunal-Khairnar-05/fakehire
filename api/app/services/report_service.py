"""Business rules for scam reports.

- You can only report a check that is YOURS (otherwise it looks like it doesn't exist).
- One report per check per user (enforced by the database's UNIQUE constraint).
- Only PENDING reports can be reviewed, and two moderators can't review the same one.
"""
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Check, Report
from ..repositories.report_repo import ReportRepository


class CheckNotFound(Exception):
    pass


class AlreadyReported(Exception):
    pass


class ReportNotFound(Exception):
    pass


class AlreadyReviewed(Exception):
    pass


class ReportService:
    def __init__(self, session: Session):
        self.session = session
        self.reports = ReportRepository(session)

    def report(self, user_id: int, check_id: int, company_name: str, reason: str | None) -> Report:
        check = self.session.get(Check, check_id)
        # Someone else's check gets the SAME answer as a missing one: no hint that it exists
        if check is None or check.user_id != user_id:
            raise CheckNotFound()
        try:
            report = self.reports.add(check_id=check_id, reporter_id=user_id,
                                      company_name=company_name, reason=reason or None)
            self.session.commit()
            return report
        except IntegrityError:
            self.session.rollback()
            raise AlreadyReported()

    def queue(self, limit: int, after: datetime | None) -> tuple[list[tuple[Report, Check]], datetime | None]:
        rows = self.reports.pending_queue(limit, after)
        next_after = rows[-1][0].created_at if len(rows) == limit else None
        return rows, next_after

    def review(self, moderator_id: int, report_id: int, decision: str) -> Report:
        report = self.reports.get_for_update(report_id)    # row is locked from here until commit
        if report is None:
            self.session.rollback()
            raise ReportNotFound()
        if report.status != "pending":
            self.session.rollback()
            raise AlreadyReviewed()
        report.status = decision
        report.reviewed_by = moderator_id
        report.reviewed_at = datetime.now(timezone.utc)
        self.session.commit()
        return report

    def mine(self, user_id: int, limit: int) -> list[Report]:
        return self.reports.list_for_reporter(user_id, limit)
