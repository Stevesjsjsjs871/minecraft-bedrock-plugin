"""Authenticated HTTP adapter for all original Bedrock Engineer Python MCP handlers."""
from __future__ import annotations
import hmac, importlib, json, os, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(os.environ.get("PLUGIN_ROOT","/app/plugin"))
sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/"server"))
WORKSPACE=Path(os.environ.get("MINECRAFT_BEDROCK_WORKSPACE","/data/workspace")).expanduser()
WORKSPACE.mkdir(parents=True,exist_ok=True)
os.environ.setdefault("MINECRAFT_BEDROCK_WORKSPACE",str(WORKSPACE))
MODULE_NAMES=["mcp_server","texture_generator_mcp","texture_link_audit_mcp","entity_authoring_mcp","animation_controller_mcp","animation_clip_mcp","animation_pipeline_audit_mcp","animated_entity_bundle_mcp","geometry_uv_audit_mcp","geometry_uv_template_mcp","texture_painting_mcp","reference_texture_transfer_mcp","uv_mapping_assistant_mcp","visual_reference_analyzer_mcp","reference_mapping_review_mcp","uv_texture_retarget_mcp"]
MODULES=[importlib.import_module(n) for n in MODULE_NAMES]
for module in MODULES:
    if not callable(getattr(module,"handle_message",None)):
        raise RuntimeError("MCP module has no handle_message handler: "+module.__name__)
ROUTES={}; TOOLS=[]
for module in MODULES:
    for tool in getattr(module,"TOOLS",[]):
        name=tool["name"]
        if name in ROUTES: raise RuntimeError("Duplicate MCP tool: "+name)
        ROUTES[name]=module; TOOLS.append(tool)
VERSION=(ROOT/"VERSION").read_text(encoding="utf-8").strip()
MAX_BODY=8*1024*1024

def dispatch(m):
    method=m.get("method"); rid=m.get("id"); p=m.get("params") or {}
    if method=="initialize":
        pv=p.get("protocolVersion","2025-03-26")
        return {"jsonrpc":"2.0","id":rid,"result":{"protocolVersion":pv if pv in ("2025-06-18","2025-03-26","2024-11-05") else "2025-03-26","capabilities":{"tools":{"listChanged":False}},"serverInfo":{"name":"minecraft-bedrock-engineer","version":VERSION}}}
    if method=="ping": return {"jsonrpc":"2.0","id":rid,"result":{}}
    if method=="tools/list": return {"jsonrpc":"2.0","id":rid,"result":{"tools":TOOLS}}
    if method=="tools/call":
        module=ROUTES.get(p.get("name"))
        if module is None: return {"jsonrpc":"2.0","id":rid,"error":{"code":-32602,"message":"Unknown tool"}} 
        return module.handle_message({"jsonrpc":"2.0","id":rid,"method":"tools/call","params":p})
    if method and method.startswith("notifications/"): return None
    return {"jsonrpc":"2.0","id":rid,"error":{"code":-32601,"message":"Method not found"}}

class Handler(BaseHTTPRequestHandler):
    def send_json(self,status,obj):
        raw=b"" if obj is None else json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers()
        if raw: self.wfile.write(raw)
    def authorized(self):
        expected=os.environ.get("MCP_BACKEND_TOKEN","")
        supplied=self.headers.get("Authorization","")
        return bool(expected) and hmac.compare_digest(supplied,"Bearer "+expected)
    def do_GET(self):
        if self.path.rstrip("/")!="/health": return self.send_json(404,{"error":"not_found"})
        return self.send_json(200,{"status":"ok","version":VERSION,"servers":len(MODULES),"tools":len(TOOLS)})
    def do_POST(self):
        if self.path.rstrip("/")!="/mcp": return self.send_json(404,{"error":"not_found"})
        if not self.authorized(): return self.send_json(401,{"error":"unauthorized"})
        try:
            n=int(self.headers.get("Content-Length","0"))
            if n<1 or n>MAX_BODY:return self.send_json(413,{"error":"request_size_out_of_bounds"})
            msg=json.loads(self.rfile.read(n)); result=dispatch(msg)
            self.send_json(202 if result is None else 200,result)
        except (ValueError, json.JSONDecodeError): self.send_json(400,{"error":"invalid_json"})
        except Exception as exc:
            sys.stderr.write("[bedrock-mcp] request failed: "+type(exc).__name__+"\n")
            self.send_json(500,{"error":"internal_error","type":type(exc).__name__})
    def log_message(self,fmt,*args):sys.stderr.write("[bedrock-mcp] "+(fmt%args)+"\n")

if __name__=="__main__":
    if not os.environ.get("MCP_BACKEND_TOKEN"):
        raise RuntimeError("MCP_BACKEND_TOKEN must be configured; refusing to start an unauthenticated MCP server.")
    ThreadingHTTPServer(("0.0.0.0",int(os.environ.get("PORT","8080"))),Handler).serve_forever()
