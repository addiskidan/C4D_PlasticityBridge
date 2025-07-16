import threading
import asyncio
import websockets
import weakref
import traceback
import struct
import re

import sys
import os

python311_path = os.path.join(os.path.dirname(__file__), "resource", "modules", "python", "libs", "python311", "site-packages")
if os.path.exists(python311_path) and python311_path not in sys.path:
    sys.path.insert(0, python311_path)


import numpy as np
from enum import Enum

class MessageType(Enum):
    TRANSACTION_1 = 0
    ADD_1 = 1
    UPDATE_1 = 2
    DELETE_1 = 3
    MOVE_1 = 4
    ATTRIBUTE_1 = 5

    NEW_VERSION_1 = 10
    NEW_FILE_1 = 11

    LIST_ALL_1 = 20
    LIST_SOME_1 = 21
    LIST_VISIBLE_1 = 22
    SUBSCRIBE_ALL_1 = 23
    SUBSCRIBE_SOME_1 = 24
    UNSUBSCRIBE_ALL_1 = 25
    REFACET_SOME_1 = 26

class ObjectType(Enum):
    SOLID = 0
    SHEET = 1
    WIRE = 2
    GROUP = 5
    EMPTY = 6

class FacetShapeType(Enum):
    ANY = 20500
    CUT = 20501
    CONVEX = 20502

