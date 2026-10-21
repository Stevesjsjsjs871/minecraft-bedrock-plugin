(function () {
  const ID = "minecraft_bedrock_mcp_bridge";
  let createAction, exportAction, infoDialog;

  function projectSummary() {
    const elements = Array.isArray(Project?.elements) ? Project.elements : [];
    const textures = Array.isArray(Project?.textures) ? Project.textures : [];
    const animations = Array.isArray(Project?.animations) ? Project.animations : [];
    return {
      name: Project?.name || "Untitled",
      format: Format?.id || Format?.name || null,
      counts: { elements: elements.length, textures: textures.length, animations: animations.length },
      elements: elements.slice(0, 500).map(e => ({
        name: e.name, type: e.type, uuid: e.uuid,
        from: Array.isArray(e.from) ? e.from : undefined,
        to: Array.isArray(e.to) ? e.to : undefined,
        origin: Array.isArray(e.origin) ? e.origin : undefined,
        rotation: Array.isArray(e.rotation) ? e.rotation : undefined
      }))
    };
  }

  function createBlockout() {
    if (typeof Cube === "undefined" || typeof Group === "undefined") {
      Blockbench.showQuickMessage("Open a model project first.");
      return;
    }
    const existing = Array.isArray(Project?.elements) ? Project.elements : [];
    if (existing.length && !confirm("This project already has elements. Add a starter mob to it?")) return;
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
    Blockbench.showQuickMessage("Starter mob blockout created. Add textures and verify export format.");
  }

  function exportSummary() {
    const blob = new Blob([JSON.stringify(projectSummary(), null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "blockbench-project-summary.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    Blockbench.showQuickMessage("Project summary exported.");
  }

  Plugin.register(ID, {
    title: "Minecraft Bedrock MCP Bridge",
    author: "Stevesjsjsjs",
    description: "Editor-side helpers for Bedrock models. No network listener or remote code execution.",
    icon: "cubes",
    version: "0.1.0",
    variant: "both",
    tags: ["Minecraft: Bedrock Edition"],
    onload() {
      createAction = new Action("bedrock_mcp_create_mob_blockout", {
        name: "Create Bedrock Mob Blockout",
        description: "Create a simple six-part humanoid starter model",
        icon: "cubes",
        click: createBlockout
      });
      exportAction = new Action("bedrock_mcp_export_summary", {
        name: "Export Project Summary (JSON)",
        description: "Export a safe summary of the current project",
        icon: "file_json",
        click: exportSummary
      });
      MenuBar.addAction(createAction, "tools");
      MenuBar.addAction(exportAction, "file.export");
      infoDialog = new Dialog({
        id: "bedrock_mcp_bridge_info",
        title: "Minecraft Bedrock MCP Bridge",
        width: 440,
        lines: [
          "This first bridge adds editor-side actions; it is not yet a live MCP connection.",
          "Use Tools > Create Bedrock Mob Blockout to create a starter model.",
          "Use File > Export > Export Project Summary (JSON) to save a summary for analysis."
        ],
        buttons: ["Close"]
      });
    },
    onunload() {
      createAction?.delete();
      exportAction?.delete();
      infoDialog?.hide?.();
    }
  });
})();