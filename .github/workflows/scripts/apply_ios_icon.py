#!/usr/bin/env python3
"""Set the app icon in a Godot-generated, single-app Xcode project."""

import argparse
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import uuid


def apply_icon(project_dir, icon_dir):
    if icon_dir.suffix != ".icon" or not (icon_dir / "icon.json").is_file():
        raise ValueError(f"Expected an Icon Composer bundle at {icon_dir}")

    project_file = project_dir / "project.pbxproj"
    project = plistlib.loads(subprocess.check_output(
        ["plutil", "-convert", "xml1", "-o", "-", str(project_file)]
    ))
    objects = project["objects"]
    root = objects[project["rootObject"]]
    app, = (objects[key] for key in root["targets"]
            if objects[key].get("productType") == "com.apple.product-type.application")
    resources, = (objects[key] for key in app["buildPhases"]
                  if objects[key]["isa"] == "PBXResourcesBuildPhase")
    children = objects[root["mainGroup"]]["children"]

    file_id = next((key for key in children
                    if objects[key].get("path") == icon_dir.name
                    and objects[key].get("lastKnownFileType") == "folder.iconcomposer.icon"), None)
    if file_id is None:
        file_id = uuid.uuid4().hex[:24].upper()
        objects[file_id] = {
            "isa": "PBXFileReference",
            "lastKnownFileType": "folder.iconcomposer.icon",
            "path": icon_dir.name,
            "sourceTree": "<group>",
        }
        children.append(file_id)

    if not any(objects[key].get("fileRef") == file_id for key in resources["files"]):
        build_id = uuid.uuid4().hex[:24].upper()
        objects[build_id] = {"isa": "PBXBuildFile", "fileRef": file_id}
        resources["files"].append(build_id)

    configs = objects[app["buildConfigurationList"]]["buildConfigurations"]
    for key in configs:
        objects[key]["buildSettings"]["ASSETCATALOG_COMPILER_APPICON_NAME"] = icon_dir.stem

    shutil.copytree(icon_dir, project_dir.parent / icon_dir.name, dirs_exist_ok=True)
    with tempfile.TemporaryDirectory(dir=project_dir) as temporary:
        output = Path(temporary) / project_file.name
        output.write_bytes(plistlib.dumps(project))
        subprocess.run(["plutil", "-lint", str(output)], check=True)
        output.replace(project_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("icon", type=Path)
    args = parser.parse_args()
    try:
        apply_icon(args.project, args.icon)
    except (ValueError, KeyError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"Could not apply the iOS icon: {exc}\n")
