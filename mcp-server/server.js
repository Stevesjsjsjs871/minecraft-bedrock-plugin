#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "node:fs/promises";
import path from "node:path";

const server = new McpServer({
  name: "minecraft-bedrock-mcp-server",
  version: "0.1.0"
});

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function textResult(value) {
  return { content: [{ type: "text", text: typeof value === "string" ? value : JSON.stringify(value, null, 2) }] };
}

function validateManifest(manifest) {
  const errors = [];
  const warnings = [];
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return { valid: false, errors: ["Manifest root must be a JSON object."], warnings };
  }
  if (manifest.format_version === undefined) warnings.push("Missing format_version.");
  if (!manifest.header || typeof manifest.header !== "object") {
    errors.push("Missing header object.");
  } else {
    if (typeof manifest.header.name !== "string" || !manifest.header.name.trim()) errors.push("header.name must be a non-empty string.");
    if (typeof manifest.header.description !== "string") warnings.push("header.description is missing or is not a string.");
    if (!Array.isArray(manifest.header.version) || manifest.header.version.length !== 3 || !manifest.header.version.every(n => Number.isInteger(n) && n >= 0)) {
      errors.push("header.version must be an array of three non-negative integers, e.g. [1, 0, 0].");
    }
    if (!UUID_RE.test(String(manifest.header.uuid ?? ""))) errors.push("header.uuid is not a valid versioned UUID.");
  }
  if (!Array.isArray(manifest.modules) || manifest.modules.length === 0) {
    errors.push("modules must be a non-empty array.");
  } else {
    for (let i = 0; i < manifest.modules.length; i++) {
      const module = manifest.modules[i];
      if (!module || typeof module !== "object") {
        errors.push(`modules[${i}] must be an object.`);
        continue;
      }
      if (!["data", "resources", "client_data", "javascript"].includes(module.type)) {
        errors.push(`modules[${i}].type is missing or unsupported: ${String(module.type)}.`);
      }
      if (!Array.isArray(module.version) || module.version.length !== 3 || !module.version.every(n => Number.isInteger(n) && n >= 0)) {
        errors.push(`modules[${i}].version must contain three non-negative integers.`);
      }
      if (!UUID_RE.test(String(module.uuid ?? ""))) errors.push(`modules[${i}].uuid is not a valid versioned UUID.`);
    }
  }
  if (manifest.dependencies !== undefined && !Array.isArray(manifest.dependencies)) {
    errors.push("dependencies must be an array when present.");
  }
  return { valid: errors.length === 0, errors, warnings };
}

server.tool(
  "validate_manifest_json",
  "Validate the basic structure of a Minecraft Bedrock manifest.json provided as text. This is a static check, not a full engine validation.",
  { manifest_json: z.string().min(2).describe("Complete UTF-8 contents of manifest.json") },
  async ({ manifest_json }) => {
    let parsed;
    try { parsed = JSON.parse(manifest_json); }
    catch (error) { return textResult({ valid: false, errors: [`Invalid JSON: ${error.message}`], warnings: [] }); }
    return textResult(validateManifest(parsed));
  }
);

server.tool(
  "validate_manifest_file",
  "Read and validate a manifest.json at an explicit local path. Intended for Android/Termux paths after storage permission is granted.",
  { file_path: z.string().min(1).describe("Absolute or relative path to manifest.json") },
  async ({ file_path }) => {
    try {
      const absolute = path.resolve(file_path);
      const raw = await fs.readFile(absolute, "utf8");
      const result = validateManifest(JSON.parse(raw));
      return textResult({ file_path: absolute, ...result });
    } catch (error) {
      return textResult({ valid: false, errors: [`Could not read or parse manifest: ${error.message}`], warnings: [] });
    }
  }
);

server.tool(
  "inspect_pack_directory",
  "Inspect a local Bedrock Behavior Pack or Resource Pack directory. Lists files and checks for manifest.json and common expected folders. Does not execute scripts or follow symbolic links.",
  {
    directory_path: z.string().min(1).describe("Path to a BP/RP directory"),
    max_files: z.number().int().min(1).max(2000).default(500).describe("Maximum number of file entries to return")
  },
  async ({ directory_path, max_files }) => {
    const root = path.resolve(directory_path);
    try {
      const rootStat = await fs.stat(root);
      if (!rootStat.isDirectory()) return textResult({ error: "The supplied path is not a directory.", directory: root });
      const files = [];
      const problems = [];
      const queue = [{ abs: root, rel: "" }];
      while (queue.length && files.length < max_files) {
        const current = queue.shift();
        const entries = await fs.readdir(current.abs, { withFileTypes: true });
        for (const entry of entries) {
          const abs = path.join(current.abs, entry.name);
          const rel = path.posix.join(current.rel, entry.name);
          if (entry.isSymbolicLink()) {
            problems.push(`Skipped symbolic link: ${rel}`);
          } else if (entry.isDirectory()) {
            queue.push({ abs, rel });
          } else if (entry.isFile()) {
            files.push(rel);
            if (files.length >= max_files) break;
          }
        }
      }
      if (queue.length) problems.push(`File listing capped at ${max_files} entries.`);
      const manifestPath = path.join(root, "manifest.json");
      let manifest = null;
      try {
        manifest = validateManifest(JSON.parse(await fs.readFile(manifestPath, "utf8")));
        if (!manifest.valid) problems.push(...manifest.errors.map(e => `manifest.json: ${e}`));
        problems.push(...manifest.warnings.map(e => `manifest.json warning: ${e}`));
      } catch (error) {
        problems.push(`Could not validate root manifest.json: ${error.message}`);
      }
      const lowerFiles = files.map(f => f.toLowerCase());
      const hints = [];
      if (lowerFiles.some(f => f.startsWith("entities/"))) hints.push("Entity definitions folder found.");
      if (lowerFiles.some(f => f.startsWith("animations/"))) hints.push("Animations folder found.");
      if (lowerFiles.some(f => f.startsWith("textures/"))) hints.push("Textures folder found.");
      if (lowerFiles.some(f => f.startsWith("scripts/"))) hints.push("Scripts folder found.");
      if (lowerFiles.some(f => f.startsWith("recipes/"))) hints.push("Recipes folder found.");
      return textResult({
        directory: root,
        file_count_returned: files.length,
        files,
        manifest,
        hints,
        problems,
        note: "Static inspection only. This does not launch Minecraft or prove that the pack works in-game."
      });
    } catch (error) {
      return textResult({ error: `Could not inspect directory: ${error.message}`, directory: root });
    }
  }
);

server.tool(
  "compare_pack_versions",
  "Compare two Minecraft version arrays such as [1, 2, 0].",
  {
    first: z.array(z.number().int().nonnegative()).length(3),
    second: z.array(z.number().int().nonnegative()).length(3)
  },
  async ({ first, second }) => {
    const comparison = first.findIndex((n, i) => n !== second[i]);
    const result = comparison === -1 ? "equal" : first[comparison] > second[comparison] ? "first_is_newer" : "second_is_newer";
    return textResult({ first, second, result });
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
