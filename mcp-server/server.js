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


function inspectBlockbenchModel(model) {
  const errors = [];
  const warnings = [];
  if (!model || typeof model !== "object" || Array.isArray(model)) {
    return { valid: false, errors: ["Model root must be a JSON object."], warnings };
  }
  if (!Array.isArray(model.elements)) warnings.push("No elements array found; this may not be a standard Blockbench cube model.");
  if (!Array.isArray(model.outliner)) warnings.push("No outliner array found.");
  if (!Array.isArray(model.textures)) warnings.push("No textures array found.");
  const elements = Array.isArray(model.elements) ? model.elements : [];
  const textures = Array.isArray(model.textures) ? model.textures : [];
  const uuids = new Set();
  const duplicateUuids = [];
  for (let i = 0; i < elements.length; i++) {
    const el = elements[i];
    if (!el || typeof el !== "object") { errors.push(`elements[${i}] is not an object.`); continue; }
    if (el.uuid) {
      if (uuids.has(el.uuid)) duplicateUuids.push(el.uuid);
      uuids.add(el.uuid);
    }
    if (!Array.isArray(el.from) || el.from.length !== 3 || !el.from.every(Number.isFinite)) errors.push(`elements[${i}].from must contain 3 numbers.`);
    if (!Array.isArray(el.to) || el.to.length !== 3 || !el.to.every(Number.isFinite)) errors.push(`elements[${i}].to must contain 3 numbers.`);
    if (Array.isArray(el.from) && Array.isArray(el.to) && el.from.length === 3 && el.to.length === 3) {
      if (el.from.some((v, j) => v > el.to[j])) warnings.push(`Element ${el.name ?? i}: one or more 'from' coordinates exceed 'to'.`);
      if ([0,1,2].some(j => Math.abs(el.from[j]) > 256 || Math.abs(el.to[j]) > 256)) warnings.push(`Element ${el.name ?? i}: coordinate outside ±256; check model scale.`);
    }
    if (el.faces && typeof el.faces === "object") {
      for (const [faceName, face] of Object.entries(el.faces)) {
        if (!face || typeof face !== "object") continue;
        if (Number.isInteger(face.texture) && (face.texture < 0 || face.texture >= textures.length)) {
          warnings.push(`Element ${el.name ?? i}, face ${faceName}: texture index ${face.texture} is outside textures array (review candidate; format variants may differ).`);
        }
      }
    }
  }
  if (duplicateUuids.length) errors.push(`Duplicate element UUIDs: ${[...new Set(duplicateUuids)].join(", ")}`);
  const referenced = new Set();
  function walkOutliner(nodes) {
    if (!Array.isArray(nodes)) return;
    for (const node of nodes) {
      if (typeof node === "string") referenced.add(node);
      else if (node && typeof node === "object") {
        if (node.uuid) referenced.add(node.uuid);
        if (Array.isArray(node.children)) walkOutliner(node.children);
      }
    }
  }
  walkOutliner(model.outliner);
  const missingOutlinerRefs = [...referenced].filter(id => !uuids.has(id));
  if (missingOutlinerRefs.length) warnings.push(`Outliner references UUIDs not found in elements: ${missingOutlinerRefs.join(", ")}`);
  const unusedElements = elements.filter(el => el?.uuid && !referenced.has(el.uuid)).map(el => el.name || el.uuid);
  if (unusedElements.length) warnings.push(`Elements not referenced by outliner: ${unusedElements.slice(0, 30).join(", ")}${unusedElements.length > 30 ? "…" : ""}`);
  const animations = Array.isArray(model.animations) ? model.animations.length : 0;
  return {
    valid: errors.length === 0,
    format_version: model.meta?.format_version ?? model.format_version ?? null,
    name: model.name ?? null,
    model_format: model.meta?.model_format ?? null,
    resolution: model.resolution ?? null,
    counts: { elements: elements.length, textures: textures.length, outliner_roots: Array.isArray(model.outliner) ? model.outliner.length : 0, animations },
    texture_summary: textures.slice(0, 100).map(t => ({ name: t?.name ?? null, relative_path: t?.relative_path ?? null, width: t?.width ?? null, height: t?.height ?? null, source_embedded: typeof t?.source === "string" && t.source.startsWith("data:") })),
    errors, warnings,
    note: "Heuristic static inspection only. It does not render the model in Blockbench or prove Minecraft compatibility."
  };
}

server.tool(
  "inspect_blockbench_model_json",
  "Inspect a Blockbench .bbmodel JSON supplied as text: summarize elements, textures, outliner, duplicate UUIDs, coordinate anomalies, and suspicious references.",
  { model_json: z.string().min(2).describe("Complete text of a Blockbench .bbmodel JSON file") },
  async ({ model_json }) => {
    try { return textResult(inspectBlockbenchModel(JSON.parse(model_json))); }
    catch (error) { return textResult({ valid: false, errors: [`Invalid JSON: ${error.message}`], warnings: [] }); }
  }
);

server.tool(
  "inspect_blockbench_model_file",
  "Read and inspect a local Blockbench .bbmodel file. Useful in Termux on Android after storage permission is granted.",
  { file_path: z.string().min(1).describe("Path to a .bbmodel file") },
  async ({ file_path }) => {
    const absolute = path.resolve(file_path);
    try {
      const raw = await fs.readFile(absolute, "utf8");
      return textResult({ file_path: absolute, ...inspectBlockbenchModel(JSON.parse(raw)) });
    } catch (error) {
      return textResult({ file_path: absolute, valid: false, errors: [`Could not read or parse Blockbench model: ${error.message}`], warnings: [] });
    }
  }
);

