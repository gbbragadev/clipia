from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job, User
from app.errors import not_found_error, validate_uuid


async def get_owned_job(db: AsyncSession, user: User, job_id: str) -> Job:
    parsed_job_id = validate_uuid(job_id)
    result = await db.execute(select(Job).where(Job.id == parsed_job_id, Job.user_id == user.id))
    job = result.scalar_one_or_none()
    if job is None:
        raise not_found_error()
    return job
