package main

import (
	"fmt"
	"os"

	pm "github.com/samuelyuan/polytopiamapmodelgo"
)

func main() {
	pm.DecompressFile(os.Args[1])
	pm.DebugMode = true
	defer func() { if r := recover(); r != nil { fmt.Println("PANIC:", r) } }()
	s, err := pm.ReadPolytopiaCompressedFile(os.Args[1])
	fmt.Println(err)
	if s != nil { fmt.Println(s.GameVersion, s.MapWidth) }
}
