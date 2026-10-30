import { Container } from "@cloudflare/containers";

interface Env {
  BEDROCK_MCP: DurableObjectNamespace<BedrockMcpContainer>;
  MCP_AUTH_TOKEN: string;
}
export class BedrockMcpContainer extends Container {
  defaultPort = 8080;
  sleepAfter = "10m";
}
function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {status, headers: {"content-type":"application/json; charset=utf-8","cache-control":"no-store"}});
}
export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") return json({status:"ok",service:"minecraft-bedrock-engineer",version:"1.4.0"});
    if (url.pathname !== "/mcp") return json({error:"not_found"},404);
    if (request.method !== "POST") return json({error:"method_not_allowed"},405);
    const authorization = request.headers.get("authorization") ?? "";
    const expected = `Bearer ${env.MCP_AUTH_TOKEN}`;
    if (!env.MCP_AUTH_TOKEN || authorization.length !== expected.length) return json({error:"unauthorized"},401);
    let mismatch=0;
    for(let i=0;i<expected.length;i++) mismatch |= authorization.charCodeAt(i)^expected.charCodeAt(i);
    if(mismatch!==0) return json({error:"unauthorized"},401);
    const id=env.BEDROCK_MCP.idFromName("bedrock-engineer-1-4-0");
    const container=env.BEDROCK_MCP.get(id);
    const headers=new Headers(request.headers); headers.delete("authorization"); headers.delete("host");
    return container.fetch(new Request("http://container:8080/mcp",{method:"POST",headers,body:await request.arrayBuffer()}));
  }
};
