from fastapi import APIRouter, Form, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlmodel import func, select

from app.core.deps import CurrentUserDep, DbDep, SettingsDep
from app.core.exceptions import FileTooLargeError, NotFoundError, RateLimitedError, ValidationError
from app.core.limiter import get_limiter
from app.db.models import Report
from app.schemas.common import Paginated
from app.schemas.report import ReportOut, ReportSummaryOut
from app.services import pdf
from app.services.analysis import run_analysis

router = APIRouter(prefix="/interview", tags=["interview"])

JD_MIN_LENGTH = 50
JD_MAX_LENGTH = 20_000
SELF_MAX_LENGTH = 2_000


def _get_owned_report(db, report_id: str, user_id: str) -> Report:
    report = db.get(Report, report_id)
    # A foreign or missing id returns 404, never 403: 403 would confirm the
    # id exists, which leaks information. See CLAUDE.md.
    if report is None or report.user_id != user_id:
        raise NotFoundError("Report not found.")
    return report


@router.post("/", response_model=ReportOut, status_code=201)
async def create_report(
    db: DbDep,
    settings: SettingsDep,
    user: CurrentUserDep,
    resume: UploadFile,
    job_description: str = Form(...),
    self_description: str = Form(""),
) -> ReportOut:
    if not (JD_MIN_LENGTH <= len(job_description) <= JD_MAX_LENGTH):
        raise ValidationError(
            f"Job description must be {JD_MIN_LENGTH} to {JD_MAX_LENGTH} characters.",
            fields={"job_description": "invalid length"},
        )
    if len(self_description) > SELF_MAX_LENGTH:
        raise ValidationError(
            f"Self description must be under {SELF_MAX_LENGTH} characters.",
            fields={"self_description": "too long"},
        )

    # Read one byte past the limit instead of the whole upload: a 500 MB
    # file would otherwise be held in memory on a 512 MB instance before the
    # size check ever ran.
    resume_bytes = await resume.read(settings.max_upload_bytes + 1)
    if len(resume_bytes) > settings.max_upload_bytes:
        raise FileTooLargeError()

    limiter = get_limiter(settings.analyses_per_hour, settings.analyses_per_day)
    if not limiter.acquire(user.id):
        raise RateLimitedError()

    try:
        result = await run_in_threadpool(
            run_analysis, resume_bytes, job_description, self_description, settings
        )
    except Exception:
        limiter.release(user.id)
        raise

    report = Report(
        user_id=user.id,
        title=result.report.title,
        job_description=job_description,
        self_description=self_description,
        resume_text=result.resume_text,
        match_score=result.report.match_score,
        scored_against=result.scored_against.value,
        role_title=result.role_title,
        skill_gaps=[g.model_dump(mode="json") for g in result.report.skill_gaps],
        technical_qs=[q.model_dump(mode="json") for q in result.report.technical_qs],
        behavioral_qs=[q.model_dump(mode="json") for q in result.report.behavioral_qs],
        preparation_plan=[p.model_dump(mode="json") for p in result.report.preparation_plan],
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # Inline, not in the threadpool: the request's session is not thread-safe
    # and the query is one indexed select.
    _prune_old_reports(db, user.id, settings.max_reports_per_user)

    return ReportOut.model_validate(report, from_attributes=True)


def _prune_old_reports(db, user_id: str, keep: int) -> None:
    """Reports beyond `keep` per user, oldest first, are deleted. Runs after
    every create so the table never grows without bound."""
    ids = db.exec(
        select(Report.id)
        .where(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .offset(keep)
    ).all()
    if not ids:
        return
    for report_id in ids:
        db.delete(db.get(Report, report_id))
    db.commit()


@router.get("/", response_model=Paginated[ReportSummaryOut])
def list_reports(
    db: DbDep, user: CurrentUserDep, limit: int = Query(20, le=100), offset: int = Query(0, ge=0)
) -> Paginated:
    total = db.exec(select(func.count()).select_from(Report).where(Report.user_id == user.id)).one()
    rows = db.exec(
        select(Report)
        .where(Report.user_id == user.id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    items = [ReportSummaryOut.model_validate(r, from_attributes=True) for r in rows]
    return Paginated(items=items, total=total)


@router.get("/{report_id}", response_model=ReportOut)
def get_report(db: DbDep, user: CurrentUserDep, report_id: str) -> ReportOut:
    report = _get_owned_report(db, report_id, user.id)
    return ReportOut.model_validate(report, from_attributes=True)


@router.delete("/{report_id}", status_code=204)
def delete_report(db: DbDep, user: CurrentUserDep, report_id: str) -> None:
    report = _get_owned_report(db, report_id, user.id)
    db.delete(report)
    db.commit()


@router.post("/{report_id}/pdf")
async def export_pdf(db: DbDep, user: CurrentUserDep, report_id: str) -> StreamingResponse:
    report = _get_owned_report(db, report_id, user.id)
    report_out = ReportOut.model_validate(report, from_attributes=True)
    pdf_bytes = await run_in_threadpool(pdf.render_report_pdf, report_out.model_dump(mode="json"))
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{report_id}.pdf"'},
    )
