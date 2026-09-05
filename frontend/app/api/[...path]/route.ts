import { NextRequest } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

const BACKEND_API_BASE = process.env.BACKEND_API_BASE ?? "http://127.0.0.1:8010";

const proxyRequest = async (request: NextRequest, path: string[]) => {
  const target = new URL(`/api/${path.join("/")}`, BACKEND_API_BASE);
  target.search = request.nextUrl.search;

  const isBodyless = request.method === "GET" || request.method === "HEAD";
  const response = await fetch(target, {
    method: request.method,
    headers: {
      "content-type": request.headers.get("content-type") ?? "application/json",
    },
    body: isBodyless ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    redirect: "manual",
  });

  const headers = new Headers();
  headers.set("content-type", response.headers.get("content-type") ?? "application/json");
  const location = response.headers.get("location");
  if (location) {
    const dest = new URL(location, request.nextUrl.origin);
    headers.set("location", `${dest.pathname}${dest.search}`);
  }

  return new Response(response.body, {
    status: response.status,
    headers,
  });
};

export const GET = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const POST = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const DELETE = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));
