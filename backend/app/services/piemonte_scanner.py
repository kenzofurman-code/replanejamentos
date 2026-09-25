import os
import json
import glob
from typing import List, Dict, Any

DEFAULT_SEARCH_PATHS = [
    r"C:\Users\HomePC\Piemonte Construtora\Piemonte Engenharia - Planejamento",
    r"C:\Users\HomePC\OneDrive - Piemonte Construtora\PLANEJAMENTO PIEMONTE"
]

UPLOADED_PROJECTS_DIR = os.path.abspath(
    os.getenv("PROJECTS_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "data", "projects"))
)

def scan_piemonte_projects(base_paths: List[str] = None) -> List[Dict[str, Any]]:
    """
    Scans both local uploaded projects directory (backend/data/projects)
    and any existing Piemonte network/OneDrive directories.
    """
    projects_dict: Dict[str, Dict[str, Any]] = {}
    
    # 1. Scan Uploaded / Standalone projects directory
    if os.path.exists(UPLOADED_PROJECTS_DIR):
        for entry in os.scandir(UPLOADED_PROJECTS_DIR):
            if entry.is_dir() and not entry.name.startswith("."):
                proj_name = entry.name
                proj_id = proj_name.lower().replace(" ", "_")
                
                # Check for project.json metadata
                meta_path = os.path.join(entry.path, "project.json")
                custom_name = None
                if os.path.exists(meta_path):
                    try:
                        with open(meta_path, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                            custom_name = meta.get("name")
                            if meta.get("id"):
                                proj_id = meta["id"]
                    except Exception:
                        pass
                
                final_name = custom_name or proj_name.replace("_", " ").title()
                
                # Scan for .xlsx files
                files = []
                for f in os.scandir(entry.path):
                    if f.is_file() and f.name.endswith(".xlsx") and not f.name.startswith("~$"):
                        files.append({
                            "filename": f.name,
                            "path": f.path,
                            "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                            "modified_time": f.stat().st_mtime
                        })
                
                files.sort(key=lambda x: x["modified_time"], reverse=True)
                if files:
                    projects_dict[proj_id] = {
                        "id": proj_id,
                        "name": final_name,
                        "folder_name": entry.name,
                        "path": entry.path,
                        "has_ff": len(files) > 0,
                        "files": files,
                        "latest_file": files[0] if files else None,
                        "is_uploaded": True
                    }
            elif entry.is_file() and entry.name.endswith(".xlsx") and not entry.name.startswith("~$"):
                # Single .xlsx directly in data/projects
                base_name = os.path.splitext(entry.name)[0]
                proj_id = base_name.lower().replace(" ", "_")
                files = [{
                    "filename": entry.name,
                    "path": entry.path,
                    "size_mb": round(entry.stat().st_size / (1024 * 1024), 2),
                    "modified_time": entry.stat().st_mtime
                }]
                projects_dict[proj_id] = {
                    "id": proj_id,
                    "name": base_name.replace("_", " ").title(),
                    "folder_name": base_name,
                    "path": entry.path,
                    "has_ff": True,
                    "files": files,
                    "latest_file": files[0],
                    "is_uploaded": True
                }

    # 2. Scan external / Piemonte directories if they exist
    if base_paths is None:
        base_paths = DEFAULT_SEARCH_PATHS
        
    for base in base_paths:
        if not os.path.exists(base):
            continue
            
        # Scan specifically for PLATEA or other planning project folders
        for entry in os.scandir(base):
            if entry.is_dir() and "PLATEA" in entry.name.upper():
                raw_name = entry.name
                proj_name = raw_name.replace("PLANEJAMENTO", "").strip()
                if not proj_name:
                    proj_name = "PLATEA"
                    
                ff_dir = os.path.join(entry.path, "1.Longo Prazo", "2.Físico-Financeiro")
                files = []
                if os.path.exists(ff_dir):
                    for f in os.scandir(ff_dir):
                        if f.is_file() and f.name.endswith(".xlsx") and not f.name.startswith("~$"):
                            files.append({
                                "filename": f.name,
                                "path": f.path,
                                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                                "modified_time": f.stat().st_mtime
                            })
                
                files.sort(key=lambda x: x["modified_time"], reverse=True)
                proj_id = proj_name.lower().replace(" ", "_")
                
                if proj_id not in projects_dict:
                    projects_dict[proj_id] = {
                        "id": proj_id,
                        "name": proj_name,
                        "folder_name": raw_name,
                        "path": entry.path,
                        "has_ff": len(files) > 0,
                        "files": files,
                        "latest_file": files[0] if files else None,
                        "is_uploaded": False
                    }
                else:
                    existing_paths = {f["path"] for f in projects_dict[proj_id]["files"]}
                    for f in files:
                        if f["path"] not in existing_paths:
                            projects_dict[proj_id]["files"].append(f)
                    projects_dict[proj_id]["files"].sort(key=lambda x: x["modified_time"], reverse=True)
                    projects_dict[proj_id]["latest_file"] = projects_dict[proj_id]["files"][0] if projects_dict[proj_id]["files"] else None

    # Sort projects alphabetically
    result = list(projects_dict.values())
    result.sort(key=lambda x: x["name"])
    return result

if __name__ == "__main__":
    projs = scan_piemonte_projects()
    print(f"Total projects found: {len(projs)}")
    for p in projs:
        latest = p['latest_file']['filename'] if p['latest_file'] else 'None'
        print(f"- {p['name']} ({len(p['files'])} FF files) | Latest: {latest}")
