import os
import io
import json
from starlette.testclient import TestClient
from app import app
import database

def run_tests():
    print("--- 1. Testing Database & 10-Node Engine Multi-Webhook Configuration ---")
    with TestClient(app) as client:
        # Test /api/info
        res = client.get("/api/info")
        assert res.status_code == 200, f"/api/info failed: {res.text}"
        info = res.json()
        print("API Info:", info)
        assert info["webhook_configured"] is True
        assert info["node_count"] == 10, f"Expected 10 nodes, got {info['node_count']}"
        assert len(info["nodes"]) == 10
        assert "stats" in info

        # Test /api/settings
        settings_res = client.get("/api/settings")
        assert settings_res.status_code == 200
        settings_data = settings_res.json()
        assert len(settings_data["storage_nodes"]) == 10
        assert settings_data["node_count"] == 10
        print("Verified /api/settings returns 10 storage nodes!")

        # Test create folder
        f_res = client.post("/api/folders", json={"name": "Documents"})
        assert f_res.status_code == 200, f"Create folder failed: {f_res.text}"
        folder_data = f_res.json()
        folder_id = folder_data["id"]
        print("Created folder:", folder_data["name"], folder_id)

        # Test list folders
        f_list_res = client.get("/api/folders")
        assert f_list_res.status_code == 200
        folders = f_list_res.json()["folders"]
        assert any(f["id"] == folder_id for f in folders), "Created folder not in list"

        # Test breadcrumbs
        bc_res = client.get(f"/api/folders/{folder_id}/breadcrumbs")
        assert bc_res.status_code == 200
        breadcrumbs = bc_res.json()["breadcrumbs"]
        print("Breadcrumbs:", breadcrumbs)
        assert len(breadcrumbs) == 2

        # Test file upload (Small file: single chunk distributed round-robin)
        sample_content = b"Hello, this is a test personal cloud storage document with 10-node engine!"
        upload_res = client.post(
            "/api/upload",
            files={"file": ("hello.txt", sample_content, "text/plain")},
            data={"folder_id": folder_id}
        )
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
        upload_data = upload_res.json()
        print("Upload result (small):", upload_data)
        file_id = upload_data["file"]["id"]
        assert upload_data["chunks_count"] == 1
        assert upload_data["node_count"] == 10

        # Check chunk structure in database
        db_file = client.get(f"/api/files/{file_id}").json()
        print("DB File Chunks:", db_file["chunk_message_ids"])
        assert isinstance(db_file["chunk_message_ids"], list)
        chunk0 = db_file["chunk_message_ids"][0]
        assert "message_id" in chunk0
        assert "node_url" in chunk0

        # Test file streaming
        stream_res = client.get(f"/api/files/{file_id}/stream")
        assert stream_res.status_code == 200
        assert stream_res.content == sample_content
        print("Streaming verified, content matched!")

        # Test file download
        dl_res = client.get(f"/api/files/{file_id}/download")
        assert dl_res.status_code == 200
        assert dl_res.content == sample_content
        assert "attachment" in dl_res.headers.get("content-disposition", "")
        print("Download verified, content-disposition correct!")

        # Test share link
        share_res = client.get(f"/api/share/{file_id}")
        assert share_res.status_code == 200
        assert share_res.content == sample_content
        print("Public Share link verified!")

        # Test Large file chunking (> 19MB simulation) distributed across multiple nodes
        print("--- 2. Testing 10-Node Parallel Chunking (> 19MB) ---")
        chunk_test_size = 20 * 1024 * 1024 # 20MB -> 2 chunks
        pattern = b"MultiNode2026!__" * (chunk_test_size // 16)
        large_upload_res = client.post(
            "/api/upload",
            files={"file": ("large_cluster_video.mp4", pattern, "video/mp4")},
            data={"folder_id": folder_id}
        )
        assert large_upload_res.status_code == 200, f"Large upload failed: {large_upload_res.text}"
        large_upload_data = large_upload_res.json()
        print("Large file upload result:", large_upload_data)
        assert large_upload_data["chunks_count"] == 2
        large_file_id = large_upload_data["file"]["id"]

        large_db_file = client.get(f"/api/files/{large_file_id}").json()
        large_chunks = large_db_file["chunk_message_ids"]
        print("Large File Chunks distribution:")
        for idx, ch in enumerate(large_chunks):
            print(f"  Chunk {idx}: Node {ch.get('node_index')} -> message {ch.get('message_id')}")

        # Stream large file and verify reassembled bytes
        large_stream_res = client.get(f"/api/files/{large_file_id}/stream")
        assert large_stream_res.status_code == 200
        assert len(large_stream_res.content) == len(pattern)
        assert large_stream_res.content == pattern
        print("Reassembled 20MB multi-chunk file verified with byte-level precision!")

        # Test Trashing and Restoring
        print("--- 3. Testing Trash, Restore, and Permanent Deletion ---")
        trash_res = client.post(f"/api/files/{file_id}/trash")
        assert trash_res.status_code == 200

        # Verify not in normal list
        list_active = client.get(f"/api/files?folder_id={folder_id}").json()["files"]
        assert not any(f["id"] == file_id for f in list_active)

        # Restore
        restore_res = client.post(f"/api/files/{file_id}/restore")
        assert restore_res.status_code == 200
        print("Trash and restore verified!")

        # Permanent delete
        del_res = client.delete(f"/api/files/{file_id}")
        assert del_res.status_code == 200
        del_large_res = client.delete(f"/api/files/{large_file_id}")
        assert del_large_res.status_code == 200

        # Clean up folder
        del_folder_res = client.delete(f"/api/folders/{folder_id}")
        assert del_folder_res.status_code == 200

        # Test settings update & test endpoint
        print("--- 4. Testing Multi-Node Test & Settings Validation ---")
        test_res = client.post("/api/settings/test", json={"url": "https://invalid-webhook.com"})
        assert test_res.status_code == 200
        assert test_res.json()["success"] is False

        # Test all nodes ping
        test_all_res = client.post("/api/settings/test", json={"test_all": True})
        assert test_all_res.status_code == 200
        test_all_data = test_all_res.json()
        print("Test All Nodes result:", test_all_data["message"])
        assert test_all_data["success"] is True
        assert len(test_all_data["nodes"]) == 10

        # Test static index.html serving
        html_res = client.get("/")
        assert html_res.status_code == 200
        assert "AeroVault" in html_res.text
        assert "Devanarayanan" in html_res.text
        assert "bottom-nav-bar" in html_res.text
        assert "settingsView" in html_res.text
        assert "themeDarkCard" in html_res.text
        assert "discord" not in html_res.text.lower()
        print("Static frontend serving verified with 100% white-labeling, bottom nav, and Settings view!")

        print("--- ALL 10-NODE MULTI-WEBHOOK BACKEND & FRONTEND TESTS PASSED SUCCESSFULLY! ---")

if __name__ == "__main__":
    run_tests()
