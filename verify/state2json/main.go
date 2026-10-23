// state2json: convert a Battle of Polytopia .state save file to JSON (initial map + current map + players + header).
// Built on github.com/samuelyuan/polytopiamapmodelgo. Usage: state2json <in.state> <out.json>
package main

import (
	"encoding/json"
	"fmt"
	"os"

	pm "github.com/samuelyuan/polytopiamapmodelgo"
)

func main() {
	if len(os.Args) < 3 {
		fmt.Println("usage: state2json <in.state> <out.json>")
		os.Exit(2)
	}
	s, err := pm.ReadPolytopiaCompressedFile(os.Args[1])
	if err != nil {
		fmt.Println("FAILED:", err)
		os.Exit(1)
	}
	out := map[string]interface{}{
		"format": "polytopia-state-json/1", "gameVersion": s.GameVersion,
		"mapWidth": s.MapWidth, "mapHeight": s.MapHeight, "currentTurn": s.MaxTurn,
		"header": s.MapHeaderOutput, "initialTiles": s.InitialTileData, "initialPlayers": s.InitialPlayerData,
		"tiles": s.TileData, "players": s.PlayerData, "captures": s.TurnCaptureMap,
	}
	b, _ := json.Marshal(out)
	if err := os.WriteFile(os.Args[2], b, 0644); err != nil {
		fmt.Println("FAILED:", err)
		os.Exit(1)
	}
	fmt.Printf("OK version=%d size=%dx%d turn=%d players=%d\n", s.GameVersion, s.MapWidth, s.MapHeight, s.MaxTurn, len(s.PlayerData))
}
