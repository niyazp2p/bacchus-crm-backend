from arq import create_pool
from arq.connections import RedisSettings, ArqRedis
from app.core.config import settings

_redis_pool: ArqRedis | None = None

async def get_redis_pool() -> ArqRedis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await create_pool(
            RedisSettings(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                database=settings.REDIS_DB,
            )
        )
    return _redis_pool

async def enqueue_background_task(function_name: str, *args, **kwargs):
    pool = await get_redis_pool()
    return await pool.enqueue_job(function_name, *args, **kwargs)