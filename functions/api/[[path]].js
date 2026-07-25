export async function onRequest({ env, request }) {
  if (!env.API_WORKER) {
    return Response.json(
      { error: "API Worker binding is not configured" },
      { status: 500 },
    );
  }

  return env.API_WORKER.fetch(request);
}