class PlasticityClient:
    def __init__(self, handler=None):
        self.handler = handler
        self.connected = False
        self.websocket = None
        self.server = None
        self.filename = None
        self.message_id = 0
        self.subscribed = False
        self.loop = None
        self.thread = None

    def connect(self, server):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.connect_thread, args=(server,))
        self.thread.daemon = True
        self.thread.start()

    def connect_thread(self, server):
        async def run():
            try:
                await self.connect_async(server)
            except Exception as e:
                print("[client.py] Async task failed:", e)
                traceback.print_exc()

        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(run())

    async def connect_async(self, server):
        try:
            print(f"[client.py] Trying to connect to ws://{server}...")
            ws = await asyncio.wait_for(websockets.connect(f"ws://{server}"), timeout=5)
            print("[client.py] WebSocket connected!")

            self.connected = True
            self.websocket = weakref.proxy(ws)
            self.server = server
            self.message_id = 0

            if self.handler:
                self.handler.on_connect()

            try:
                while True:
                    message = await ws.recv()
                    await self.on_message(ws, message)
            except websockets.ConnectionClosed:
                print("[client.py] WebSocket closed.")
            finally:
                self.connected = False
                self.websocket = None
                self.filename = None
                self.subscribed = False
                if self.handler:
                    self.handler.on_disconnect()

        except asyncio.TimeoutError:
            print("[client.py] Connection timed out.")
            if self.handler:
                self.handler.on_disconnect()
        except Exception as e:
            print("[client.py] Connection error:", e)
            traceback.print_exc()
            if self.handler:
                self.handler.on_disconnect()

    # Message handling methods
    async def on_message(self, ws, message):
        if isinstance(message, str):
            print("[client.py] Warning: received unexpected text message:", message)
            return

        view = memoryview(message)
        offset = 0
        try:
            message_type = MessageType(int.from_bytes(view[offset:offset + 4], 'little'))
        except Exception:
            print("[client.py] Malformed message header.")
            return

        offset += 4

        if message_type == MessageType.TRANSACTION_1:
            self.__on_transaction(view, offset, update_only=True)
        elif message_type == MessageType.LIST_ALL_1 or message_type == MessageType.LIST_SOME_1 or message_type == MessageType.LIST_VISIBLE_1:
            self.__on_list_message(view, offset)
        elif message_type == MessageType.NEW_VERSION_1:
            self.__on_new_version(view, offset)
        elif message_type == MessageType.NEW_FILE_1:
            self.__on_new_file(view, offset)
        elif message_type == MessageType.REFACET_SOME_1:
            self.__on_refacet(view, offset)

    def __on_transaction(self, view, offset, update_only):
        filename_length = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        filename = view[offset:offset + filename_length].tobytes().decode('utf-8')
        offset += filename_length
        self.filename = filename

        padding = (4 - (filename_length % 4)) % 4
        offset += padding

        version = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4

        num_messages = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4

        transaction = {
            "filename": filename,
            "version": version,
            "delete": [],
            "add": [],
            "update": []
        }

        for _ in range(num_messages):
            item_length = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            self.on_message_item(view[offset:offset + item_length], transaction)
            offset += item_length

        if self.handler:
            if update_only:
                self.handler.on_transaction(transaction)
            else:
                self.handler.on_list(transaction)

    def __on_list_message(self, view, offset):
        print("on list message")
        message_id = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        code = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4

        if code != 200:
            print(f"List all failed with code: {code}")
            return

        self.__on_transaction(view, offset, update_only=False)

    def __on_new_version(self, view, offset):
        filename_length = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        filename = view[offset:offset + filename_length].tobytes().decode('utf-8')
        offset += filename_length
        self.filename = filename

        padding = (4 - (filename_length % 4)) % 4
        offset += padding

        version = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4

        if self.handler:
            self.handler.on_new_version(filename, version)

    def __on_new_file(self, view, offset):
        filename_length = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        filename = view[offset:offset + filename_length].tobytes().decode('utf-8')
        offset += filename_length
        self.filename = filename

        if self.handler:
            self.handler.on_new_file(filename)

    def __on_refacet(self, view, offset):
        message_id = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        code = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4

        if code != 200:
            print(f"Refacet failed with code: {code}")
            return

        filename_length = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        filename = view[offset:offset + filename_length].tobytes().decode('utf-8')
        offset += filename_length
        self.filename = filename

        padding = (4 - (filename_length % 4)) % 4
        offset += padding

        file_version = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        num_items = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4

        plasticity_ids = []
        versions = []
        faces = []
        positions = []
        indices = []
        normals = []
        groups = []
        face_ids = []

        for _ in range(num_items):
            plasticity_id = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            version = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            num_face_facets = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            face = np.frombuffer(view[offset:offset + num_face_facets * 4], dtype=np.int32)
            offset += num_face_facets * 4
            num_positions = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            position = np.frombuffer(view[offset:offset + num_positions * 4], dtype=np.float32)
            offset += num_positions * 4
            num_index = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            index = np.frombuffer(view[offset:offset + num_index * 4], dtype=np.int32)
            offset += num_index * 4
            num_normals = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            normal = np.frombuffer(view[offset:offset + num_normals * 4], dtype=np.float32)
            offset += num_normals * 4
            num_groups = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            group = np.frombuffer(view[offset:offset + num_groups * 4], dtype=np.int32).tolist()
            offset += num_groups * 4
            num_face_ids = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            face_id = np.frombuffer(view[offset:offset + num_face_ids * 4], dtype=np.int32).tolist()
            offset += num_face_ids * 4

            plasticity_ids.append(plasticity_id)
            versions.append(version)
            faces.append(face)
            positions.append(position)
            indices.append(index)
            normals.append(normal)
            groups.append(group)
            face_ids.append(face_id)

        if self.handler:
            self.handler.on_refacet(filename, file_version, plasticity_ids,
                                   versions, faces, positions, indices, 
                                   normals, groups, face_ids)

    def on_message_item(self, view, transaction):
        offset = 0
        try:
            message_type = MessageType(int.from_bytes(view[offset:offset + 4], 'little'))
        except:
            return
        offset += 4

        if message_type == MessageType.DELETE_1:
            num_objects = int.from_bytes(view[offset:offset + 4], 'little')
            offset += 4
            transaction["delete"].extend(
                np.frombuffer(view[offset:offset + num_objects * 4], dtype=np.int32))
        elif message_type == MessageType.ADD_1:
            transaction["add"].extend(decode_objects(view[offset:], True))
        elif message_type == MessageType.UPDATE_1:
            transaction["update"].extend(decode_objects(view[offset:], True))

    # Command methods
    def list_all(self):
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.list_all_async(), self.loop).result()

    async def list_all_async(self):
        self.message_id += 1
        get_objects_message = struct.pack("<I", MessageType.LIST_ALL_1.value)
        get_objects_message += struct.pack("<I", self.message_id)
        await self.websocket.send(get_objects_message)

    def list_visible(self):
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.list_visible_async(), self.loop).result()

    async def list_visible_async(self):
        self.message_id += 1
        get_objects_message = struct.pack("<I", MessageType.LIST_VISIBLE_1.value)
        get_objects_message += struct.pack("<I", self.message_id)
        await self.websocket.send(get_objects_message)

    def subscribe_all(self):
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.subscribe_all_async(), self.loop).result()
            self.subscribed = True

    async def subscribe_all_async(self):
        self.message_id += 1
        subscribe_message = struct.pack("<I", MessageType.SUBSCRIBE_ALL_1.value)
        subscribe_message += struct.pack("<I", self.message_id)
        await self.websocket.send(subscribe_message)

    def unsubscribe_all(self):
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.unsubscribe_all_async(), self.loop).result()
            self.subscribed = False

    async def unsubscribe_all_async(self):
        self.message_id += 1
        subscribe_message = struct.pack("<I", MessageType.UNSUBSCRIBE_ALL_1.value)
        subscribe_message += struct.pack("<I", self.message_id)
        await self.websocket.send(subscribe_message)

    def subscribe_some(self, filename, plasticity_ids):
        if self.connected and plasticity_ids:
            asyncio.run_coroutine_threadsafe(
                self.subscribe_some_async(filename, plasticity_ids), self.loop).result()

    async def subscribe_some_async(self, filename, plasticity_ids):
        if not plasticity_ids:
            return

        self.message_id += 1
        subscribe_message = struct.pack("<I", MessageType.SUBSCRIBE_SOME_1.value)
        subscribe_message += struct.pack("<I", self.message_id)
        subscribe_message += struct.pack("<I", len(filename))
        subscribe_message += struct.pack(f"<{len(filename)}s", filename.encode('utf-8'))
        padding = (4 - (len(filename) % 4)) % 4
        subscribe_message += struct.pack(f"<{padding}x")
        subscribe_message += struct.pack("<I", len(plasticity_ids))
        for plasticity_id in plasticity_ids:
            subscribe_message += struct.pack("<I", plasticity_id)
        await self.websocket.send(subscribe_message)

    def refacet_some(self, filename, plasticity_ids, relative_to_bbox=True, curve_chord_tolerance=0.01, 
                    curve_chord_angle=0.35, surface_plane_tolerance=0.01, surface_plane_angle=0.35, 
                    match_topology=True, max_sides=3, plane_angle=0, min_width=0, max_width=0, 
                    curve_chord_max=0, shape=FacetShapeType.CUT):
        if self.connected and plasticity_ids:
            asyncio.run_coroutine_threadsafe(
                self.refacet_some_async(filename, plasticity_ids, relative_to_bbox, curve_chord_tolerance,
                                      curve_chord_angle, surface_plane_tolerance, surface_plane_angle,
                                      match_topology, max_sides, plane_angle, min_width, max_width,
                                      curve_chord_max, shape), self.loop).result()

    async def refacet_some_async(self, filename, plasticity_ids, relative_to_bbox=True, curve_chord_tolerance=0.01, 
                               curve_chord_angle=0.35, surface_plane_tolerance=0.01, surface_plane_angle=0.35, 
                               match_topology=True, max_sides=3, plane_angle=0, min_width=0, max_width=0, 
                               curve_chord_max=0, shape=FacetShapeType.CUT):
        if not plasticity_ids:
            return

        self.message_id += 1
        refacet_message = struct.pack("<I", MessageType.REFACET_SOME_1.value)
        refacet_message += struct.pack("<I", self.message_id)
        refacet_message += struct.pack("<I", len(filename))
        refacet_message += struct.pack(f"<{len(filename)}s", filename.encode('utf-8'))
        padding = (4 - (len(filename) % 4)) % 4
        refacet_message += struct.pack(f"<{padding}x")
        refacet_message += struct.pack("<I", len(plasticity_ids))
        for plasticity_id in plasticity_ids:
            refacet_message += struct.pack("<I", plasticity_id)
        refacet_message += struct.pack("<I", relative_to_bbox)
        refacet_message += struct.pack("<f", curve_chord_tolerance)
        refacet_message += struct.pack("<f", curve_chord_angle)
        refacet_message += struct.pack("<f", surface_plane_tolerance)
        refacet_message += struct.pack("<f", surface_plane_angle)
        refacet_message += struct.pack("<I", 1 if match_topology else 0)
        refacet_message += struct.pack("<I", max_sides)
        refacet_message += struct.pack("<f", plane_angle)
        refacet_message += struct.pack("<f", min_width)
        refacet_message += struct.pack("<f", max_width)
        refacet_message += struct.pack("<f", curve_chord_max)
        refacet_message += struct.pack("<I", shape.value)

        await self.websocket.send(refacet_message)

    def disconnect(self):
        if self.connected:
            asyncio.run_coroutine_threadsafe(self.disconnect_async(), self.loop).result()

    async def disconnect_async(self):
        if self.websocket:
            await self.websocket.close()
        self.connected = False
        self.filename = None
        self.subscribed = False
        self.websocket = None
        if self.handler:
            self.handler.on_disconnect()

    def report(self, level, message):
        if self.handler:
            self.handler.report(level, message)

