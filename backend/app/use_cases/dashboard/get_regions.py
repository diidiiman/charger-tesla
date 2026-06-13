from app.schemas import RegionInfo
from app import prices


class GetRegionsUseCase:
    async def call(self) -> list[RegionInfo]:
        return [RegionInfo(**r) for r in prices.list_regions()]
