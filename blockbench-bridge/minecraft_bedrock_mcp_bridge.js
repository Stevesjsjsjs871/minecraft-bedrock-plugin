(function () {
  const ID = "minecraft_bedrock_mcp_bridge";
  const BASE = "http://127.0.0.1:8765";
  let pollTimer = null;
  let busy = false;
  let statusAction = null;
  let blockoutAction = null;

  async function api(path, options) {
    const response = await fetch(BASE + path, {
      cache: "no-store",
      ...options,
      headers: { "Content-Type": "application/json", ...(options && options.headers || {}) }
    });
    if (!response.ok) throw new Error("Bridge HTTP " + response.status);
    return response.json();
  }

  function getProjectSummary() {
    const elements = Array.isArray(Project?.elements) ? Project.elements : [];
    const textures = Array.isArray(Project?.textures) ? Project.textures : [];
    const animations = Array.isArray(Project?.animations) ? Project.animations : [];
    return {
      name: Project?.name || "Untitled",
      format: Format?.id || Format?.name || null,
      counts: { elements: elements.length, textures: textures.length, animations: animations.length },
      elements: elements.slice(0, 300).map(e => ({
        name: e.name, type: e.type, uuid: e.uuid,
        from: Array.isArray(e.from) ? e.from : undefined,
        to: Array.isArray(e.to) ? e.to : undefined,
        origin: Array.isArray(e.origin) ? e.origin : undefined,
        rotation: Array.isArray(e.rotation) ? e.rotation : undefined
      }))
    };
  }

  function createBlockout() {
    if (typeof Cube === "undefined" || typeof Group === "undefined") throw new Error("Open a supported model project first.");
    const existing = Array.isArray(Project?.elements) ? Project.elements : [];
    if (existing.length && !confirm("This project already contains elements. Add a starter mob to it?")) {
      return { cancelled: true };
    }
    Undo.initEdit({ elements: [], outliner: true, selection: true });
    const root = new Group({ name: "root", origin: [0, 0, 0] }).init();
    root.addTo();
    const parts = [
      {name:"body", from:[-4,6,-2], to:[4,14,2], origin:[0,10,0]},
      {name:"head", from:[-4,14,-4], to:[4,22,4], origin:[0,18,0]},
      {name:"left_arm", from:[4,6,-2], to:[6,14,2], origin:[5,14,0]},
      {name:"right_arm", from:[-6,6,-2], to:[-4,14,2], origin:[-5,14,0]},
      {name:"left_leg", from:[0,0,-2], to:[2,6,2], origin:[1,6,0]},
      {name:"right_leg", from:[-2,0,-2], to:[0,6,2], origin:[-1,6,0]}
    ];
    for (const part of parts) new Cube(part).addTo(root);
    root.open();
    Canvas.updateAll();
    Undo.finishEdit("Create Bedrock mob blockout");
    return { created: parts.length, group: "root" };
  }

  async function handleCommand(command) {
    let result;
    try {
      if (command.type === "get_project") result = getProjectSummary();
      else if (command.type === "create_blockout") result = createBlockout();
      else throw new Error("Unsupported command: " + command.type);
      await api("/result", { method: "POST", body: JSON.stringify({ id: command.id, ok: true, result }) });
    } catch (error) {
      try { await api("/result", { method: "POST", body: JSON.stringify({ id: command.id, ok: false, error: String(error?.message || error) }) }); } catch (_) {}
    }
  }

  async function poll() {
    if (busy) return;
    busy = true;
    try {
      const data = await api("/next");
      if (data.command) await handleCommand(data.command);
    } catch (error) {
      // Bridge may not be running yet; retry quietly.
    } finally {
      busy = false;
    }
  }

  Plugin.register(ID, {
    title: "Minecraft Bedrock MCP Bridge",
    author: "Stevesjsjsjs",
    description: "Connects the active Blockbench tab to a loopback-only Termux MCP bridge. Allows project summary and a starter blockout.",
    icon: "cubes",
    version: "0.2.0",
    variant: "both",
    tags: ["Minecraft: Bedrock Edition"],
    onload() {
      statusAction = new Action("bedrock_mcp_bridge_status", {
        name: "Check Termux Bridge",
        description: "Check the local Termux bridge connection",
        icon: "link",
        click: async () => {
          try {
            const status = await api("/health");
            Blockbench.showQuickMessage(status.client_connected ? "Termux bridge connected" : "Bridge server found; waiting for editor poll");
          } catch (error) {
            Blockbench.showQuickMessage("Termux bridge unavailable. Start npm start in Termux.");
          }
        }
      });
      blockoutAction = new Action("bedrock_mcp_create_mob_blockout", {
        name: "Create Bedrock Mob Blockout",
        description: "Create a simple six-part humanoid starter model",
        icon: "cubes",
        click: () => {
          try {
            const result = createBlockout();
            if (!result.cancelled) Blockbench.showQuickMessage("Created starter blockout");
          } catch (error) {
            Blockbench.showQuickMessage("Could not create model: " + error.message);
          }
        }
      });
      MenuBar.addAction(statusAction, "tools");
      MenuBar.addAction(blockoutAction, "tools");
      pollTimer = setInterval(poll, 700);
      poll();
    },
    onunload() {
      if (pollTimer) clearInterval(pollTimer);
      statusAction?.delete();
      blockoutAction?.delete();
    }
  });
})();