def decode_objects(buffer, use_pid_suffix=True):
    view = memoryview(buffer)
    num_objects = int.from_bytes(view[:4], 'little')
    offset = 4
    objects = []

    for _ in range(num_objects):
        object_type, object_id, version_id, parent_id, material_id, flags, name, vertices, faces, normals, offset, groups, face_ids = decode_object_data(
            view, offset, use_pid_suffix)
        objects.append({
            "type": object_type, 
            "id": object_id, 
            "version": version_id, 
            "parent_id": parent_id, 
            "material_id": material_id,
            "flags": flags, 
            "name": name, 
            "vertices": vertices, 
            "faces": faces, 
            "normals": normals, 
            "groups": groups, 
            "face_ids": face_ids
        })
        # print(objects)
    return objects

def decode_object_data(view, offset, use_pid_suffix=True):
    object_type = int.from_bytes(view[offset:offset + 4], 'little')
    offset += 4
    object_id = int.from_bytes(view[offset:offset + 4], 'little')
    offset += 4
    version_id = int.from_bytes(view[offset:offset + 4], 'little')
    offset += 4
    parent_id = int.from_bytes(view[offset:offset + 4], 'little', signed=True)
    offset += 4
    material_id = int.from_bytes(view[offset:offset + 4], 'little', signed=True)
    offset += 4
    flags = int.from_bytes(view[offset:offset + 4], 'little')
    offset += 4
    name_length = int.from_bytes(view[offset:offset + 4], 'little')
    offset += 4
    name = view[offset:offset + name_length].tobytes().decode('utf-8')
    offset += name_length
    name_with_id = f"{name}_{object_id}" if use_pid_suffix else name
    padding = (4 - (name_length % 4)) % 4
    offset += padding

    vertices = faces = normals = groups = face_ids = None

    if object_type == ObjectType.SOLID.value or object_type == ObjectType.SHEET.value:
        num_vertices = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        vertices = np.frombuffer(view[offset:offset + num_vertices * 12], dtype=np.float32)
        offset += num_vertices * 12
        num_faces = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        faces = np.frombuffer(view[offset:offset + num_faces * 12], dtype=np.int32)
        offset += num_faces * 12
        num_normals = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        normals = np.frombuffer(view[offset:offset + num_normals * 12], dtype=np.float32)
        offset += num_normals * 12
        num_groups = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        groups = np.frombuffer(view[offset:offset + num_groups * 4], dtype=np.int32).tolist()
        offset += num_groups * 4
        num_face_ids = int.from_bytes(view[offset:offset + 4], 'little')
        offset += 4
        face_ids = np.frombuffer(view[offset:offset + num_face_ids * 4], dtype=np.int32).tolist()
        offset += num_face_ids * 4

    final_name = name_with_id
    if final_name and final_name[0].isdigit():
        final_name = f"Null_{final_name}"

    # print(object_type, object_id, version_id, parent_id, material_id, flags, final_name, vertices, faces, normals, offset, groups, face_ids)
    return object_type, object_id, version_id, parent_id, material_id, flags, final_name, vertices, faces, normals, offset, groups, face_ids

def sanitize_name(name):
    return re.sub(r'[^a-zA-Z0-9_]', '_', name).strip() if isinstance(name, str) else ""