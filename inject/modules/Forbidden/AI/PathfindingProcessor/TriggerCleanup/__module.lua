--[[ 7/24/25
Cleanups up the API.
This is used to remove any visualizations, waypoints, or other data that was created for the NPC.
This is called when the NPC is removed from the game or when the AI is no longer needed
Prevents memory leaks.

Developer History
    > @crit-dev (@rman501), initial commit
        o7 to future devs
]]--

-- == Module Declaration ==
local root                  = script.Parent.Parent.Parent
local ConfigHandler             = remoteRequire("Forbidden/AI/ConfigHandler")
local DirectMoveTo              = remoteRequire("Forbidden/AI/DirectMoveTo")
local WaypointLooper            = remoteRequire("Forbidden/AI/PathfindingProcessor/WaypointLooper")
local WaypointsVisualization    = remoteRequire("Forbidden/AI/Visualization/WaypointsVisualization")
local Common                    = remoteRequire("Forbidden/Common")


-- == API Function == --
return function(NPC: Instance)

    WaypointsVisualization.DeleteVisualization(NPC)
    
    ConfigHandler.TriggerCleanup(NPC)

    WaypointLooper.TriggerCleanup(NPC)

    DirectMoveTo.TriggerCleanup(NPC)

    Common.TriggerCleanupTypeHelp(NPC)
    
end