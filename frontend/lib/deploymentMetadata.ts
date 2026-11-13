const UNKNOWN = "unknown";
const SAFE_METADATA_VALUE = /[^A-Za-z0-9._:+,/ -]/g;

export const DEPLOYMENT_META_NAMES = {
  commit: "ask4mo:deploy:commit",
  timestamp: "ask4mo:deploy:timestamp",
  tags: "ask4mo:deploy:tags",
} as const;

function deploymentToken(name: string, limit: number): string {
  const raw = (process.env[name] ?? "").trim();
  const safe = raw.replace(SAFE_METADATA_VALUE, "").slice(0, limit).trim();
  return safe || UNKNOWN;
}

export function deploymentMetadata(): Record<string, string> {
  return {
    [DEPLOYMENT_META_NAMES.commit]: deploymentToken("APP_GIT_SHA", 64),
    [DEPLOYMENT_META_NAMES.timestamp]: deploymentToken("APP_BUILD_TIME", 40),
    [DEPLOYMENT_META_NAMES.tags]: deploymentToken("APP_DEPLOY_TAGS", 256),
  };
}