server.tool(
  "validate_bedrock_geometry_json",
  "Check common Minecraft Bedrock geometry JSON structure, bone names, cube bounds, and duplicate bone identifiers. This is not a complete schema validator.",
  { geometry_json: z.string().min(2).describe("Contents of an exported Bedrock geometry JSON file") },
  async ({ geometry_json }) => {
    let doc;
    try { doc = JSON.parse(geometry_json); }
    catch (error) { return textResult({ valid: false, errors: [`Invalid JSON: ${error.message}`], warnings: [] }); }
    const errors = [], warnings = [];
    const geometries = Array.isArray(doc?.["minecraft:geometry"]) ? doc["minecraft:geometry"] : [];
    if (!geometries.length) errors.push('Expected a non-empty "minecraft:geometry" array.');
    const identifiers = new Set();
    let boneCount = 0, cubeCount = 0;
    for (let gi = 0; gi < geometries.length; gi++) {
      const geo = geometries[gi];
      const id = geo?.description?.identifier;
      if (typeof id !== "string" || !id.trim()) errors.push(`minecraft:geometry[${gi}] is missing description.identifier.`);
      if (id && identifiers.has(id)) errors.push(`Duplicate geometry identifier: ${id}`);
      if (id) identifiers.add(id);
      if (!Array.isArray(geo?.bones)) { errors.push(`Geometry ${id ?? gi} has no bones array.`); continue; }
      const boneNames = new Set();
      for (const bone of geo.bones) {
        boneCount++;
        if (!bone || typeof bone.name !== "string" || !bone.name.trim()) errors.push(`Geometry ${id ?? gi} contains a bone without a name.`);
        else if (boneNames.has(bone.name)) errors.push(`Geometry ${id ?? gi} has duplicate bone name: ${bone.name}`);
        else boneNames.add(bone.name);
        if (bone.parent && !geo.bones.some(b => b?.name === bone.parent)) warnings.push(`Geometry ${id ?? gi}, bone ${bone.name}: parent '${bone.parent}' not found in this geometry.`);
        if (bone.cubes !== undefined && !Array.isArray(bone.cubes)) errors.push(`Bone ${bone.name}: cubes must be an array when present.`);
        for (const cube of Array.isArray(bone.cubes) ? bone.cubes : []) {
          cubeCount++;
          if (!Array.isArray(cube.origin) || cube.origin.length !== 3 || !cube.origin.every(Number.isFinite)) errors.push(`Bone ${bone.name}: cube origin must contain 3 numbers.`);
          if (!Array.isArray(cube.size) || cube.size.length !== 3 || !cube.size.every(n => Number.isFinite(n) && n >= 0)) errors.push(`Bone ${bone.name}: cube size must contain 3 non-negative numbers.`);
          if (Array.isArray(cube.size) && cube.size.some(n => n > 128)) warnings.push(`Bone ${bone.name}: unusually large cube dimension; review scale.`);
        }
      }
    }
    return textResult({ valid: errors.length === 0, counts: { geometries: geometries.length, bones: boneCount, cubes: cubeCount }, identifiers: [...identifiers], errors, warnings, note: "Static structural checks only; validate against the target Bedrock version and test in-game." });
  }
);

server.tool(
  "inspect_png_texture_file",
  "Read PNG header metadata (dimensions and bit depth) without decoding or modifying the texture.",
  { file_path: z.string().min(1).describe("Path to a PNG texture file") },
  async ({ file_path }) => {
    const absolute = path.resolve(file_path);
    try {
      const handle = await fs.open(absolute, "r");
      try {
        const buffer = Buffer.alloc(26);
        const { bytesRead } = await handle.read(buffer, 0, 26, 0);
        const signature = Buffer.from([137,80,78,71,13,10,26,10]);
        if (bytesRead < 26 || !buffer.subarray(0, 8).equals(signature)) return textResult({ valid_png: false, file_path: absolute, error: "File is too short or is not a PNG." });
        return textResult({ valid_png: true, file_path: absolute, width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20), bit_depth: buffer[24], color_type: buffer[25], note: "Header-only inspection; pixel data and transparency have not been decoded." });
      } finally { await handle.close(); }
    } catch (error) { return textResult({ valid_png: false, file_path: absolute, error: error.message }); }
  }
);

server.tool(
  "validate_json_file",
  "Parse any local JSON file and return valid JSON plus its top-level type and keys; does not apply a Minecraft-specific schema.",
  { file_path: z.string().min(1).describe("Path to a JSON file") },
  async ({ file_path }) => {
    const absolute = path.resolve(file_path);
    try {
      const parsed = JSON.parse(await fs.readFile(absolute, "utf8"));
      return textResult({ valid: true, file_path: absolute, top_level_type: Array.isArray(parsed) ? "array" : parsed === null ? "null" : typeof parsed, keys: parsed && !Array.isArray(parsed) && typeof parsed === "object" ? Object.keys(parsed) : [], array_length: Array.isArray(parsed) ? parsed.length : null });
    } catch (error) { return textResult({ valid: false, file_path: absolute, error: error.message }); }
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
