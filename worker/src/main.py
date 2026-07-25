from workers import WorkerEntrypoint

from routes import route_request


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        return await route_request(request, self.env)
