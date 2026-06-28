"""Overrides de geracao por job (SFX/musica) guardados no hash Redis do job.

Os workers e o endpoint /composition leem essas flags do mesmo hash onde mora o
template_id, para decidir POR-VIDEO o que antes so existia global em settings.
"""


def resolve_job_flag(redis_client, job_id: str, key: str, default: bool) -> bool:
    """Le um override booleano por-job ("1"/"0") do hash Redis; cai no default se ausente."""
    raw = redis_client.hget(f"job:{job_id}", key)
    if isinstance(raw, bytes):
        raw = raw.decode()
    if raw == "1":
        return True
    if raw == "0":
        return False
    return default
