import os
import io
import asyncio
import logging
from pathlib import Path
from typing import List, AsyncGenerator, Optional, Tuple, Dict, Any, Union
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("discord_storage")
logger.setLevel(logging.INFO)

# 19 MiB in bytes
CHUNK_SIZE = 19 * 1024 * 1024

# Local fallback directory when webhook nodes are not configured or in offline mode
FALLBACK_DIR = Path(".local_storage_fallback")
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)


def clean_webhook_url(url: str) -> str:
    """Strip query parameters, whitespace, and trailing slashes."""
    if not url:
        return ""
    clean = url.strip().split("?")[0].rstrip("/")
    return clean


def is_valid_webhook_url(url: str) -> bool:
    clean = clean_webhook_url(url)
    if not clean:
        return False
    if "YOUR_WEBHOOK_ID" in clean:
        return False
    return (
        clean.startswith("https://discord.com/api/webhooks/") or
        clean.startswith("https://discordapp.com/api/webhooks/")
    )


def parse_webhook_urls(input_data: Union[str, List[str], None]) -> List[str]:
    """Parse comma-separated string, newline-separated string, or list into cleaned valid URLs."""
    if not input_data:
        return []
    
    raw_urls: List[str] = []
    if isinstance(input_data, list):
        raw_urls = input_data
    elif isinstance(input_data, str):
        # Split by comma or newline
        tokens = [t.strip() for token in input_data.replace("\n", ",").split(",") if (t := token.strip())]
        raw_urls = tokens

    valid_urls: List[str] = []
    seen = set()
    for u in raw_urls:
        c = clean_webhook_url(u)
        if c and is_valid_webhook_url(c) and c not in seen:
            seen.add(c)
            valid_urls.append(c)
    return valid_urls


def get_env_webhook_urls() -> List[str]:
    """Load storage node URLs from STORAGE_WEBHOOK_URLS or DISCORD_WEBHOOK_URL."""
    multi = os.getenv("STORAGE_WEBHOOK_URLS", "").strip()
    urls = parse_webhook_urls(multi)
    if urls:
        return urls
    
    single = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    return parse_webhook_urls(single)


