from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(r"E:\ForbiddenV2")
MANIFEST_PATH = ROOT / "manifest.txt"
SCRIPTS_DIR = ROOT / "scripts"
INJECT_DIR = ROOT / "inject"
MODULES_DIR = INJECT_DIR / "modules"
ENTRY_PATH = INJECT_DIR / "entry.lua"
BUILD_INFO_PATH = INJECT_DIR / "build_info.json"

ROOT_PREFIX = "Forbidden API V2.UngroupInReplicatedStorage."
INJECT_ROOT_NAME = "Forbidden"


MANIFEST_RE = re.compile(r"^\[(\d+)\]\s+([^|]+?)\s+\|\s+(.+?)\s+\|\s+(.+)$")
SOURCE_NAME_RE = re.compile(r"^\d+_(.+)\.(module|client|server)\.lua$")
TARGETED_SOURCE_REWRITES = {
    "require(rs.Forbidden.Packages.robloxstatemachine)": "require(__FORBIDDEN_ROOT.Packages.robloxstatemachine)",
}
BLOCK_COMMENT_START_RE = re.compile(r"^\s*--\[(=*)\[")
LOCAL_ASSIGN_RE = re.compile(r"^\s*local\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")


def parse_manifest() -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for raw_line in MANIFEST_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        match = MANIFEST_RE.match(line)
        if not match:
            continue

        _, class_name, full_name, exported_path = match.groups()
        if not full_name.startswith(ROOT_PREFIX + INJECT_ROOT_NAME):
            continue

        source_file = Path(exported_path.replace("/", "\\"))
        source_name = source_file.name
        source_match = SOURCE_NAME_RE.match(source_name)
        if not source_match:
            raise RuntimeError(f"Unexpected dumped source filename: {source_name}")

        hierarchy_blob = source_match.group(1)
        parts = hierarchy_blob.split("__")
        if not parts or parts[0] != "UngroupInReplicatedStorage":
            raise RuntimeError(f"Unexpected dumped hierarchy in {source_name}")

        parts = parts[1:]
        if not parts or parts[0] != INJECT_ROOT_NAME:
            continue

        node_id = "/".join(parts)

        entries.append(
            {
                "class_name": class_name.strip(),
                "full_name": full_name.strip(),
                "source_path": str(source_file),
                "node_id": node_id,
                "parts": parts,
            }
        )

    return entries


def lua_quote(value: str) -> str:
    return json.dumps(value)


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def patch_source(node_id: str, source: str) -> str:
    patched = source

    for original, replacement in TARGETED_SOURCE_REWRITES.items():
        patched = patched.replace(original, replacement)

    patched = rewrite_static_requires(node_id, patched)

    if node_id == "Forbidden/AI":
        head, marker, tail = patched.rpartition("return API")
        if not marker:
            raise RuntimeError("Could not find `return API` in Forbidden/AI")

        injected_insert_antilag = """
API.InsertAntiLag = function(NPC: Instance, UseExtremeCase: boolean?, IgnoreHumanoidCheck: boolean?)
    warn("Forbidden injected build: AI.InsertAntiLag is not supported.")
    return nil
end

return API"""
        patched = head + injected_insert_antilag + tail

    return patched


def parent_id(node_id: str) -> str | None:
    if "/" not in node_id:
        return None
    return node_id.rsplit("/", 1)[0]


def tokenize_expr(expr: str) -> tuple[str, list[tuple[str, str]]] | None:
    expr = expr.strip()
    if not expr:
        return None

    index = 0
    ident = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expr)
    if not ident:
        return None

    base = ident.group(0)
    index = ident.end()
    ops: list[tuple[str, str]] = []

    while index < len(expr):
        if expr.startswith(".", index):
            index += 1
            match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expr[index:])
            if not match:
                return None
            name = match.group(0)
            index += len(name)
            ops.append(("child", name))
            continue

        if expr.startswith("[", index):
            bracket = re.match(r'\[\s*["\']([^"\']+)["\']\s*\]', expr[index:])
            if not bracket:
                return None
            ops.append(("child", bracket.group(1)))
            index += len(bracket.group(0))
            continue

        if expr.startswith(":WaitForChild(", index):
            wait_match = re.match(r':WaitForChild\(\s*["\']([^"\']+)["\']\s*\)', expr[index:])
            if not wait_match:
                return None
            ops.append(("child", wait_match.group(1)))
            index += len(wait_match.group(0))
            continue

        if expr[index].isspace():
            index += 1
            continue

        return None

    return base, ops


