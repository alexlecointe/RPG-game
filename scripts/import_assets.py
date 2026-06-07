#!/usr/bin/env python3
"""Import Pokemon Assets from ~/Desktop/Pokemon Assets/ into Xcode asset catalog."""
import os, shutil, json, re, unicodedata

SRC = os.path.expanduser("~/Desktop/Pokemon Assets")
DST = os.path.expanduser("~/Projects/RPG-game/ios/RPGAgentCompany/Assets.xcassets")

def sanitize(name: str) -> str:
    """Convert Figma export name to a clean asset name."""
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("←", "left").replace("→", "right")
    name = name.replace("↑", "up").replace("↓", "down")
    name = name.replace("↖︎", "tl").replace("↗︎", "tr")
    name = name.replace("↘︎", "br").replace("↙", "bl")
    name = name.replace("⏺", "center").replace("︎", "")
    name = name.replace("'", "")
    name = re.sub(r"[=,]", "_", name)
    name = re.sub(r"[^a-zA-Z0-9_.\-]", "_", name)
    name = re.sub(r"_+", "_", name)
    name = name.strip("_").lower()
    return name

def make_imageset(dst_dir: str, asset_name: str, src_path: str):
    """Create an .imageset folder with Contents.json and copy the PNG."""
    iset = os.path.join(dst_dir, f"{asset_name}.imageset")
    os.makedirs(iset, exist_ok=True)
    png_name = f"{asset_name}.png"
    shutil.copy2(src_path, os.path.join(iset, png_name))
    contents = {
        "images": [{"filename": png_name, "idiom": "universal"}],
        "info": {"author": "xcode", "version": 1}
    }
    with open(os.path.join(iset, "Contents.json"), "w") as f:
        json.dump(contents, f, indent=2)

def process_folder(subfolder: str, prefix: str, dst_subdir: str = ""):
    src_dir = os.path.join(SRC, subfolder)
    dst_dir = os.path.join(DST, dst_subdir) if dst_subdir else DST
    os.makedirs(dst_dir, exist_ok=True)
    count = 0
    for fname in sorted(os.listdir(src_dir)):
        if not fname.lower().endswith(".png"):
            continue
        base = fname[:-4]  # remove .png
        clean = sanitize(base)
        asset_name = f"{prefix}_{clean}" if prefix else clean
        make_imageset(dst_dir, asset_name, os.path.join(src_dir, fname))
        count += 1
    print(f"  {subfolder}: {count} assets -> {dst_dir}")
    return count

# Clean old generated imagesets
old_sets = [
    "BuildingsSheet", "CharactersSheet", "PathsSheet",
    "base_tiles", "characters_full", "fences_sheet", "gym",
    "house1", "house2", "house3", "lab", "mountains",
    "moving_water", "ornaments_sheet", "paths_full",
    "plants_sheet", "pokemart", "pokemon_center",
    "signs_sheet", "still_water", "water_layer"
]
for name in old_sets:
    p = os.path.join(DST, f"{name}.imageset")
    if os.path.exists(p):
        shutil.rmtree(p)
        print(f"  Removed old: {name}.imageset")

total = 0
total += process_folder("Base", "base")
total += process_folder("Building", "bld")
total += process_folder("Character", "char")
total += process_folder("Ledge", "ledge")
total += process_folder("Mountains", "mtn")
total += process_folder("Moving Water", "mwater")
total += process_folder("Path", "path")
total += process_folder("Plants", "plant")
total += process_folder("Rocks", "rock")
total += process_folder("Still Water", "swater")
total += process_folder("Water Layer", "wlayer")

print(f"\nDone! {total} imagesets created in {DST}")
