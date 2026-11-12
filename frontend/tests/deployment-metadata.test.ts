import { afterEach, describe, expect, it } from "vitest";
import { DEPLOYMENT_META_NAMES, deploymentMetadata } from "@/lib/deploymentMetadata";

const KEYS = ["APP_GIT_SHA", "APP_BUILD_TIME", "APP_DEPLOY_TAGS"] as const;

afterEach(() => {
  for (const key of KEYS) delete process.env[key];
});

describe("deployment metadata", () => {
  it("reports unknown when the container did not inject provenance", () => {
    expect(deploymentMetadata()).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "unknown",
      [DEPLOYMENT_META_NAMES.timestamp]: "unknown",
      [DEPLOYMENT_META_NAMES.tags]: "unknown",
    });
  });

  it("exposes the injected commit, timestamp and tags", () => {
    process.env.APP_GIT_SHA = "  00f7ddfba454f3daa946d867d6e131220bb0dc69  ";
    process.env.APP_BUILD_TIME = "2026-11-12T18:40:00Z";
    process.env.APP_DEPLOY_TAGS = 'branch:dockerize,git:v1.0.0,image:ask4mo-local-web';
    expect(deploymentMetadata()).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "00f7ddfba454f3daa946d867d6e131220bb0dc69",
      [DEPLOYMENT_META_NAMES.timestamp]: "2026-11-12T18:40:00Z",
      [DEPLOYMENT_META_NAMES.tags]: "branch:dockerize,git:v1.0.0,image:ask4mo-local-web",
    });
  });

  it("strips unsafe characters before they reach an HTML meta tag", () => {
    process.env.APP_GIT_SHA = "<script>alert(1)</script>";
    process.env.APP_BUILD_TIME = "2026-11-12T18:40:00Z";
    process.env.APP_DEPLOY_TAGS = 'branch:dockerize,"unsafe"<tag>';
    expect(deploymentMetadata()).toEqual({
      [DEPLOYMENT_META_NAMES.commit]: "scriptalert1/script",
      [DEPLOYMENT_META_NAMES.timestamp]: "2026-11-12T18:40:00Z",
      [DEPLOYMENT_META_NAMES.tags]: "branch:dockerize,unsafetag",
    });
  });
});
