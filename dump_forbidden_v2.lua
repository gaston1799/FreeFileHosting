local ASSET_ID = "99009254123330"
local ROOT_DIR = "E:/ForbiddenV2"
local MODEL_PATH = ROOT_DIR .. "/ForbiddenV2.rbxmx"
local SCRIPT_DIR = ROOT_DIR .. "/scripts"
local MANIFEST_PATH = ROOT_DIR .. "/manifest.txt"

local SCRIPT_CLASSES = {
	Script = true,
	LocalScript = true,
	ModuleScript = true,
}

local function sanitizeName(name)
	local cleaned = name:gsub("[<>:\"/\\|%?%*]", "_")
	cleaned = cleaned:gsub("%s+", " ")
	if cleaned == "" then
		cleaned = "unnamed"
	end
	return cleaned
end

local function splitPath(path)
	local parts = {}
	for part in path:gmatch("[^/]+") do
		table.insert(parts, part)
	end
	return parts
end

local function joinPath(parts)
	return table.concat(parts, "/")
end

local function getRelativeNames(root, instance)
	local names = {}
	local current = instance

	while current and current ~= root do
		table.insert(names, 1, sanitizeName(current.Name))
		current = current.Parent
	end

	return names
end

local function getScriptExtension(className)
	if className == "ModuleScript" then
		return "module.lua"
	elseif className == "LocalScript" then
		return "client.lua"
	end
	return "server.lua"
end

local function ensureParentDir(filePath)
	local parts = splitPath(filePath)
	table.remove(parts, #parts)
	if #parts > 0 then
		remodel.createDirAll(joinPath(parts))
	end
end

local function readSource(instance)
	local ok, value = pcall(function()
		return remodel.getRawProperty(instance, "Source")
	end)

	if ok and type(value) == "string" then
		return value
	end

	return "-- Failed to read Source for " .. instance:GetFullName()
end

remodel.createDirAll(ROOT_DIR)
remodel.createDirAll(SCRIPT_DIR)

local instances = remodel.readModelAsset(ASSET_ID)
assert(#instances > 0, "No instances returned from asset")

local root = instances[1]
remodel.writeModelFile(MODEL_PATH, root)

local manifestLines = {
	"AssetId: " .. ASSET_ID,
	"Root: " .. root.Name .. " (" .. root.ClassName .. ")",
	"ModelFile: " .. MODEL_PATH,
	"",
	"Exported scripts:",
}

local scriptCount = 0

for _, instance in ipairs(root:GetDescendants()) do
	if SCRIPT_CLASSES[instance.ClassName] then
		scriptCount = scriptCount + 1

		local relativeNames = getRelativeNames(root, instance)
		local exportBase = string.format("%03d_%s", scriptCount, table.concat(relativeNames, "__"))
		local exportPath = SCRIPT_DIR .. "/" .. exportBase .. "." .. getScriptExtension(instance.ClassName)

		ensureParentDir(exportPath)
		remodel.writeFile(exportPath, readSource(instance))

		table.insert(
			manifestLines,
			string.format(
				"[%03d] %s | %s | %s",
				scriptCount,
				instance.ClassName,
				instance:GetFullName(),
				exportPath
			)
		)
	end
end

table.insert(manifestLines, "")
table.insert(manifestLines, "Total scripts: " .. tostring(scriptCount))
remodel.writeFile(MANIFEST_PATH, table.concat(manifestLines, "\n"))

print("Wrote model:", MODEL_PATH)
print("Wrote manifest:", MANIFEST_PATH)
print("Exported scripts:", scriptCount)
