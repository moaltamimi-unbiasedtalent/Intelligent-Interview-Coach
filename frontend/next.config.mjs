/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // The frontend is a pure client of the FastAPI backend; no server secrets here.
  env: {},
};

export default nextConfig;
