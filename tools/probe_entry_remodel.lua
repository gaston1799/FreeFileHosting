local ROOT = "E:/ForbiddenV2"
local ENTRY_PATH = ROOT .. "/inject/entry.lua"

local function readFile(path)
	local file = io.open(path, "rb")
	assert(file, "Failed to open " .. path)
	local data = file:read("*a")
	file:close()
	return data
end

local function splitLines(text)
	local lines = {}
	for line in (text .. "\n"):gmatch("(.-)\r?\n") do
		lines[#lines + 1] = line
	end
	return lines
end

local function buildPrelude(lines)
	local out = {}
	for i, line in ipairs(lines) do
		if line:find("^local BASE_URL = inferBaseUrl%(%)") then
			break
		end
		out[#out + 1] = line
	end
	out[#out + 1] = "return readInjectedBase()"
	return table.concat(out, "\n")
end

local function runCase(name, env)
	local entrySource = readFile(ENTRY_PATH)
	local lines = splitLines(entrySource)
	local prelude = buildPrelude(lines)
	local chunk, loadErr
	if loadstring then
		chunk, loadErr = loadstring(prelude, "@probe_entry.lua")
		if chunk and setfenv then
			setfenv(chunk, env)
		end
	else
		chunk, loadErr = load(prelude, "@probe_entry.lua", "t", env)
	end
	if not chunk then
		print("[LOAD FAIL]", name, loadErr)
		return
	end

	local ok, result = pcall(chunk)
	if ok then
		print("[OK]", name, tostring(result))
	else
		print("[FAIL]", name, tostring(result))
	end
end

print("=== REMODEL ENTRY PRELUDE PROBE START ===")

runCase("normal_table_insert", {
	_G = {},
	type = type,
	ipairs = ipairs,
	pcall = pcall,
	loadstring = loadstring,
	load = load,
	setfenv = setfenv,
	debug = nil,
	shared = {},
	table = table,
})

runCase("missing_table_insert", {
	_G = {},
	type = type,
	ipairs = ipairs,
	pcall = pcall,
	loadstring = loadstring,
	load = load,
	setfenv = setfenv,
	debug = nil,
	shared = {},
	table = {},
})

runCase("shared_lookup_error", {
	_G = {},
	type = type,
	ipairs = ipairs,
	pcall = pcall,
	loadstring = loadstring,
	load = load,
	setfenv = setfenv,
	debug = nil,
	shared = setmetatable({}, {
		__index = function()
			error("shared access failed")
		end,
	}),
	table = table,
})

print("=== REMODEL ENTRY PRELUDE PROBE END ===")
