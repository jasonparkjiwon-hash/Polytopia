#!/bin/sh
# Re-clone the third-party reference repos into ext/ at the commits used (see THIRD_PARTY.md).
set -e
D=$(cd "$(dirname "$0")/.." && pwd); mkdir -p "$D/ext"; cd "$D/ext"
get() { # dir url commit
  [ -d "$1" ] || git clone -q "$2" "$1"
  [ -n "$3" ] && git -C "$1" checkout -q "$3" 2>/dev/null || true
  echo "$1 @ $(git -C "$1" rev-parse --short HEAD)"
}
get HenBOMB_Polyfish                    https://github.com/HenBOMB/Polyfish.git                    a9f90ab
get GAIGResearch_Tribes                 https://github.com/GAIGResearch/Tribes.git                 270e7e5
get DylanHannaScience_polytopia_python  https://github.com/DylanHannaScience/polytopia_python.git  97746bb
get polytopiamapmodelgo                 https://github.com/samuelyuan/polytopiamapmodelgo.git      d09f4e0
get samuelyuan_PolytopiaSaveEditor      https://github.com/samuelyuan/PolytopiaSaveEditor.git      b20890f
get samuelyuan_PolytopiaMapEditor       https://github.com/samuelyuan/PolytopiaMapEditor.git       440439b
get PolytopiaWorld                      https://github.com/samuelyuan/PolytopiaWorld.git           021787e
get Bibliofile_polytopia                https://github.com/Bibliofile/polytopia.git                20a83b5
get JThh_polytopia-ext                  https://github.com/JThh/polytopia-ext.git                  71788c3
get PolyMod                             https://github.com/PolyModdingTeam/PolyMod.git             7972052
get polytopiacalculator                 https://github.com/amigobrewbrew/polytopiacalculatorfirebase-public.git ""
