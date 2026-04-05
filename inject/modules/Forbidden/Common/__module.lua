local storage = remoteRequire("Forbidden/Common/Storage")
local typehelp = remoteRequire("Forbidden/Common/TypeHelp")

return {
    GetForbiddenStorageFolder = storage.GetForbiddenStorageFolder,
    GetForbiddenTemporaryWorkspaceFolder = storage.GetForbiddenTemporaryWorkspaceFolder,
    GetForbiddenWSPartsFolder = storage.GetForbiddenWSPartsFolder,
    GetBasePart = typehelp.GetBasePart,
    GetDistanceFromNPCToTarget = typehelp.GetDistanceFromNPCToTarget,
    TriggerCleanupTypeHelp = typehelp.TriggerCleanup
}