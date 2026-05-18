import path from "node:path";

// Production safety guard: NEXT_PUBLIC_DEV_ADMIN_TOKEN must never be set in a
// production build. It is a dev-only escape hatch for local direct-backend access.
// In production, Caddy injects Authorization server-side via header_up.
if (
  process.env.NODE_ENV === "production" &&
  process.env.NEXT_PUBLIC_DEV_ADMIN_TOKEN
) {
  throw new Error(
    "[SECURITY] NEXT_PUBLIC_DEV_ADMIN_TOKEN is set in a production build. " +
    "This variable is dev-only and must never appear in a production environment. " +
    "Remove it from your .env before building for production."
  );
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  outputFileTracingRoot: path.join(process.cwd()),
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || "",
};

export default nextConfig;
