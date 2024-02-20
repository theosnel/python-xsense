import asyncio

from xsense.async_xsense import AsyncXSense
from xsense.utils import dump_environment, get_credentials


async def run(username: str, password: str):
    api = AsyncXSense()
    await api.init()
    await api.login(username, password)
    await api.load_all()

    for _, h in api.houses.items():
        for _, s in h.stations.items():
            await api.get_state(s)

    dump_environment(api)


username, password = get_credentials()
asyncio.run(run(username, password))