class DiscordStorageEngine:
    def __init__(self, webhook_urls: Optional[Union[str, List[str]]] = None):
        if webhook_urls:
            self._node_urls: List[str] = parse_webhook_urls(webhook_urls)
        else:
            self._node_urls: List[str] = get_env_webhook_urls()
        
        self._round_robin_counter: int = 0
        logger.info(f"Initialized Storage Engine with {len(self._node_urls)} active node(s).")

    @property
    def is_configured(self) -> bool:
        return len(self._node_urls) > 0

    @property
    def node_count(self) -> int:
        return len(self._node_urls)

    def get_urls(self) -> List[str]:
        return list(self._node_urls)

    def set_urls(self, urls: Union[str, List[str]]):
        self._node_urls = parse_webhook_urls(urls)
        logger.info(f"Storage Engine updated: {len(self._node_urls)} active node(s).")

    def get_url(self) -> str:
        """Backwards compatibility helper: returns the primary node URL."""
        return self._node_urls[0] if self._node_urls else ""

    def set_url(self, new_url: str):
        """Backwards compatibility helper: sets single node URL."""
        self.set_urls([new_url] if new_url else [])

    def get_primary_url(self) -> str:
        return self._node_urls[0] if self._node_urls else ""

    def normalize_chunk(self, chunk_item: Any) -> Dict[str, str]:
        """
        Ensures any chunk descriptor (string, dict, local fallback) is normalized to:
        {"message_id": "...", "node_url": "..."}
        """
        primary = self.get_primary_url()
        if isinstance(chunk_item, str):
            return {"message_id": chunk_item, "node_url": primary}
        elif isinstance(chunk_item, dict):
            msg_id = str(chunk_item.get("message_id", ""))
            node_url = clean_webhook_url(chunk_item.get("node_url") or chunk_item.get("webhook_url") or primary)
            return {"message_id": msg_id, "node_url": node_url}
        return {"message_id": str(chunk_item), "node_url": primary}

    async def test_connection(self, url: Optional[str] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Test a single storage node webhook connection."""
        target_url = clean_webhook_url(url or self.get_primary_url())
        if not target_url:
            return False, "Storage node URL is empty.", None

        if not is_valid_webhook_url(target_url):
            return False, "Invalid node webhook URL format.", None

        timeout = httpx.Timeout(15.0, connect=8.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.get(target_url)
                if resp.status_code == 200:
                    data = resp.json()
                    name = data.get("name", "Storage Node")
                    channel_id = data.get("channel_id", "Unknown")
                    return True, f"Connected to '{name}' (Channel: {channel_id})", data
                elif resp.status_code == 404:
                    return False, "Storage node not found (404).", None
                elif resp.status_code == 401:
                    return False, "Storage node unauthorized (401). Invalid token.", None
                else:
                    return False, f"Node returned status {resp.status_code}: {resp.text}", None
            except Exception as e:
                return False, f"Connection failed: {str(e)}", None

    async def test_all_nodes(self) -> List[Dict[str, Any]]:
        """Concurrently test all configured storage nodes."""
        results = []
        if not self._node_urls:
            return results

        async def _test_single(idx: int, url: str) -> Dict[str, Any]:
            success, message, metadata = await self.test_connection(url)
            return {
                "id": idx,
                "name": f"Storage Node {idx}",
                "url": url,
                "success": success,
                "message": message,
                "metadata": metadata
            }

        tasks = [_test_single(i, url) for i, url in enumerate(self._node_urls, 1)]
        results = await asyncio.gather(*tasks)
        return list(results)

    async def _post_chunk_with_retry(
        self,
        client: httpx.AsyncClient,
        url: str,
        chunk_name: str,
        chunk_data: bytes,
        chunk_index: int,
        total_chunks: int,
        original_filename: str,
        node_num: int = 1
    ) -> str:
        """Upload a single chunk to the specified storage node with rate-limiting backoff."""
        post_url = f"{url}?wait=true"
        max_retries = 5
        base_delay = 1.5

        for attempt in range(max_retries):
            files = {
                "files[0]": (chunk_name, chunk_data, "application/octet-stream")
            }
            data = {
                "content": f"📦 **File Chunk**: `{chunk_name}` ({chunk_index + 1}/{total_chunks}) on Node {node_num} for `{original_filename}`"
            }

            try:
                resp = await client.post(post_url, data=data, files=files)

                # Rate-limit handling (429 Too Many Requests)
                if resp.status_code == 429:
                    retry_info = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                    retry_after = float(resp.headers.get("Retry-After", retry_info.get("retry_after", base_delay)))
                    wait_time = max(retry_after + 0.2, 0.5)
                    logger.warning(
                        f"[Node {node_num}] Rate limit hit. Backing off for {wait_time:.2f}s (Attempt {attempt + 1}/{max_retries})..."
                    )
                    await asyncio.sleep(wait_time)
                    continue

                if resp.status_code in (200, 201):
                    msg_data = resp.json()
                    message_id = str(msg_data.get("id"))
                    return message_id

                logger.error(f"[Node {node_num}] Upload error ({resp.status_code}): {resp.text}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                resp.raise_for_status()

            except httpx.RequestError as exc:
                logger.error(f"[Node {node_num}] Network error uploading chunk {chunk_name}: {exc}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(base_delay * (attempt + 1))
                    continue
                raise

        raise RuntimeError(f"Failed to upload chunk '{chunk_name}' on Node {node_num} after {max_retries} attempts.")

    async def upload_file_stream(
        self,
        filename: str,
        file_bytes: bytes,
        mime_type: str = "application/octet-stream"
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Splits file_bytes into 19MB chunks and uploads them across all available storage nodes
        using round-robin load balancing and parallel execution (up to 6 concurrent workers).
        Returns a list of chunk descriptors and total size.
        """
        total_size = len(file_bytes)
        num_chunks = max(1, (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE)

        # Fallback to local storage if no nodes configured
        if not self.is_configured:
            logger.info(f"Storage nodes not configured. Using local fallback storage for '{filename}'.")
            chunk_descriptors: List[Dict[str, Any]] = []
            for i in range(num_chunks):
                start = i * CHUNK_SIZE
                end = min(start + CHUNK_SIZE, total_size)
                chunk_slice = file_bytes[start:end]
                pseudo_id = f"local_{os.urandom(8).hex()}"
                chunk_path = FALLBACK_DIR / f"{pseudo_id}.part"
                chunk_path.write_bytes(chunk_slice)
                chunk_descriptors.append({
                    "message_id": pseudo_id,
                    "node_url": "local",
                    "node_index": 0
                })
            return chunk_descriptors, total_size

        nodes = self._node_urls
        num_nodes = len(nodes)

        # Calculate round-robin starting position
        start_counter = self._round_robin_counter
        self._round_robin_counter = (self._round_robin_counter + num_chunks) % num_nodes

        # Upload up to 6 chunks concurrently
        semaphore = asyncio.Semaphore(6)
        timeout = httpx.Timeout(120.0, connect=15.0)
        limits = httpx.Limits(max_connections=30, max_keepalive_connections=20)

        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            async def upload_worker(chunk_idx: int, chunk_slice: bytes, target_url: str, node_idx: int) -> Tuple[int, Dict[str, Any]]:
                chunk_name = filename if num_chunks == 1 else f"{filename}.part{chunk_idx}"
                async with semaphore:
                    msg_id = await self._post_chunk_with_retry(
                        client=client,
                        url=target_url,
                        chunk_name=chunk_name,
                        chunk_data=chunk_slice,
                        chunk_index=chunk_idx,
                        total_chunks=num_chunks,
                        original_filename=filename,
                        node_num=node_idx + 1
                    )
                    return chunk_idx, {
                        "message_id": msg_id,
                        "node_url": target_url,
                        "node_index": node_idx + 1
                    }

            tasks = []
            for i in range(num_chunks):
                node_idx = (start_counter + i) % num_nodes
                target_url = nodes[node_idx]
                start_byte = i * CHUNK_SIZE
                end_byte = min(start_byte + CHUNK_SIZE, total_size)
                slice_bytes = file_bytes[start_byte:end_byte]
                tasks.append(upload_worker(i, slice_bytes, target_url, node_idx))

            results = await asyncio.gather(*tasks)
            # Sort by chunk index to guarantee strictly sequential byte order
            results.sort(key=lambda x: x[0])
            chunk_descriptors = [r[1] for r in results]

        logger.info(f"Successfully uploaded '{filename}' ({total_size} bytes, {num_chunks} chunks) across {num_nodes} nodes.")
        return chunk_descriptors, total_size

    async def get_fresh_chunk_attachment_url(
        self,
        client: httpx.AsyncClient,
        node_url: str,
        message_id: str
    ) -> Optional[str]:
        """Fetch fresh unexpired attachment URL for a message from its specific node."""
        if not node_url or not is_valid_webhook_url(node_url) or message_id.startswith("local_"):
            return None

        msg_url = f"{node_url}/messages/{message_id}"
        max_retries = 3

        for attempt in range(max_retries):
            try:
                resp = await client.get(msg_url)
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", 1.0))
                    await asyncio.sleep(retry_after + 0.1)
                    continue

                if resp.status_code == 200:
                    data = resp.json()
                    attachments = data.get("attachments", [])
                    if attachments and "url" in attachments[0]:
                        return attachments[0]["url"]
                    logger.error(f"Message {message_id} on {node_url} has no attachments.")
                    return None
                elif resp.status_code == 404:
                    logger.error(f"Message {message_id} not found on node (404).")
                    return None
                else:
                    logger.warning(f"Failed to fetch fresh URL for message {message_id}: {resp.status_code}")
                    await asyncio.sleep(1.0)
            except Exception as e:
                logger.error(f"Error fetching message {message_id} from {node_url}: {e}")
                await asyncio.sleep(1.0)

        return None

    async def stream_file_chunks(
        self,
        chunk_items: List[Any],
        buffer_size: int = 65536
    ) -> AsyncGenerator[bytes, None]:
        """
        Asynchronously streams all chunks sequentially.
        Pre-fetches fresh CDN attachment URLs concurrently across all nodes for instant, stutter-free playback.
        """
        normalized = [self.normalize_chunk(c) for c in chunk_items]
        timeout = httpx.Timeout(90.0, connect=15.0)
        limits = httpx.Limits(max_connections=30, max_keepalive_connections=20)

        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            # Concurrently resolve fresh CDN URLs for all chunks
            async def resolve_url(chunk: Dict[str, str]) -> Tuple[Dict[str, str], Optional[str]]:
                msg_id = chunk["message_id"]
                node_url = chunk["node_url"]
                if msg_id.startswith("local_"):
                    return chunk, None
                url = await self.get_fresh_chunk_attachment_url(client, node_url, msg_id)
                return chunk, url

            resolved = await asyncio.gather(*[resolve_url(c) for c in normalized])

            # Stream each chunk in exact sequence
            for chunk, attachment_url in resolved:
                msg_id = chunk["message_id"]

                # Handle local fallback chunk
                if msg_id.startswith("local_"):
                    chunk_path = FALLBACK_DIR / f"{msg_id}.part"
                    if chunk_path.exists():
                        with open(chunk_path, "rb") as f:
                            while True:
                                data = f.read(buffer_size)
                                if not data:
                                    break
                                yield data
                    else:
                        logger.error(f"Fallback chunk {chunk_path} missing.")
                    continue

                if not attachment_url:
                    logger.error(f"Missing attachment URL for chunk {msg_id}")
                    continue

                # Stream bytes directly from CDN URL
                try:
                    async with client.stream("GET", attachment_url) as stream_resp:
                        if stream_resp.status_code in (200, 206):
                            async for b in stream_resp.aiter_bytes(chunk_size=buffer_size):
                                yield b
                        else:
                            logger.error(f"CDN download failed with status {stream_resp.status_code}")
                except Exception as e:
                    logger.error(f"Exception while streaming chunk {msg_id} from CDN: {e}")

    async def delete_chunk_messages(self, chunk_items: List[Any]):
        """
        Permanently deletes chunks concurrently from their respective storage nodes.
        """
        normalized = [self.normalize_chunk(c) for c in chunk_items]
        timeout = httpx.Timeout(20.0, connect=8.0)
        limits = httpx.Limits(max_connections=30, max_keepalive_connections=20)

        async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
            async def delete_single(chunk: Dict[str, str]):
                msg_id = chunk["message_id"]
                node_url = chunk["node_url"]

                if msg_id.startswith("local_"):
                    chunk_path = FALLBACK_DIR / f"{msg_id}.part"
                    if chunk_path.exists():
                        try:
                            chunk_path.unlink()
                        except Exception as e:
                            logger.error(f"Failed to delete local chunk {chunk_path}: {e}")
                    return

                if not node_url or not is_valid_webhook_url(node_url):
                    return

                delete_url = f"{node_url}/messages/{msg_id}"
                try:
                    resp = await client.delete(delete_url)
                    if resp.status_code == 429:
                        retry_after = float(resp.headers.get("Retry-After", 1.0))
                        await asyncio.sleep(retry_after)
                        await client.delete(delete_url)
                except Exception as e:
                    logger.error(f"Error deleting message {msg_id} from {node_url}: {e}")

            await asyncio.gather(*[delete_single(c) for c in normalized])
