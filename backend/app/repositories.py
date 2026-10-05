from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import MIN_INTERVAL_KEY, Basin, BathReading, Filature, Setting, User


class UserRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()


class BasinRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def board(self) -> Filature | None:
        result = await self.session.execute(
            select(Filature).options(
                selectinload(Filature.basins).selectinload(Basin.readings)
            )
        )
        return result.scalars().first()

    async def get(self, basin_id: int) -> Basin | None:
        result = await self.session.execute(
            select(Basin)
            .options(selectinload(Basin.readings))
            .where(Basin.id == basin_id)
        )
        return result.scalar_one_or_none()

    async def add_reading(self, basin: Basin, temp_c: float, operator: str) -> BathReading:
        row = BathReading(basin=basin, water_temp_c=temp_c, operator=operator)
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return row

    async def save_status(self, basin: Basin, status: str) -> None:
        basin.status = status
        await self.session.commit()


class SettingsRepo:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def min_interval_raw(self) -> str | None:
        row = await self.session.get(Setting, MIN_INTERVAL_KEY)
        return row.value if row else None

    async def save_min_interval(self, minutes: int) -> None:
        row = await self.session.get(Setting, MIN_INTERVAL_KEY)
        if row is None:
            row = Setting(key=MIN_INTERVAL_KEY, value=str(minutes))
            self.session.add(row)
        else:
            row.value = str(minutes)
        await self.session.commit()
