# handler.py
import traceback
from enum import Enum
import numpy as np
import re
import c4d

class PlasticityIdUniquenessScope(Enum):
    ITEM = 0
    GROUP = 1
    EMPTY = 2

class ObjectType(Enum):
    SOLID = 0
    SHEET = 1
    WIRE = 2
    GROUP = 5
    EMPTY = 6

class SceneHandler:
    def __init__(self, plasticity_ui=None):
        self.connected = False
        self.plasticity_ui = plasticity_ui  # Optional UI reference
        self.files = {}

    def sanitize_name(self, name):
        """Sanitizes a string to remove invalid characters."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name) if isinstance(name, str) else ""

    def on_connect(self):
        """Called when the client connects to the server."""
        self.connected = True
        self.files = {}
        print("✅ Connected to Plasticity server")
        if self.plasticity_ui and hasattr(self.plasticity_ui, 'update_ui_connected'):
            self.plasticity_ui.update_ui_connected()

    def on_disconnect(self):
        """Called when the client disconnects from the server."""
        self.connected = False
        self.files = {}
        print("❌ Disconnected from Plasticity server")
        if self.plasticity_ui and hasattr(self.plasticity_ui, 'update_ui_disconnected'):
            self.plasticity_ui.update_ui_disconnected()

    def on_new_file(self, filename):
        """Called when a new file is received from Plasticity."""
        print(f"📄 New file received: {filename}")
        self.files[filename] = {
            PlasticityIdUniquenessScope.ITEM: {},
            PlasticityIdUniquenessScope.GROUP: {}
        }


    def on_new_version(self, filename, version):
        """Called when a new version of a file is received."""
        print(f"🔄 New version {version} received for file: {filename}")

    def on_transaction(self, transaction):
        """Called when a transaction message is received."""
        try:
            filename = transaction.get("filename", "unknown")
            version = transaction.get("version", 0)
            print(f"📝 Transaction received for {filename} (v{version})")

            if filename not in self.files:
                self.on_new_file(filename)

            inbox = self.__prepare(filename)

            if "delete" in transaction:
                print(f"🗑️ Deleted {len(transaction['delete'])} objects")
                for pid in transaction["delete"]:
                    self.__delete_object(filename, version, pid)

            if "add" in transaction:
                print(f"➕ Added {len(transaction['add'])} objects")
                print("send to replace objects")
                self.__replace_objects(filename, inbox, version, transaction["add"])

            if "update" in transaction:
                print(f"✏️ Updated {len(transaction['update'])} objects")
                self.__replace_objects(filename, inbox, version, transaction["update"])

        except Exception as e:
            print(f"❌ Error processing transaction: {e}")
            traceback.print_exc()


    def on_list(self, message):
        """Called when a list message is received (full sync)."""
        print("📋 List message received")

        try:
            filename = message.get("filename", "unknown")
            version = message.get("version", 0)
            print(f"📝 Transaction received for {filename} (v{version})")
            if filename not in self.files:
                self.on_new_file(filename)

            inbox = self.__prepare(filename)

            all_items = set()
            all_groups = set()

            if "add" in message:
                for item in message["add"]:
                    if item["type"] == ObjectType.GROUP.value:
                        all_groups.add(item["id"])
                    else:
                        all_items.add(item["id"])

                self.__replace_objects(filename, inbox, version, message["add"])

            # Clean up deleted ITEMs
            to_delete = []
            for plasticity_id in self.files[filename][PlasticityIdUniquenessScope.ITEM]:
                if plasticity_id not in all_items:
                    to_delete.append(plasticity_id)
            for plasticity_id in to_delete:
                self.__delete_object(filename, version, plasticity_id)

            # Clean up deleted GROUPs
            to_delete = []
            for plasticity_id in self.files[filename][PlasticityIdUniquenessScope.GROUP]:
                if plasticity_id not in all_groups:
                    to_delete.append(plasticity_id)
            for plasticity_id in to_delete:
                self.__delete_group(filename, version, plasticity_id)

            c4d.EventAdd()

        except Exception as e:
            print(f"❌ Error processing list message: {e}")
            traceback.print_exc()



    def on_refacet(self, filename, version, plasticity_ids, versions, faces, positions, indices, normals, groups, face_ids):
        """Called when a refacet message is received."""
        print(f"🔷 Refacet received for {filename} (v{version})")
        print(f"Affected objects: {plasticity_ids}")

        try:
            self.__prepare(filename)

            for i in range(len(plasticity_ids)):
                plasticity_id = plasticity_ids[i]
                obj = self.files[filename][PlasticityIdUniquenessScope.ITEM].get(plasticity_id)
                if not obj:
                    print(f"Object with plasticity_id {plasticity_id} not found.")
                    continue

                face = faces[i] if faces else None
                position = positions[i]
                index = indices[i]
                normal = normals[i]
                group = groups[i]
                face_id = face_ids[i]

                self.__update_mesh_ngons(obj, version, face, position, index, normal, group, face_id)

        except Exception as e:
            print(f"Error processing refacet: {e}")
            traceback.print_exc()


    def report(self, level, message):
        """Report messages at different severity levels."""
        if level.lower() == 'error':
            print(f"[ERROR] {message}")
        elif level.lower() == 'warning':
            print(f"[WARNING] {message}")
        else:
            print(f"[INFO] {message}")


    def __create_mesh(self, name, vertices, indices, normals, groups, face_ids):
        try:
            print(f"Creating mesh: {name}")

            # Build vertex list
            points = []
            for i in range(0, len(vertices), 3):
                x = float(vertices[i])
                y = float(vertices[i + 1])
                z = float(vertices[i + 2])
                points.append(c4d.Vector(x, y, z))

            # Build polygon list
            polygons = []
            try:
                face_array = np.array(indices, dtype=np.int32).reshape(-1, 3)
                for face in face_array:
                    polygons.append(c4d.CPolygon(face[0], face[1], face[2], face[2]))  # triangle
            except Exception as e:
                print(f"[create_mesh] Error reshaping/processing faces: {e}")
                return None

            mesh = c4d.PolygonObject(len(points), len(polygons))
            mesh.SetAllPoints(points)
            for i, poly in enumerate(polygons):
                mesh.SetPolygon(i, poly)

            mesh.Message(c4d.MSG_UPDATE)
            return mesh

        except Exception as e:
            print(f"[create_mesh] Error creating mesh '{name}': {e}")
            traceback.print_exc()
            return None


    def __update_object_and_mesh(self, obj, object_type, version, name, verts, indices, normals, groups, face_ids, parent_id):
        try:
            print(f"[update] Updating object '{name}' with new geometry.")

            # Convert vertices from flat array to c4d.Vector list
            points = []
            for i in range(0, len(verts), 3):
                x = float(verts[i])
                y = float(verts[i + 1])
                z = float(verts[i + 2])
                points.append(c4d.Vector(x, y, z))

            # Convert indices to c4d.CPolygon list
            polygons = []
            try:
                face_array = np.array(indices, dtype=np.int32).reshape(-1, 3)
                for face in face_array:
                    polygons.append(c4d.CPolygon(face[0], face[1], face[2], face[2]))  # triangle padded
            except Exception as e:
                print(f"[update_object_and_mesh] Failed to parse face indices: {e}")
                return

            # Ensure object is a PolygonObject
            if not isinstance(obj, c4d.PolygonObject):
                print("[update_object_and_mesh] Target object is not a PolygonObject.")
                return

            # Resize and update geometry
            obj.ResizeObject(len(points), len(polygons))
            obj.SetAllPoints(points)
            for i, poly in enumerate(polygons):
                obj.SetPolygon(i, poly)

            obj.Message(c4d.MSG_UPDATE)
            c4d.EventAdd()

        except Exception as e:
            print(f"❌ Error in __update_object_and_mesh: {e}")
            traceback.print_exc()






    def __create_group(self, name, matrix=None, parent=None):
        """
        Creates a group (Null object) and inserts into the scene.

        Args:
            name (str): Group name.
            matrix (optional): 4x4 transform matrix (row-major, flat or nested).
            parent (BaseObject or None): Optional parent object.

        Returns:
            group (BaseObject): The created group node.
        """
        try:
            group = c4d.BaseObject(c4d.Onull)
            group.SetName(name)

            if matrix:
                try:
                    if isinstance(matrix[0], list):  # nested matrix
                        flat = [v for row in matrix for v in row]
                    else:
                        flat = matrix

                    tm = c4d.Matrix()
                    tm.v1 = c4d.Vector(flat[0], flat[1], flat[2])
                    tm.v2 = c4d.Vector(flat[4], flat[5], flat[6])
                    tm.v3 = c4d.Vector(flat[8], flat[9], flat[10])
                    tm.off = c4d.Vector(flat[12], flat[13], flat[14])
                    group.SetMg(tm)
                except Exception as e:
                    print(f"[__create_group] Invalid matrix for {name}: {e}")

            if parent:
                group.InsertUnder(parent)
            else:
                c4d.documents.GetActiveDocument().InsertObject(group)

            c4d.EventAdd()
            print(f"[__create_group] Created group: {name}")
            return group

        except Exception as e:
            print(f"[__create_group] Failed to create group '{name}': {e}")
            import traceback
            traceback.print_exc()
            return None


    def __replace_objects(self, filename, inbox_collection, version, objects):
        """
        Replace or create objects/groups from Plasticity transaction data.
        """
        doc = c4d.documents.GetActiveDocument()
        scale = 1.0

        # First pass: create or update
        for item in objects:
            object_type = item["type"]
            plasticity_id = item["id"]
            name = item["name"]
            parent_id = item["parent_id"]
            verts = item["vertices"]
            indices = item["faces"]
            normals = item["normals"]
            groups = item["groups"]
            face_ids = item["face_ids"]

            if object_type in [ObjectType.SOLID.value, ObjectType.SHEET.value]:
                if plasticity_id not in self.files[filename][PlasticityIdUniquenessScope.ITEM]:
                    print("Before create")
                    mesh = self.__create_mesh(name, verts, indices, normals, groups, face_ids)
                    obj = self.__add_object(filename, object_type, plasticity_id, name, mesh)
                    if obj:
                        obj.SetAbsScale(c4d.Vector(scale, scale, scale))
                        self.files[filename][PlasticityIdUniquenessScope.ITEM][plasticity_id] = obj
                else:
                    obj = self.files[filename][PlasticityIdUniquenessScope.ITEM][plasticity_id]
                    self.__update_object_and_mesh(obj, object_type, version, name, verts, indices, normals, groups, face_ids, parent_id)

            elif object_type == ObjectType.GROUP.value:
                if plasticity_id > 0:
                    if plasticity_id not in self.files[filename][PlasticityIdUniquenessScope.GROUP]:
                        group = self.__create_group(name)
                        # Tag only non-Inbox groups
                        if group.GetName().lower() != "inbox":
                            bc = group.GetDataInstance()
                            bc.SetInt32(1001, plasticity_id)
                            bc.SetString(1002, filename)
                            self.files[filename][PlasticityIdUniquenessScope.GROUP][plasticity_id] = group
                    else:
                        group = self.files[filename][PlasticityIdUniquenessScope.GROUP][plasticity_id]
                        group.SetName(name)

        # Second pass: parenting and visibility
        for item in objects:
            object_type = item["type"]
            plasticity_id = item["id"]
            parent_id = item["parent_id"]
            flags = item["flags"]

            is_hidden = flags & 1
            is_visible = flags & 2
            is_selectable = flags & 4

            if plasticity_id == 0:
                continue

            scope = PlasticityIdUniquenessScope.GROUP if object_type == ObjectType.GROUP.value else PlasticityIdUniquenessScope.ITEM
            obj = self.files[filename][scope].get(plasticity_id)
            if not obj:
                print(f"[__replace_objects] Missing object {plasticity_id}")
                continue

            parent = self.files[filename][PlasticityIdUniquenessScope.GROUP].get(parent_id) if parent_id > 0 else inbox_collection

            if parent:
                obj.InsertUnder(parent)
            else:
                doc.InsertObject(obj)

            # Visibility
            if object_type == ObjectType.GROUP.value:
                obj[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = 1 if is_visible else 0
                obj[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = 1 if is_visible else 0
            else:
                obj.SetEditorMode(c4d.MODE_ON if is_visible else c4d.MODE_OFF)
                obj.SetRenderMode(c4d.MODE_ON if is_visible else c4d.MODE_OFF)

        c4d.EventAdd()




    def __inbox_for_filename(self, filename):
        """
        Returns or creates the Plasticity collection for this filename.
        Creates a "Plasticity" top group and a child named after filename, with an "Inbox" group inside.
        """
        doc = c4d.documents.GetActiveDocument()
        plasticity_root = doc.SearchObject("Plasticity")

        if not plasticity_root:
            plasticity_root = c4d.BaseObject(c4d.Onull)
            plasticity_root.SetName("Plasticity")
            doc.InsertObject(plasticity_root)

        filename_group = plasticity_root.GetDown()
        while filename_group:
            if filename_group.GetName() == filename:
                break
            filename_group = filename_group.GetNext()
        if not filename_group:
            filename_group = c4d.BaseObject(c4d.Onull)
            filename_group.SetName(filename)
            filename_group.InsertUnder(plasticity_root)

        inbox_group = filename_group.GetDown()
        while inbox_group:
            if inbox_group.GetName().lower() == "inbox":
                break
            inbox_group = inbox_group.GetNext()
        if not inbox_group:
            inbox_group = c4d.BaseObject(c4d.Onull)
            inbox_group.SetName("Inbox")
            inbox_group.InsertUnder(filename_group)

        return inbox_group


    def __prepare(self, filename):
        """
        Scans the existing scene structure and builds up the ID -> object mapping.
        Returns the inbox group where new objects should be inserted.
        """
        inbox_group = self.__inbox_for_filename(filename)

        existing_objects = {
            PlasticityIdUniquenessScope.ITEM: {},
            PlasticityIdUniquenessScope.GROUP: {}
        }

        def walk_hierarchy(obj):
            objs = []
            groups = []
            while obj:
                bc = obj.GetDataInstance()
                pid = bc.GetInt32(1001) if bc else None

                # Skip groups with no ID or system containers like Inbox
                if pid:
                    if obj.CheckType(c4d.Onull):
                        if obj.GetName().lower() != "inbox":
                            groups.append((pid, obj))
                    else:
                        objs.append((pid, obj))

                if obj.GetDown():
                    sub_objs, sub_groups = walk_hierarchy(obj.GetDown())
                    objs += sub_objs
                    groups += sub_groups

                obj = obj.GetNext()

            return objs, groups

        objects, groups = walk_hierarchy(inbox_group)

        for pid, obj in objects:
            existing_objects[PlasticityIdUniquenessScope.ITEM][pid] = obj
        for pid, group in groups:
            existing_objects[PlasticityIdUniquenessScope.GROUP][pid] = group

        self.files[filename] = existing_objects
        return inbox_group



    def __update_mesh_ngons(self, obj, version, faces, verts, indices, normals, groups, face_ids):
        """Update an existing mesh object with new ngon geometry."""
        try:
            if not isinstance(obj, c4d.BaseObject):
                print(f"Invalid object passed to __update_mesh_ngons: {obj}")
                return

            mesh = obj.GetDataInstance()
            if not mesh:
                print(f"Object has no data: {obj}")
                return

            doc = c4d.documents.GetActiveDocument()
            doc.StartUndo()
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)

            # Convert verts to Vector list
            vert_count = len(verts) // 3
            points = [c4d.Vector(verts[i], verts[i+1], verts[i+2]) for i in range(0, len(verts), 3)]
            obj.ResizeObject(vert_count, len(faces))
            obj.SetAllPoints(points)

            # Build polygons
            polygons = []
            current = 0
            for face_vert_count in faces:
                if face_vert_count == 3:
                    polygons.append(c4d.CPolygon(indices[current], indices[current+1], indices[current+2]))
                elif face_vert_count == 4:
                    polygons.append(c4d.CPolygon(indices[current], indices[current+1], indices[current+2], indices[current+3]))
                else:
                    print(f"Ngon with {face_vert_count} verts not directly supported here. Skipped.")
                current += face_vert_count

            obj.SetPolygonCount(len(polygons))
            for i, poly in enumerate(polygons):
                obj.SetPolygon(i, poly)

            obj.Message(c4d.MSG_UPDATE)
            doc.AddUndo(c4d.UNDOTYPE_CHANGE, obj)
            doc.EndUndo()
            c4d.EventAdd()

            # Store meta
            obj.SetName(obj.GetName())  # force rename refresh
            obj.SetUserDataContainer([("plasticity_version", version)])
            obj.SetEditorMode(c4d.MODE_ON)
            obj.SetRenderMode(c4d.MODE_ON)

            obj.SetDirty(c4d.DIRTY_DATA)
            print(f"Ngon mesh updated: {obj.GetName()}")

        except Exception as e:
            print(f"Error in __update_mesh_ngons: {e}")
            traceback.print_exc()

    def __delete_object(self, obj):
        """Delete a single object from the scene."""
        try:
            if obj is None:
                return
            obj.Remove()
            c4d.EventAdd()
        except Exception as e:
            print(f"Error in __delete_object: {e}")
            import traceback
            traceback.print_exc()


    def __delete_group(self, filename, version, plasticity_id):
        """Deletes a group (null object or similar) from the scene and internal registry."""
        try:
            group = self.files[filename][PlasticityIdUniquenessScope.GROUP].pop(plasticity_id, None)
            if group:
                doc = c4d.documents.GetActiveDocument()
                doc.StartUndo()
                doc.AddUndo(c4d.UNDOTYPE_DELETE, group)
                group.Remove()  # ← Fixed
                doc.EndUndo()
                c4d.EventAdd()
                print(f"🗑️ Deleted group: {group.GetName()}")
            else:
                print(f"Group with id {plasticity_id} not found in file: {filename}")
        except Exception as e:
            print(f"Error in __delete_group: {e}")
            import traceback
            traceback.print_exc()


    def __add_object(self, filename, object_type, plasticity_id, name, mesh):
        """Adds a new mesh object to the document and internal files registry."""
        try:
            mesh.SetName(name)
            mesh.SetEditorMode(c4d.MODE_UNDEF)
            mesh.SetRenderMode(c4d.MODE_UNDEF)
            mesh.SetBit(c4d.BIT_ACTIVE)

            mesh.SetAbsPos(c4d.Vector(0))
            mesh.SetAbsRot(c4d.Vector(0))
            mesh.SetAbsScale(c4d.Vector(1))

            # Store metadata in the BaseContainer
            bc = mesh.GetDataInstance()
            bc.SetInt32(1001, plasticity_id)  # Plasticity ID
            bc.SetString(1002, filename)      # File source name

            self.files[filename][PlasticityIdUniquenessScope.ITEM][plasticity_id] = mesh

            doc = c4d.documents.GetActiveDocument()
            doc.InsertObject(mesh)
            c4d.EventAdd()

            print(f"Added object: {name} (ID {plasticity_id})")
            return mesh

        except Exception as e:
            print(f"Error in __add_object: {e}")
            import traceback
            traceback.print_exc()
            return None
