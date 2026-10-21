import http from "node:http";
import crypto from "node:crypto";

const HOST = "127.0.0.1";
const PORT = 8765;
const token = crypto.randomBytes(24).toString("hex");
const queue = [];
const pending = new Map();
const MAX_QUEUE = 100;

const server = http.createServer((req, res) => {
  const origin = req.headers.origin || "";
  // Browser editor must explicitly authorize localhost access; no wildcard CORS.
  if (origin === "https://web.blockbench.net" || origin === "https://blockbench.net") {
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader("Vary", "Origin");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type, Authorization");
  }
  if (req.method === "OPTIONS") { res.writeHead(204); return res.end(); }
  const url = new URL(req.url || "/", "http://127.0.0.1");
  if (url.pathname === "/health" && req.method === "GET") {
    res.writeHead(200, {"Content-Type":"application/json","Cache-Control":"no-store"});
    return res.end(JSON.stringify({ok:true,service:"bedrock-blockbench-bridge",port:PORT}));
  }
  if (req.headers.authorization !== "Bearer " + token) {
    res.writeHead(401, {"Content-Type":"application/json"});
    return res.end(JSON.stringify({error:"Unauthorized. Use the token printed when the bridge started."}));
  }
  if (url.pathname === "/next" && req.method === "GET") {
    const task = queue.shift() || null;
    res.writeHead(200, {"Content-Type":"application/json","Cache-Control":"no-store"});
    return res.end(JSON.stringify({task}));
  }
  if (url.pathname === "/result" && req.method === "POST") {
    return readJson(req, res, body => {
      const waiter = pending.get(body?.id);
      if (waiter) { pending.delete(body.id); waiter(body.result); }
      res.writeHead(200, {"Content-Type":"application/json"});
      res.end(JSON.stringify({ok:true}));
    });
  }
  if (url.pathname === "/command" && req.method === "POST") {
    return readJson(req, res, body => {
      const allowed = new Set(["project_summary","create_mob_blockout","add_cube"]);
      if (!body || !allowed.has(body.command)) {
        res.writeHead(400, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({error:"Command not allowed. Allowed: project_summary, create_mob_blockout, add_cube."}));
      }
      if (queue.length >= MAX_QUEUE) {
        res.writeHead(429, {"Content-Type":"application/json"});
        return res.end(JSON.stringify({error:"Command queue is full."}));
      }
      const id = crypto.randomUUID();
      queue.push({id, command:body.command, args:body.args || {}});
      const timer = setTimeout(() => {
        pending.delete(id);
        if (!res.headersSent) { res.writeHead(504, {"Content-Type":"application/json"}); res.end(JSON.stringify({error:"No Blockbench plugin response. Is the plugin connected and its tab active?"})); }
      }, 15000);
      pending.set(id, result => {
        clearTimeout(timer);
        if (!res.headersSent) { res.writeHead(200, {"Content-Type":"application/json"}); res.end(JSON.stringify({id,result})); }
      });
    });
  }
  res.writeHead(404, {"Content-Type":"application/json"});
  res.end(JSON.stringify({error:"Not found"}));
});
function readJson(req,res,callback) {
  let data="";
  req.on("data", chunk => { data += chunk; if(data.length > 65536){res.writeHead(413);res.end();req.destroy();} });
  req.on("end", () => { try { callback(JSON.parse(data || "{}")); } catch { res.writeHead(400, {"Content-Type":"application/json"});res.end(JSON.stringify({error:"Invalid JSON"})); } });
}
server.listen(PORT, HOST, () => {
  console.log("Blockbench local bridge listening on http://" + HOST + ":" + PORT);
  console.log("Bearer token (keep private; enter in the Blockbench plugin): " + token);
  console.log("Health check: http://" + HOST + ":" + PORT + "/health");
});
