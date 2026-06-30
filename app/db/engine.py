from sqlalchemy.engine.url import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings


def build_engine(database_url: str) -> AsyncEngine:
    url = make_url(database_url)
    kwargs = {"echo": False}

    if not url.drivername.startswith("sqlite"):
        kwargs.update(
            {
                "pool_pre_ping": True,
                "pool_size": 10,
                "max_overflow": 20,
                "pool_timeout": 30,
                "pool_recycle": 1800,
            }
        )

    return create_async_engine(database_url, **kwargs)


# Engine principal (FastAPI): roda num event loop persistente -> pool de conexoes ajuda.
engine = build_engine(settings.DATABASE_URL)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def build_worker_engine(database_url: str) -> AsyncEngine:
    """Engine para o worker Celery, que roda asyncio.run() (loop NOVO) por task.

    Conexoes asyncpg ficam presas ao loop que as criou; reusar do pool num loop posterior
    estoura 'RuntimeError: Event loop is closed'. NullPool abre conexao fresca por sessao,
    eliminando o cross-loop. (Em SQLite/testes tambem e seguro.)
    """
    return create_async_engine(database_url, echo=False, poolclass=NullPool)


# Engine do worker: usar nas tasks Celery (refund, finalize/save_script, cleanups).
worker_engine = build_worker_engine(settings.DATABASE_URL)
worker_session = async_sessionmaker(worker_engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
