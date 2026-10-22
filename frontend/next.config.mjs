/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // 04D: the real-stack journey builds with a different NEXT_PUBLIC_API_BASE_URL into its OWN directory so it never overwrites the default build the mocked suite uses.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  // The frontend is a pure client of the FastAPI backend; no server secrets here.
  env: {},
  // 03A: platform-wide Review and Diagnostics moved under /admin. The old URLs keep working (bookmarks, the Command Center's server-provided links).
  // The redirect grants nothing: the destination page and every API call it makes are authorised again, so a Candidate lands on the access-denied state.
  // `/review/agent` (the Candidate's own, owner-scoped run details) is deliberately NOT redirected.
  async redirects() {
    return [
      { source: "/review", destination: "/admin/review", permanent: false },
      { source: "/review/rag", destination: "/admin/review/rag", permanent: false },
      { source: "/review/evaluation", destination: "/admin/review/evaluation", permanent: false },
    ];
  },
};

export default nextConfig;
