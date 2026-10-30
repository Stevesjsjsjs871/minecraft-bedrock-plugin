/**
 * Minecraft Bedrock Engineer — Cloudflare Workers Free gateway.
 * Stateless Streamable HTTP MCP endpoint; no Containers or Durable Objects.
 */
interface Env {
  MCP_AUTH_TOKEN: string;
  GITHUB_BRANCH?: string;
}
type Rpc = { jsonrpc?: string; id?: string | number | null; method?: string; params?: Record<string, unknown> };
const REPO = "Stevesjsjsjs871/minecraft-bedrock-plugin";
const DEFAULT_BRANCH = "feat/cloudflare-workers-mcp";
const MAX_BODY = 1024 * 1024;

const tools = [
  { name: "bedrock_generate_manifest", description: "Generate a valid Minecraft Bedrock BP or RP manifest (format_version 2) with fresh UUIDs. Returns JSON; does not write files.", inputSchema: { type: "object", properties: { pack_type: { type: "string", enum: ["behavior", "resource"] }, name: { type: "string", minLength: 1, maxLength: 64 }, description: { type: "string", minLength: 1, maxLength: 256 }, min_engine_version: { type: "array", items: { type: "integer", minimum: 0 }, minItems: 3, maxItems: 3 }, version: { type: "array", items: { type: "integer", minimum: 0 }, minItems: 3, maxItems: 3 }, dependency_uuid: { type: "string", description: "Optional BP header UUID for an RP dependency." }, dependency_version: { type: "array", items: { type: "integer", minimum: 0 }, minItems: 3, maxItems: 3 } }, required: ["pack_type", "name", "description", "min_engine_version"], additionalProperties: false } },
  { name: "bedrock_validate_manifest", description: "Statically validate a Minecraft Bedrock manifest JSON object: format version, header, UUIDs, versions, module types and dependencies.", inputSchema: { type: "object", properties: { manifest: { type: "object" } }, required: ["manifest"], additionalProperties: false } },
  { name: "bedrock_read_plugin_source", description: "Read a text source/reference file from the public Minecraft Bedrock Engineer GitHub repository. Only paths under server/ or skills/ are allowed; no arbitrary URLs.", inputSchema: { type: "object", properties: { path: { type: "string", minLength: 1, maxLength: 240 } }, required: ["path"], additionalProperties: false } },
  { name: "bedrock_plugin_capabilities", description: "List the Python MCP modules preserved in the full local plugin and explain which runtime currently powers this free remote Worker gateway.", inputSchema: { type: "object", properties: {}, additionalProperties: false } }
] as const;

const modules = [
  "mcp_server", "texture_generator_mcp", "texture_link_audit_mcp", "entity_authoring_mcp",
  "animation_controller_mcp", "animation_clip_mcp", "animation_pipeline_audit_mcp",
  "animated_entity_bundle_mcp", "geometry_uv_audit_mcp", "geometry_uv_template_mcp",
  "texture_painting_mcp", "reference_texture_transfer_mcp", "uv_mapping_assistant_mcp",
  "visual_reference_analyzer_mcp", "reference_mapping_review_mcp", "uv_texture_retarget_mcp"
];

