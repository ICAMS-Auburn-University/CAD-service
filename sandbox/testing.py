import FreeCAD
import Import
import sys
import os

def print_object_tree(obj, indent=0):
    # Recursively print the group hierarchy
    print('  ' * indent + f"{obj.Name} ({obj.Label}) [{obj.TypeId}]")
    # If the object is a group, recursively print its children
    if hasattr(obj, "Group"):
        for child in obj.Group:
            print_object_tree(child, indent+1)

def load_and_report(input_file: str):
    abs_path = os.path.abspath(input_file)
    print(f"Loading STEP file: {abs_path}")
    doc = FreeCAD.newDocument("diag_tmp")
    # Use Import.insert to preserve group structure
    Import.insert(abs_path, doc.Name)
    doc.recompute()
    print(f"STEP import complete. Document object count: {len(doc.Objects)}\n")
    print("Object hierarchy:")
    # Print the tree for all root-level objects
    for obj in doc.Objects:
        # Only print if object is not part of another group (top-level)
        if not hasattr(obj, "InList") or not obj.InList:
            print_object_tree(obj)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: freecadcmd script.py <path/to/file.step>")
        sys.exit(1)
    load_and_report(sys.argv[1])