def resolve_expr_to_node(
    expr: str,
    current_node_id: str,
    aliases: dict[str, str],
    node_class_map: dict[str, str],
) -> str | None:
    tokenized = tokenize_expr(expr)
    if not tokenized:
        return None

    base, ops = tokenized

    if base == "script":
        node_id = current_node_id
    elif base in aliases:
        node_id = aliases[base]
    elif base in {"rs", "ReplicatedStorage"}:
        node_id = None
    else:
        return None

    for kind, value in ops:
        if kind != "child":
            return None

        if node_id is None:
            if value != INJECT_ROOT_NAME:
                return None
            node_id = INJECT_ROOT_NAME
            continue

        if value == "Parent":
            node_id = parent_id(node_id)
            if node_id is None:
                return None
            continue

        candidate = f"{node_id}/{value}"
        if candidate not in node_class_map:
            return None
        node_id = candidate

    return node_id


def find_require_calls(line: str) -> list[tuple[int, int, str]]:
    calls: list[tuple[int, int, str]] = []
    cursor = 0

    while True:
        start = line.find("require(", cursor)
        if start == -1:
            break

        index = start + len("require(")
        depth = 1
        while index < len(line):
            char = line[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    expr = line[start + len("require(") : index]
                    calls.append((start, index + 1, expr))
                    cursor = index + 1
                    break
            index += 1
        else:
            break

    return calls


def rewrite_static_requires(current_node_id: str, source: str) -> str:
    aliases: dict[str, str] = {}
    lines = source.splitlines()
    rewritten_lines: list[str] = []
    block_comment_equals: str | None = None

    for line in lines:
        stripped = line.lstrip()

        if block_comment_equals is not None:
            rewritten_lines.append(line)
            if f"]{block_comment_equals}]" in line:
                block_comment_equals = None
            continue

        block_match = BLOCK_COMMENT_START_RE.match(stripped)
        if block_match:
            block_comment_equals = block_match.group(1)
            rewritten_lines.append(line)
            if f"]{block_comment_equals}]" in stripped:
                block_comment_equals = None
            continue

        if stripped.startswith("--"):
            rewritten_lines.append(line)
            continue

        require_calls = find_require_calls(line)
        if require_calls:
            updated_line = line
            for start, end, expr in reversed(require_calls):
                resolved = resolve_expr_to_node(expr, current_node_id, aliases, NODE_CLASS_MAP)
                if not resolved:
                    continue
                if NODE_CLASS_MAP.get(resolved) != "ModuleScript":
                    continue
                replacement = f'remoteRequire({lua_quote(resolved)})'
                updated_line = updated_line[:start] + replacement + updated_line[end:]
            line = updated_line

        assign_match = LOCAL_ASSIGN_RE.match(line)
        if assign_match:
            alias_name, alias_expr = assign_match.groups()
            resolved_alias = resolve_expr_to_node(alias_expr, current_node_id, aliases, NODE_CLASS_MAP)
            if resolved_alias:
                aliases[alias_name] = resolved_alias

        rewritten_lines.append(line)

    return "\n".join(rewritten_lines)


def module_rel_path(parts: list[str]) -> str:
    return "/".join(["modules", *parts, "__module.lua"])


def build_entry(
    node_class_map: dict[str, str],
    module_path_map: dict[str, str],
    entry_module_id: str,
) -> str:
    node_class_items = ",\n".join(
        f"    [{lua_quote(node_id)}] = {lua_quote(class_name)}"
        for node_id, class_name in sorted(node_class_map.items())
    )
    module_path_items = ",\n".join(
        f"    [{lua_quote(node_id)}] = {lua_quote(rel_path)}"
        for node_id, rel_path in sorted(module_path_map.items())
    )

    return f"""-- Auto-generated by tools/build_injected_forbidden.py
-- Usage:
--   local url = "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/inject/entry.lua"
--   local AI = loadstring(game:HttpGet(url), url)()
--
-- If your executor does not preserve the chunk source for debug.info, set:
--   getgenv().__FORBIDDEN_BASE_URL = "https://raw.githubusercontent.com/<owner>/<repo>/<branch>/inject"
-- before loading entry.lua.

local GLOBAL_ENV = (getgenv and getgenv()) or _G

local function inferBaseUrl()
    local injectedBase = GLOBAL_ENV.__FORBIDDEN_BASE_URL
    if type(injectedBase) == "string" and injectedBase ~= "" then
        return (injectedBase:gsub("/+$", ""))
    end

    if debug and debug.info then
        local ok, source = pcall(debug.info, 1, "s")
        if ok and type(source) == "string" then
            source = source:gsub("^@", "")
            if source:match("^https?://") then
                local base = source:match("^(.*)/[^/]+$")
                if base then
                    return base
                end
            end
        end
    end

    error("Unable to infer Forbidden base URL. Use loadstring(game:HttpGet(url), url)() or set __FORBIDDEN_BASE_URL.", 0)
end

local BASE_URL = inferBaseUrl()

local NODE_CLASSES = {{
{node_class_items}
}}

local MODULE_PATHS = {{
{module_path_items}
}}

local NODE_METHODS = {{}}
local NODE_MT = {{
    __index = function(self, key)
        local method = NODE_METHODS[key]
        if method ~= nil then
            return method
        end

        return self._children[key]
    end,
}}

local nodes = {{}}

local function splitId(id)
    local parts = {{}}
    for part in string.gmatch(id, "[^/]+") do
        table.insert(parts, part)
    end
    return parts
end

local function ensureNode(id)
    local existing = nodes[id]
    if existing then
        return existing
    end

    local parts = splitId(id)
    local name = parts[#parts]
    local parentId = id:match("^(.*)/[^/]+$")
    local parentNode = nil
    if parentId then
        parentNode = ensureNode(parentId)
    end

    local node = setmetatable({{
        _forbiddenNode = true,
        _id = id,
        _children = {{}},
        Name = name,
        ClassName = NODE_CLASSES[id] or "Folder",
        Parent = parentNode,
    }}, NODE_MT)

    nodes[id] = node

    if parentNode then
        parentNode._children[name] = node
    end

    return node
end

for id, _ in pairs(NODE_CLASSES) do
    ensureNode(id)
end

function NODE_METHODS:GetChildren()
    local children = {{}}
    for _, child in pairs(self._children) do
        table.insert(children, child)
    end

    table.sort(children, function(a, b)
        return a.Name < b.Name
    end)

    return children
end

function NODE_METHODS:GetDescendants()
    local descendants = {{}}

    local function walk(node)
        for _, child in ipairs(node:GetChildren()) do
            table.insert(descendants, child)
            walk(child)
        end
    end

    walk(self)
    return descendants
end

function NODE_METHODS:FindFirstChild(name, recursive)
    local direct = self._children[name]
    if direct then
        return direct
    end

    if recursive then
        for _, child in ipairs(self:GetChildren()) do
            local found = child:FindFirstChild(name, true)
            if found then
                return found
            end
        end
    end

    return nil
end

function NODE_METHODS:WaitForChild(name, timeout)
    local found = self:FindFirstChild(name, false)
    if found then
        return found
    end

    error(("Synthetic node %s has no child named %s"):format(self:GetFullName(), tostring(name)), 2)
end

function NODE_METHODS:IsA(className)
    return self.ClassName == className
end

function NODE_METHODS:GetFullName()
    local parts = {{}}
    local current = self
    while current do
        table.insert(parts, 1, current.Name)
        current = current.Parent
    end
    return table.concat(parts, ".")
end

function NODE_METHODS:Destroy()
    if self.Parent then
        self.Parent._children[self.Name] = nil
    end
    nodes[self._id] = nil
end

local runtime = {{}}
local moduleCache = {{}}
local loading = {{}}

function runtime:getNode(id)
    local node = nodes[id]
    if not node then
        error("Unknown Forbidden synthetic node: " .. tostring(id), 2)
    end
    return node
end

local function encodeUrlPath(path)
    return (path:gsub("([^%%w%%-%%._~/@])", function(char)
        return string.format("%%%02X", string.byte(char))
    end))
end

    local function syntheticRequire(target)
        if typeof(target) == "Instance" then
            return require(target)
        end

    if type(target) ~= "table" or not target._forbiddenNode then
        error("Forbidden synthetic require expected a synthetic node or Instance.", 2)
    end

    if target.ClassName ~= "ModuleScript" then
        error("Attempted to require non-ModuleScript synthetic node: " .. target:GetFullName(), 2)
    end

    local moduleId = target._id
    if moduleCache[moduleId] ~= nil then
        return moduleCache[moduleId]
    end

    if loading[moduleId] then
        error("Circular synthetic require detected for " .. moduleId, 2)
    end

    local relPath = MODULE_PATHS[moduleId]
    if not relPath then
        error("No remote module path registered for " .. moduleId, 2)
    end

    loading[moduleId] = true

    local url = BASE_URL .. "/" .. encodeUrlPath(relPath)
    local source = game:HttpGet(url)
    local prelude = "local script, require, runtime = ...\\nlocal __FORBIDDEN_ROOT = runtime:getNode('Forbidden')\\n"
    local chunk, loadErr = loadstring(prelude .. source, url)
    if not chunk then
        loading[moduleId] = nil
        error(loadErr, 0)
    end

    local ok, result = pcall(chunk, target, syntheticRequire, runtime)
    loading[moduleId] = nil
    if not ok then
        error(result, 0)
    end

    if result == nil then
        result = true
    end

    moduleCache[moduleId] = result
    return result
    end

    runtime.require = syntheticRequire
    runtime.remoteRequire = function(target)
        if type(target) == "string" then
            target = runtime:getNode(target)
        end
        return syntheticRequire(target)
    end
    GLOBAL_ENV.__FORBIDDEN_LAST_RUNTIME = runtime

    return syntheticRequire(runtime:getNode({lua_quote(entry_module_id)}))
"""


def main() -> None:
    ensure_dir(INJECT_DIR)
    ensure_dir(MODULES_DIR)

    manifest_entries = parse_manifest()
    if not manifest_entries:
        raise RuntimeError("No Forbidden entries found in manifest")

    explicit_nodes: dict[str, str] = {}
    module_entries: list[dict[str, str]] = []

    for entry in manifest_entries:
        explicit_nodes[entry["node_id"]] = entry["class_name"]
        if entry["class_name"] == "ModuleScript":
            module_entries.append(entry)

    node_class_map: dict[str, str] = {}
    for node_id, class_name in explicit_nodes.items():
        node_class_map[node_id] = class_name
        parts = node_id.split("/")
        for i in range(1, len(parts)):
            prefix_id = "/".join(parts[:i])
            node_class_map.setdefault(prefix_id, "Folder")

    global NODE_CLASS_MAP
    NODE_CLASS_MAP = node_class_map

    module_path_map: dict[str, str] = {}

    for entry in module_entries:
        source_path = Path(entry["source_path"])
        source = source_path.read_text(encoding="utf-8")
        patched_source = patch_source(entry["node_id"], source)

        rel_path = module_rel_path(entry["parts"])
        out_path = INJECT_DIR / rel_path
        ensure_dir(out_path.parent)
        out_path.write_text(patched_source, encoding="utf-8")

        module_path_map[entry["node_id"]] = rel_path.replace("\\", "/")

    entry_source = build_entry(
        node_class_map=node_class_map,
        module_path_map=module_path_map,
        entry_module_id="Forbidden/AI",
    )
    ENTRY_PATH.write_text(entry_source, encoding="utf-8")

    BUILD_INFO_PATH.write_text(
        json.dumps(
            {
                "generated_modules": len(module_entries),
                "node_count": len(node_class_map),
                "entry_module": "Forbidden/AI",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