function response(body: unknown, status = 200, extra: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra } });
}
function rpcError(id: Rpc["id"], code: number, message: string) {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message } };
}
function validUuid(v: unknown): v is string {
  return typeof v === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(v);
}
function validVersion(v: unknown): v is number[] {
  return Array.isArray(v) && v.length === 3 && v.every(x => Number.isInteger(x) && x >= 0);
}
function toolResult(value: unknown, isError = false) {
  const text = JSON.stringify(value, null, 2);
  return { content: [{ type: "text", text }], structuredContent: value, isError };
}
async function callTool(name: string, args: Record<string, unknown>, env: Env): Promise<{ value: unknown; isError?: boolean }> {
  if (name === "bedrock_generate_manifest") {
    const type = args.pack_type;
    if (type !== "behavior" && type !== "resource") throw new Error("pack_type must be behavior or resource");
    const nameValue = args.name, desc = args.description, min = args.min_engine_version;
    if (typeof nameValue !== "string" || !nameValue.trim() || typeof desc !== "string" || !desc.trim() || !validVersion(min)) throw new Error("Invalid name, description or min_engine_version");
    const version = args.version === undefined ? [1, 0, 0] : args.version;
    if (!validVersion(version)) throw new Error("version must contain three non-negative integers");
    const headerUuid = crypto.randomUUID(), moduleUuid = crypto.randomUUID();
    const manifest: Record<string, unknown> = {
      format_version: 2,
      header: { name: nameValue.trim(), description: desc.trim(), uuid: headerUuid, version, min_engine_version: min },
      modules: [{ type: type === "behavior" ? "data" : "resources", uuid: moduleUuid, version }]
    };
    if (type === "resource" && args.dependency_uuid !== undefined) {
      if (!validUuid(args.dependency_uuid)) throw new Error("dependency_uuid is not a valid UUID");
      const depVersion = args.dependency_version === undefined ? [1, 0, 0] : args.dependency_version;
      if (!validVersion(depVersion)) throw new Error("dependency_version must contain three non-negative integers");
      manifest.dependencies = [{ uuid: args.dependency_uuid, version: depVersion }];
    }
    return { value: { status: "generated", pack_type: type, manifest, writes_applied: false, runtime_status: "NOT RUN" } };
  }
  if (name === "bedrock_validate_manifest") {
    const m = args.manifest as Record<string, unknown>;
    const findings: Array<{ severity: string; path: string; message: string }> = [];
    if (!m || typeof m !== "object" || Array.isArray(m)) throw new Error("manifest must be a JSON object");
    if (m.format_version !== 2) findings.push({ severity: "ERROR", path: "format_version", message: "Expected format_version 2." });
    const h = m.header as Record<string, unknown>;
    if (!h || typeof h !== "object") findings.push({ severity: "ERROR", path: "header", message: "Missing header object." });
    else {
      if (typeof h.name !== "string" || !h.name.trim()) findings.push({ severity: "ERROR", path: "header.name", message: "A non-empty name is required." });
      if (typeof h.description !== "string") findings.push({ severity: "ERROR", path: "header.description", message: "Description must be a string." });
      if (!validUuid(h.uuid)) findings.push({ severity: "ERROR", path: "header.uuid", message: "Header UUID is invalid." });
      if (!validVersion(h.version)) findings.push({ severity: "ERROR", path: "header.version", message: "Version must contain three non-negative integers." });
      if (!validVersion(h.min_engine_version)) findings.push({ severity: "ERROR", path: "header.min_engine_version", message: "min_engine_version must contain three non-negative integers." });
    }
    if (!Array.isArray(m.modules) || m.modules.length === 0) findings.push({ severity: "ERROR", path: "modules", message: "At least one module is required." });
    else {
      const seen = new Set<string>();
      m.modules.forEach((raw, i) => {
        const mod = raw as Record<string, unknown>;
        if (!mod || typeof mod !== "object") { findings.push({ severity: "ERROR", path: `modules[${i}]`, message: "Module must be an object." }); return; }
        if (!["data", "resources", "script", "javascript", "client_data", "interface", "world_template"].includes(String(mod.type))) findings.push({ severity: "ERROR", path: `modules[${i}].type`, message: "Unknown or missing module type." });
        if (!validUuid(mod.uuid)) findings.push({ severity: "ERROR", path: `modules[${i}].uuid`, message: "Module UUID is invalid." });
        else if (seen.has(mod.uuid.toLowerCase())) findings.push({ severity: "ERROR", path: `modules[${i}].uuid`, message: "Duplicate module UUID." });
        else seen.add(mod.uuid.toLowerCase());
        if (!validVersion(mod.version)) findings.push({ severity: "ERROR", path: `modules[${i}].version`, message: "Module version must contain three non-negative integers." });
      });
    }
    if (Array.isArray(m.dependencies)) m.dependencies.forEach((raw, i) => {
      const d = raw as Record<string, unknown>;
      if (!d || !validUuid(d.uuid)) findings.push({ severity: "ERROR", path: `dependencies[${i}].uuid`, message: "Dependency UUID is invalid." });
      if (!d || !validVersion(d.version)) findings.push({ severity: "ERROR", path: `dependencies[${i}].version`, message: "Dependency version is invalid." });
    });
    return { value: { status: findings.some(f => f.severity === "ERROR") ? "invalid" : "valid", findings, error_count: findings.filter(f => f.severity === "ERROR").length, runtime_status: "NOT RUN" }, isError: false };
  }
  if (name === "bedrock_read_plugin_source") {
    const path = args.path;
    if (typeof path !== "string" || path.startsWith("/") || path.includes("..") || path.includes("\\") || !(path.startsWith("server/") || path.startsWith("skills/"))) throw new Error("Only safe relative paths under server/ or skills/ are allowed.");
    const branch = env.GITHUB_BRANCH || DEFAULT_BRANCH;
    const url = `https://raw.githubusercontent.com/${REPO}/${encodeURIComponent(branch)}/${path.split("/").map(encodeURIComponent).join("/")}`;
    const upstream = await fetch(url, { headers: { "accept": "text/plain" }, signal: AbortSignal.timeout(8000) });
    if (!upstream.ok) throw new Error(upstream.status === 404 ? "Source file not found." : `GitHub returned HTTP ${upstream.status}.`);
    const content = await upstream.text();
    if (content.length > 100_000) throw new Error("Source file exceeds the 100 KB response limit.");
    return { value: { status: "ok", path, branch, content, source_url: url } };
  }
  if (name === "bedrock_plugin_capabilities") {
    return { value: { status: "partial_remote_gateway", preserved_python_modules: modules, preserved_module_count: modules.length, remote_runtime: "Cloudflare Workers JavaScript/TypeScript, stateless", current_remote_tools: tools.map(t => t.name), local_python_mcp: "Unchanged; full local STDIO toolset remains in server/*.py", limitations: ["The Python audit/ZIP/filesystem/MCT execution modules are not executed by this free Worker yet.", "Remote tools in this Worker are lightweight manifest utilities and bounded GitHub source reads.", "No Containers, Durable Objects, paid storage or paid APIs are used."] } };
  }
  throw new Error(`Unknown tool: ${name}`);
}
function authorized(request: Request, token: string): boolean {
  const supplied = request.headers.get("authorization") || "";
  const expected = `Bearer ${token}`;
  if (!token || supplied.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < expected.length; i++) diff |= supplied.charCodeAt(i) ^ expected.charCodeAt(i);
  return diff === 0;
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") return response({ status: "ok", service: "minecraft-bedrock-engineer", gateway: "workers-free", containers: false, version: "1.4.1-free-gateway" });
    if (url.pathname !== "/mcp") return response({ error: "not_found" }, 404);
    if (request.method !== "POST") return response({ error: "method_not_allowed", allowed: ["POST"] }, 405, { allow: "POST" });
    if (!env.MCP_AUTH_TOKEN) return response({ error: "server_not_configured", message: "MCP_AUTH_TOKEN secret is missing." }, 503);
    if (!authorized(request, env.MCP_AUTH_TOKEN)) return response({ error: "unauthorized" }, 401, { "www-authenticate": "Bearer" });
    const raw = await request.text();
    if (raw.length > MAX_BODY) return response({ error: "request_too_large" }, 413);
    let message: Rpc;
    try { message = JSON.parse(raw) as Rpc; } catch { return response(rpcError(null, -32700, "Parse error"), 400); }
    if (!message || message.jsonrpc !== "2.0" || typeof message.method !== "string" || (message.params !== undefined && (typeof message.params !== "object" || message.params === null || Array.isArray(message.params)))) return response(rpcError(message?.id ?? null, -32600, "Invalid Request"), 400);
    if (message.method.startsWith("notifications/")) return new Response(null, { status: 202, headers: { "cache-control": "no-store" } });
    const id = message.id ?? null;
    if (message.method === "initialize") {
      const requested = message.params?.protocolVersion;
      const supported = ["2025-06-18", "2025-03-26", "2024-11-05"];
      return response({ jsonrpc: "2.0", id, result: { protocolVersion: supported.includes(String(requested)) ? requested : "2025-03-26", capabilities: { tools: { listChanged: false } }, serverInfo: { name: "minecraft-bedrock-engineer-free", version: "1.4.1" }, instructions: "Free stateless Worker gateway. Local Python MCP retains the full toolset; remote Worker currently exposes lightweight manifest and source-reference tools." } });
    }
    if (message.method === "ping") return response({ jsonrpc: "2.0", id, result: {} });
    if (message.method === "tools/list") return response({ jsonrpc: "2.0", id, result: { tools } });
    if (message.method === "tools/call") {
      const params = message.params || {};
      if (typeof params.name !== "string" || (params.arguments !== undefined && (typeof params.arguments !== "object" || params.arguments === null || Array.isArray(params.arguments)))) return response(rpcError(id, -32602, "Invalid tools/call parameters"));
      try {
        const result = await callTool(params.name, (params.arguments || {}) as Record<string, unknown>, env);
        return response({ jsonrpc: "2.0", id, result: toolResult(result.value, result.isError) });
      } catch (error) {
        const messageText = error instanceof Error ? error.message : "Tool execution failed";
        return response({ jsonrpc: "2.0", id, result: toolResult({ status: "error", message: messageText }, true) });
      }
    }
    return response(rpcError(id, -32601, "Method not found"));
  }
};
