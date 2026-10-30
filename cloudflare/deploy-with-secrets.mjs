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
const backendUrl = process.env.MCP_BACKEND_URL;
const backendToken = process.env.MCP_BACKEND_TOKEN;

if (typeof token !== "string" || token.length < 32) {
  console.error("Deploy stopped: MCP_AUTH_TOKEN must be at least 32 characters.");
  process.exit(1);
}
if (typeof backendUrl !== "string" || !backendUrl.startsWith("https://") || typeof backendToken !== "string" || backendToken.length < 32) {
  console.error("Deploy stopped: configure HTTPS MCP_BACKEND_URL and MCP_BACKEND_TOKEN (at least 32 characters) for the unified Python backend.");
  process.exit(1);
}

const secretsFile = join(tmpdir(), `bedrock-worker-secrets-${randomUUID()}.json`);

try {
  writeFileSync(secretsFile, JSON.stringify({ MCP_AUTH_TOKEN: token, MCP_BACKEND_URL: backendUrl, MCP_BACKEND_TOKEN: backendToken }), {
    encoding: "utf8",
    mode: 0o600,
    flag: "wx",
  });
  chmodSync(secretsFile, 0o600);

  console.log("Deploying Worker and attaching MCP gateway and backend credentials as runtime secrets...");
  execFileSync(
    process.platform === "win32" ? "npx.cmd" : "npx",
    ["wrangler", "deploy", "--secrets-file", secretsFile],
    { stdio: "inherit", env: process.env }
  );
  console.log("Worker deployment completed. Runtime secrets were supplied without printing their values.");
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
