/**
 * Cloudflare Workers Builds deploy helper.
 *
 * Workers Builds secrets are build-time only. This helper explicitly uploads
 * MCP_AUTH_TOKEN as a Worker runtime secret with Wrangler's --secrets-file.
 * The temporary file is created outside the repository and always removed.
 */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { chmodSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const token = process.env.MCP_AUTH_TOKEN;

if (typeof token !== "string" || token.length < 32) {
  console.error(
    "Deploy stopped: set a Workers Builds Secret named MCP_AUTH_TOKEN with at least 32 characters."
  );
  process.exit(1);
}

const secretsFile = join(tmpdir(), `bedrock-worker-secrets-${randomUUID()}.json`);

try {
  writeFileSync(secretsFile, JSON.stringify({ MCP_AUTH_TOKEN: token }), {
    encoding: "utf8",
    mode: 0o600,
    flag: "wx",
  });
  chmodSync(secretsFile, 0o600);

  console.log("Deploying Worker and attaching MCP_AUTH_TOKEN as a runtime secret...");
  execFileSync(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["wrangler", "deploy", "--secrets-file", secretsFile],
    { stdio: "inherit", env: process.env }
  );
  console.log("Worker deployment completed. Runtime secret was supplied without printing its value.");
} catch (error) {
  console.error("Worker deployment failed. Check the Wrangler output above.");
  process.exitCode = 1;
} finally {
  try {
    rmSync(secretsFile, { force: true });
  } catch {
    console.error("Warning: temporary secrets file could not be removed automatically.");
  }
}
