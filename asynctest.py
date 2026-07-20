import asyncio

from xsense import AsyncXSense
from xsense.utils import dump_environment, get_credentials


async def run(username: str, password: str):
    async with AsyncXSense() as api:
        await api.init()
        await api.login(username, password)
        await api.load_all()

        for h in api.houses.values():
            await api.get_house_state(h)
            for s in h.stations.values():
                await api.get_station_state(s)
                await api.get_state(s)

                if s.has_alarm:
                    await api.get_alarm_state(s)

        dump_environment(api)


if __name__ == "__main__":
    username, password = get_credentials()
    asyncio.run(run(username, password))
